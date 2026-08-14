#!/usr/bin/env python3
"""Create a target-runtime-only CycloneDX document from Buildroot output."""

import argparse
import copy
import json
from pathlib import Path


class SbomFilterError(RuntimeError):
    """The Buildroot SBOM does not contain a trustworthy runtime graph."""


def _properties(component):
    properties = component.get("properties")
    if not isinstance(properties, list):
        raise SbomFilterError("component properties are missing or malformed")
    result = {}
    for item in properties:
        if not isinstance(item, dict):
            raise SbomFilterError("component property is not an object")
        name = item.get("name")
        value = item.get("value")
        if not isinstance(name, str) or not isinstance(value, str) or name in result:
            raise SbomFilterError("component properties are malformed or duplicated")
        result[name] = value
    return result


def filter_runtime_sbom(document):
    if not isinstance(document, dict) or document.get("bomFormat") != "CycloneDX":
        raise SbomFilterError("input is not a CycloneDX document")
    if document.get("specVersion") != "1.6":
        raise SbomFilterError("input is not CycloneDX 1.6")
    components = document.get("components")
    if not isinstance(components, list):
        raise SbomFilterError("input has no component inventory")

    runtime_components = []
    runtime_refs = set()
    full_refs = set()
    for component in components:
        if not isinstance(component, dict):
            raise SbomFilterError("component entry is not an object")
        properties = _properties(component)
        package_type = properties.get("BR_TYPE")
        if package_type not in {"host", "target"}:
            raise SbomFilterError("component has an invalid or ambiguous BR_TYPE")
        reference = component.get("bom-ref")
        if not isinstance(reference, str) or not reference:
            raise SbomFilterError("component has no bom-ref")
        if reference in full_refs:
            raise SbomFilterError(f"duplicate component bom-ref: {reference}")
        full_refs.add(reference)
        if package_type != "target":
            continue
        runtime_refs.add(reference)
        runtime_components.append(copy.deepcopy(component))

    if not runtime_components:
        raise SbomFilterError("input has no explicit target runtime components")

    result = copy.deepcopy(document)
    result["components"] = sorted(
        runtime_components, key=lambda item: item["bom-ref"]
    )
    root = (result.get("metadata") or {}).get("component") or {}
    root_ref = root.get("bom-ref") if isinstance(root, dict) else None
    allowed_refs = set(runtime_refs)
    if isinstance(root_ref, str) and root_ref:
        allowed_refs.add(root_ref)

    dependencies = result.get("dependencies", [])
    if dependencies is not None and not isinstance(dependencies, list):
        raise SbomFilterError("dependencies is not a list")
    filtered_dependencies = []
    for dependency in dependencies or []:
        if not isinstance(dependency, dict):
            raise SbomFilterError("dependency entry is not an object")
        reference = dependency.get("ref")
        if reference not in full_refs and reference != root_ref:
            raise SbomFilterError("dependency has a dangling component ref")
        if reference not in allowed_refs:
            continue
        filtered = copy.deepcopy(dependency)
        depends_on = filtered.get("dependsOn", [])
        if not isinstance(depends_on, list):
            raise SbomFilterError("dependency dependsOn is not a list")
        if any(ref not in full_refs for ref in depends_on):
            raise SbomFilterError("dependency has a dangling dependsOn ref")
        filtered["dependsOn"] = sorted(
            ref for ref in depends_on if ref in runtime_refs
        )
        filtered_dependencies.append(filtered)
    result["dependencies"] = sorted(
        filtered_dependencies, key=lambda item: item["ref"]
    )

    vulnerabilities = result.get("vulnerabilities", [])
    if vulnerabilities is not None and not isinstance(vulnerabilities, list):
        raise SbomFilterError("vulnerabilities is not a list")
    filtered_vulnerabilities = []
    for vulnerability in vulnerabilities or []:
        if not isinstance(vulnerability, dict):
            raise SbomFilterError("vulnerability entry is not an object")
        affects = vulnerability.get("affects")
        if not isinstance(affects, list) or not affects:
            raise SbomFilterError("vulnerability has no affected component reference")
        if any(
            not isinstance(item, dict) or item.get("ref") not in full_refs
            for item in affects
        ):
            raise SbomFilterError("vulnerability has a dangling affected component ref")
        runtime_affects = [
            copy.deepcopy(item)
            for item in affects
            if isinstance(item, dict) and item.get("ref") in runtime_refs
        ]
        if not runtime_affects:
            continue
        filtered = copy.deepcopy(vulnerability)
        filtered["affects"] = sorted(runtime_affects, key=lambda item: item["ref"])
        filtered_vulnerabilities.append(filtered)
    result["vulnerabilities"] = sorted(
        filtered_vulnerabilities,
        key=lambda item: (
            str(item.get("id", "")),
            str((item.get("analysis") or {}).get("state", "")),
            tuple(affected.get("ref", "") for affected in item["affects"]),
        ),
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Buildroot CycloneDX JSON")
    parser.add_argument("output", help="target-only CycloneDX JSON")
    args = parser.parse_args(argv)
    source = Path(args.input)
    destination = Path(args.output)
    document = json.loads(source.read_text(encoding="utf-8"))
    filtered = filter_runtime_sbom(document)
    destination.write_text(
        json.dumps(filtered, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
