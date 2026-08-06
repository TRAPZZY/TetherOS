"""Managed, shell-free background processes for TRAP HUB."""

from dataclasses import dataclass
import subprocess
import threading
import time
from typing import Dict, Optional, Sequence


@dataclass(frozen=True)
class JobSnapshot:
    job_id: int
    argv: tuple
    status: str
    started_at: float
    finished_at: Optional[float] = None
    returncode: Optional[int] = None
    stdout: str = ""
    stderr: str = ""

    @property
    def duration_seconds(self):
        end = self.finished_at if self.finished_at is not None else time.time()
        return max(0.0, end - self.started_at)


class _Job:
    def __init__(self, snapshot, process):
        self.snapshot = snapshot
        self.process = process


class JobManager:
    """Own subprocess lifecycle and bounded captured output."""

    def __init__(self, *, max_jobs=16, output_limit=1024 * 1024, popen=subprocess.Popen):
        self.max_jobs = max_jobs
        self.output_limit = output_limit
        self._popen = popen
        self._jobs: Dict[int, _Job] = {}
        self._next_id = 1
        self._lock = threading.RLock()

    def start(self, argv: Sequence[str]) -> JobSnapshot:
        command = tuple(str(part) for part in argv)
        if not command or not command[0]:
            raise ValueError("A background job requires an executable.")
        with self._lock:
            active = sum(
                job.snapshot.status in {"running", "cancelling"}
                for job in self._jobs.values()
            )
            if active >= self.max_jobs:
                raise RuntimeError(f"Background job limit reached ({self.max_jobs}).")
            job_id = self._next_id
            self._next_id += 1

        process = self._popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )

        snapshot = JobSnapshot(job_id, command, "running", time.time())
        job = _Job(snapshot, process)
        with self._lock:
            self._jobs[job_id] = job
        threading.Thread(target=self._watch, args=(job_id,), daemon=True).start()
        return snapshot

    def _drain_output(self, stream, sink, name):
        retained = bytearray()
        truncated = False
        while True:
            chunk = stream.read(65536)
            if not chunk:
                break
            remaining = self.output_limit - len(retained)
            if remaining > 0:
                retained.extend(chunk[:remaining])
            if len(chunk) > max(remaining, 0):
                truncated = True
        text = bytes(retained).decode("utf-8", errors="replace")
        if truncated:
            text += "\n[TRAP HUB: output truncated]\n"
        sink[name] = text

    def _watch(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            return
        captured = {}
        readers = [
            threading.Thread(
                target=self._drain_output,
                args=(stream, captured, name),
                daemon=True,
            )
            for name, stream in (
                ("stdout", job.process.stdout),
                ("stderr", job.process.stderr),
            )
        ]
        for reader in readers:
            reader.start()
        returncode = job.process.wait()
        for reader in readers:
            reader.join()
        stdout = captured.get("stdout", "")
        stderr = captured.get("stderr", "")
        with self._lock:
            previous = job.snapshot
            status = "cancelled" if previous.status == "cancelling" else (
                "completed" if returncode == 0 else "failed"
            )
            job.snapshot = JobSnapshot(
                job_id=previous.job_id,
                argv=previous.argv,
                status=status,
                started_at=previous.started_at,
                finished_at=time.time(),
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            )

    def get(self, job_id: int) -> Optional[JobSnapshot]:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot if job else None

    def list(self):
        with self._lock:
            return tuple(self._jobs[job_id].snapshot for job_id in sorted(self._jobs))

    def wait(self, job_id: int, timeout=None) -> Optional[JobSnapshot]:
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            return None
        try:
            job.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return self.get(job_id)
        deadline = time.time() + 1.0
        while time.time() < deadline:
            snapshot = self.get(job_id)
            if snapshot and snapshot.status not in {"running", "cancelling"}:
                return snapshot
            time.sleep(0.01)
        return self.get(job_id)

    def cancel(self, job_id: int) -> Optional[JobSnapshot]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job.snapshot.status != "running":
                return job.snapshot
            job.snapshot = JobSnapshot(
                job_id=job.snapshot.job_id,
                argv=job.snapshot.argv,
                status="cancelling",
                started_at=job.snapshot.started_at,
            )
        job.process.terminate()
        return job.snapshot

    def shutdown(self):
        for snapshot in self.list():
            if snapshot.status in {"running", "cancelling"}:
                self.cancel(snapshot.job_id)
        for snapshot in self.list():
            if snapshot.status not in {"running", "cancelling"}:
                continue
            with self._lock:
                job = self._jobs.get(snapshot.job_id)
            if not job:
                continue
            try:
                job.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                job.process.kill()
