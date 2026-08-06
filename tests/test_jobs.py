import sys
import io
from unittest.mock import patch

from app.jobs import JobManager, JobSnapshot
from app.shell import TetherShell


def test_job_manager_runs_without_a_command_shell_and_captures_output():
    manager = JobManager()
    started = manager.start([sys.executable, "-c", "print('trap-hub-job')"])
    finished = manager.wait(started.job_id, timeout=10)

    assert finished.status == "completed"
    assert finished.returncode == 0
    assert "trap-hub-job" in finished.stdout
    manager.shutdown()


def test_job_manager_reports_nonzero_exit_as_failed():
    manager = JobManager()
    started = manager.start([sys.executable, "-c", "raise SystemExit(7)"])
    finished = manager.wait(started.job_id, timeout=10)

    assert finished.status == "failed"
    assert finished.returncode == 7
    manager.shutdown()


def test_job_manager_discards_output_beyond_the_configured_bound():
    manager = JobManager(output_limit=128)
    started = manager.start([sys.executable, "-c", "print('x' * 100000)"])
    finished = manager.wait(started.job_id, timeout=10)

    assert finished.status == "completed"
    assert "output truncated" in finished.stdout
    assert len(finished.stdout) < 256
    manager.shutdown()


def test_job_manager_rejects_empty_commands():
    manager = JobManager()
    try:
        manager.start([])
    except ValueError as exc:
        assert "requires an executable" in str(exc)
    else:
        raise AssertionError("empty job unexpectedly accepted")


class _RecordingJobs:
    def __init__(self):
        self.argv = None

    def start(self, argv):
        self.argv = tuple(argv)
        return JobSnapshot(7, self.argv, "running", 0.0)

    def list(self):
        return ()

    def shutdown(self):
        pass


def test_shell_background_marker_starts_managed_external_job():
    jobs = _RecordingJobs()
    shell = TetherShell(job_manager=jobs)

    with patch("sys.stdout", new=io.StringIO()):
        started = shell._execute("external-tool --safe value &", _from_script=True)

    assert started.job_id == 7
    assert jobs.argv == ("external-tool", "--safe", "value")


def test_shell_refuses_to_background_in_process_builtin_commands():
    jobs = _RecordingJobs()
    shell = TetherShell(job_manager=jobs)

    with patch("sys.stdout", new=io.StringIO()) as output:
        shell._execute("status &", _from_script=True)

    assert jobs.argv is None
    assert "limited to external tools" in output.getvalue()
