from datetime import datetime, timezone
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_cve_report", ROOT / "scripts" / "check-cve-report.py"
)
CVE_GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CVE_GATE)
NOW = datetime(2026, 8, 13, tzinfo=timezone.utc)


def _component(*, cpe="cpe:2.3:a:busybox:busybox:1.37.0:*:*:*:*:*:*:*"):
    component = {
        "bom-ref": "busybox",
        "name": "busybox",
        "version": "1.37.0",
        "properties": [{"name": "BR_TYPE", "value": "target"}],
    }
    if cpe is not None:
        component["cpe"] = cpe
    return component


def _report(vulnerabilities):
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [_component()],
        "vulnerabilities": vulnerabilities,
    }


def _vulnerability(*, state="exploitable", severity="high", score=8.1, affects=True):
    rating = {}
    if severity is not None:
        rating["severity"] = severity
    if score is not None:
        rating["score"] = score
    result = {
        "id": "CVE-2099-0001",
        "analysis": {"state": state},
        "ratings": [rating] if rating else [],
    }
    if affects:
        result["affects"] = [{"ref": "busybox"}]
    return result


def _evidence():
    return {
        "revision": "a" * 40,
        "commit_time": "2026-08-12T00:00:00+00:00",
        "repository_clean": True,
        "complete_years": list(range(1999, 2027)),
    }


def _evaluate(report, policy=None, evidence=None):
    return CVE_GATE.evaluate_report(
        report,
        coverage_policy=policy or {"exceptions": []},
        nvd_evidence=evidence or _evidence(),
        now=NOW,
    )


def test_blocks_exploitable_high_runtime_cve():
    result = _evaluate(_report([_vulnerability()]))
    assert result["result"] == "FAIL"


def test_blocks_rating_disagreement_conservatively():
    result = _evaluate(_report([_vulnerability(severity="medium", score=8.1)]))
    assert result["result"] == "FAIL"


def test_allows_unresolved_medium_cve_at_high_critical_gate():
    result = _evaluate(_report([_vulnerability(severity="medium", score=5.4)]))
    assert result["result"] == "PASS"


def test_blocks_every_unscored_unresolved_cve():
    for severity, score in (("unknown", None), ("medium", None), (None, None)):
        with pytest.raises(CVE_GATE.CveGateError, match="no ratings") if severity is None else _nullcontext():
            result = _evaluate(_report([_vulnerability(severity=severity, score=score)]))
            assert result["result"] == "FAIL"


def test_accepts_buildroot_cvssv2_rating_without_severity_when_score_is_medium():
    vulnerability = _vulnerability(severity=None, score=None)
    vulnerability["ratings"] = [{
        "method": "CVSSv2", "score": 5.0, "vector": "AV:N/AC:L/Au:N/C:P/I:N/A:N"
    }]
    assert _evaluate(_report([vulnerability]))["result"] == "PASS"


def test_rejects_critical_vulnerability_without_affects():
    with pytest.raises(CVE_GATE.CveGateError, match="no affected"):
        _evaluate(_report([_vulnerability(affects=False)]))


def test_rejects_ambiguous_component_type_and_wrong_spec():
    report = _report([])
    report["components"][0]["properties"] = []
    with pytest.raises(CVE_GATE.CveGateError, match="ambiguous"):
        _evaluate(report)
    report = _report([])
    report["specVersion"] = "1.5"
    with pytest.raises(CVE_GATE.CveGateError, match="1.6"):
        _evaluate(report)


def test_requires_matching_pedigree_for_resolved_with_pedigree():
    report = _report([_vulnerability(state="resolved_with_pedigree")])
    with pytest.raises(CVE_GATE.CveGateError, match="pedigree"):
        _evaluate(report)
    report["components"][0]["pedigree"] = {
        "patches": [{
            "resolves": [{"type": "security", "name": "CVE-2099-0001"}]
        }]
    }
    assert _evaluate(report)["result"] == "PASS"


def test_requires_cpe_or_current_owned_exception():
    report = _report([])
    report["components"] = [_component(cpe=None)]
    with pytest.raises(CVE_GATE.CveGateError, match="CVE coverage"):
        _evaluate(report)
    policy = {"exceptions": [{
        "components": ["busybox"],
        "owner": "Security",
        "justification": "No upstream CPE mapping is available.",
        "alternative_control": "Trivy rootfs scan and upstream advisory review.",
        "expires": "2026-12-01",
    }]}
    assert _evaluate(report, policy=policy)["result"] == "PASS"
    del report["components"][0]["version"]
    assert _evaluate(report, policy=policy)["result"] == "PASS"


@pytest.mark.parametrize("severity,score", [
    ("bogus", 5.0), ("medium", -1.0), ("medium", float("nan")), ("medium", False)
])
def test_rejects_malformed_severity_and_score(severity, score):
    with pytest.raises(CVE_GATE.CveGateError, match="severity|score"):
        _evaluate(_report([_vulnerability(severity=severity, score=score)]))


def test_rejects_stale_or_incomplete_nvd_evidence():
    stale = _evidence()
    stale["commit_time"] = "2026-07-01T00:00:00+00:00"
    with pytest.raises(CVE_GATE.CveGateError, match="freshness"):
        _evaluate(_report([]), evidence=stale)
    incomplete = _evidence()
    incomplete["complete_years"] = list(range(2000, 2027))
    with pytest.raises(CVE_GATE.CveGateError, match="every required"):
        _evaluate(_report([]), evidence=incomplete)


class _nullcontext:
    def __enter__(self):
        return None

    def __exit__(self, *_args):
        return False
