import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "filter_runtime_sbom", ROOT / "scripts" / "filter-runtime-sbom.py"
)
FILTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FILTER)


def _component(reference, package_type):
    return {
        "bom-ref": reference,
        "name": reference,
        "properties": [{"name": "BR_TYPE", "value": package_type}],
    }


def test_filters_host_components_dependencies_and_vulnerabilities():
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "metadata": {"component": {"bom-ref": "buildroot"}},
        "components": [_component("busybox", "target"), _component("host-make", "host")],
        "dependencies": [
            {"ref": "buildroot", "dependsOn": ["busybox", "host-make"]},
            {"ref": "busybox", "dependsOn": []},
            {"ref": "host-make", "dependsOn": []},
        ],
        "vulnerabilities": [
            {"id": "CVE-TARGET", "affects": [{"ref": "busybox"}]},
            {"id": "CVE-HOST", "affects": [{"ref": "host-make"}]},
        ],
    }
    result = FILTER.filter_runtime_sbom(document)
    assert [item["bom-ref"] for item in result["components"]] == ["busybox"]
    assert result["dependencies"] == [
        {"ref": "buildroot", "dependsOn": ["busybox"]},
        {"ref": "busybox", "dependsOn": []},
    ]
    assert [item["id"] for item in result["vulnerabilities"]] == ["CVE-TARGET"]


def test_requires_explicit_buildroot_target_metadata():
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [{"bom-ref": "ambiguous", "properties": []}],
    }
    with pytest.raises(FILTER.SbomFilterError, match="ambiguous BR_TYPE"):
        FILTER.filter_runtime_sbom(document)


def test_rejects_vulnerability_without_affects():
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [_component("busybox", "target")],
        "vulnerabilities": [{"id": "CVE-AMBIGUOUS"}],
    }
    with pytest.raises(FILTER.SbomFilterError, match="affected component"):
        FILTER.filter_runtime_sbom(document)


@pytest.mark.parametrize("properties", [
    [],
    [{"name": "BR_TYPE", "value": "mystery"}],
    [
        {"name": "BR_TYPE", "value": "target"},
        {"name": "BR_TYPE", "value": "host"},
    ],
])
def test_rejects_ambiguous_component_types(properties):
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [
            _component("busybox", "target"),
            {"bom-ref": "ambiguous", "name": "ambiguous", "properties": properties},
        ],
    }
    with pytest.raises(FILTER.SbomFilterError, match="BR_TYPE|duplicated"):
        FILTER.filter_runtime_sbom(document)


def test_rejects_unknown_dependency_and_vulnerability_refs():
    base = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [_component("busybox", "target")],
        "dependencies": [{"ref": "busybox", "dependsOn": ["unknown"]}],
    }
    with pytest.raises(FILTER.SbomFilterError, match="dangling"):
        FILTER.filter_runtime_sbom(base)
    base["dependencies"] = []
    base["vulnerabilities"] = [{
        "id": "CVE-X", "affects": [{"ref": "busybox"}, {"ref": "unknown"}]
    }]
    with pytest.raises(FILTER.SbomFilterError, match="dangling"):
        FILTER.filter_runtime_sbom(base)
