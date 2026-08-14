#!/usr/bin/env python3
"""Validate a pinned NVD JSON feed checkout and record release evidence."""

import argparse
from datetime import date
import json
from pathlib import Path
import re
import subprocess


class NvdEvidenceError(RuntimeError):
    """The NVD checkout is not a complete, clean pinned snapshot."""


def _git(repository, *args):
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def collect_evidence(repository, expected_revision, *, current_year=None):
    repository = Path(repository)
    if not re.fullmatch(r"[0-9a-f]{40}", expected_revision or ""):
        raise NvdEvidenceError("expected NVD revision is not a full Git SHA")
    try:
        revision = _git(repository, "rev-parse", "HEAD")
        status = _git(repository, "status", "--porcelain")
        commit_time = _git(repository, "show", "-s", "--format=%cI", "HEAD")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise NvdEvidenceError("unable to inspect NVD Git snapshot") from exc
    if revision != expected_revision:
        raise NvdEvidenceError("NVD checkout does not match the pinned revision")
    if status:
        raise NvdEvidenceError("NVD checkout is dirty")

    last_year = current_year or date.today().year
    complete_years = []
    for year in range(1999, last_year + 1):
        directory = repository / f"CVE-{year}"
        if not directory.is_dir() or not any(directory.rglob("*.json")):
            raise NvdEvidenceError(f"NVD snapshot has no JSON for CVE-{year}")
        complete_years.append(year)
    return {
        "revision": revision,
        "commit_time": commit_time,
        "repository_clean": True,
        "complete_years": complete_years,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("expected_revision")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    try:
        evidence = collect_evidence(args.repository, args.expected_revision)
        Path(args.output).write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, NvdEvidenceError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
