"""A conservative baseline over frozen public metadata and a planned host."""

import json
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

from interop_trace.edam import Edam, edam_uri
from interop_trace.environment import capture_environment
from interop_trace.status import MetadataStatus, PredictionAspect
from interop_trace.status import PredictionConclusion as Conclusion

_ROLES = ("dataset", "database", "workflow")
_REMOTE = {
    "Web API",
    "Web service",
    "Web application",
    "Database portal",
    "Bioinformatics portal",
    "SPARQL endpoint",
}
_PORTALS = {"Database portal", "Bioinformatics portal"}


def predict_interoperability(
    entries: dict[str, dict[str, Any]], environment: dict[str, str], ontology: Edam
) -> dict[str, Any]:
    """Report partial positive evidence separately from coverage and probability.

    Data is semantic, formats and shared OS support are technical, and run OS
    checks are host-specific. Each connection uses its strongest input/output
    pair (data preferred when tied) to keep evidence on the same declaration.
    """
    systems = {role: _local_systems(entries.get(role, {})) for role in _ROLES}
    host = {"Darwin": "Mac", "Linux": "Linux", "Windows": "Windows"}.get(
        environment.get("operating_system", "")
    )
    checks = {"shared_platform": _shared_platform_check(systems)}
    checks.update(
        {
            f"{role}_platform": _platform_check(role, oses, host)
            for role, oses in systems.items()
        }
    )
    for role in ("dataset", "database"):
        checks.update(
            {
                f"{role}_{axis}": check
                for axis, check in _connection_checks(entries, role, ontology).items()
            }
        )
    return {
        **_summary(list(checks.values())),
        "aspects": {
            aspect: _summary([c for c in checks.values() if c["aspect"] == aspect])
            for aspect in PredictionAspect
        },
        "failure_probability": None,
        "assumption": "Support is positive evidence, not proof of executability. "
        "Populated OS declarations are treated as allowed alternatives. "
        "A subtype is assumed acceptable where a broader input is declared. "
        "The strongest single pair per producer is reported, preferring data "
        "when tied. Additional inputs and joint workflow-mode requirements "
        "are not established.",
        "checks": checks,
    }


def _summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    conclusions = [c["conclusion"] for c in checks if c["applicable"]]
    conclusion = Conclusion.UNKNOWN
    if Conclusion.CONFLICT in conclusions:
        conclusion = Conclusion.CONFLICT
    elif Conclusion.SUPPORT in conclusions:
        conclusion = Conclusion.SUPPORT
    return {
        "conclusion": conclusion,
        "evidence_coverage": (
            sum(c != Conclusion.UNKNOWN for c in conclusions) / len(conclusions)
            if conclusions
            else None
        ),
    }


def _strings(value: Any) -> set[str]:
    return (
        set(value)
        if isinstance(value, list) and all(isinstance(v, str) for v in value)
        else set()
    )


def _local_systems(entry: dict[str, Any]) -> set[str] | None:
    """Return advertised systems, an empty set if unknown, or None if remote."""
    types = _strings(entry.get("toolType"))
    if types & _REMOTE:
        return None if types <= _REMOTE else set()
    systems = _strings(entry.get("operatingSystem"))
    return systems if systems <= {"Mac", "Linux", "Windows"} else set()


def _shared_platform_check(systems: dict[str, set[str] | None]) -> dict[str, Any]:
    local = [oses for oses in systems.values() if oses is not None]
    declared = [oses for oses in local if oses]
    result: dict[str, Any] = {
        "aspect": PredictionAspect.TECHNICAL,
        "applicable": len(local) >= 2,
        "conclusion": Conclusion.UNKNOWN,
        "reason": "Local OS declarations are incomplete or ambiguous.",
        "shared_operating_systems": None,
        "evidence": {role: ["toolType", "operatingSystem"] for role in systems},
    }
    if len(local) < 2:
        result["reason"] = (
            "Fewer than two components have an applicable local OS check."
        )
    elif len(declared) >= 2:
        common = set.intersection(*declared)
        if not common:
            result.update(
                conclusion=Conclusion.CONFLICT,
                reason="The advertised OS sets have no common system.",
                shared_operating_systems=[],
            )
        elif len(declared) == len(local):
            result.update(
                conclusion=Conclusion.SUPPORT,
                reason="All local components advertise at least one common OS.",
                shared_operating_systems=sorted(common),
            )
    return result


def _platform_check(
    role: str, systems: set[str] | None, host: str | None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "aspect": PredictionAspect.HOST,
        "applicable": True,
        "conclusion": Conclusion.UNKNOWN,
        "reason": "Missing or ambiguous host/platform declarations.",
        "evidence": {
            role: ["toolType", "operatingSystem"],
            "environment": ["operating_system"],
        },
    }
    if systems is None:
        result.update(
            applicable=False,
            reason="Only remote interfaces are declared.",
        )
    elif host and systems:
        result.update(
            conclusion=Conclusion.SUPPORT if host in systems else Conclusion.CONFLICT,
            reason=f"Host {host}; advertised systems: {', '.join(sorted(systems))}.",
        )
    return result


def _ports(
    entry: dict[str, Any], role: str, direction: str
) -> tuple[list[tuple[str, dict[str, Any]]], str]:
    """Return declared ports and explain when they cannot be used."""
    label = role.capitalize()
    if not entry:
        return [], f"No saved bio.tools description for the {role}."
    functions = entry.get("function")
    result: list[tuple[str, dict[str, Any]]] = []
    for fi, function in enumerate(functions if isinstance(functions, list) else []):
        ports = function.get(direction) if isinstance(function, dict) else None
        if isinstance(ports, list):
            result.extend(
                (f"#/function/{fi}/{direction}/{pi}", port)
                for pi, port in enumerate(ports)
                if isinstance(port, dict)
            )
    if not result:
        return [], f"{label} bio.tools entry declares no {direction} ports."
    if _strings(entry.get("toolType")) & _PORTALS:
        return [], (
            f"{label} bio.tools entry describes a portal and its {direction} ports "
            "do not identify the file used in this connection."
        )
    return result, ""


def _concepts(port: dict[str, Any], axis: str) -> list[str]:
    values = [port.get("data")] if axis == "data" else port.get("format", [])
    if not isinstance(values, list):
        return []
    return [
        uri
        for value in values
        if isinstance(value, dict) and (uri := edam_uri(value.get("uri")))
    ]


def _match(
    output: dict[str, Any], accepted: dict[str, Any], axis: str, ontology: Edam
) -> dict[str, str] | None:
    for source, target in product(_concepts(output, axis), _concepts(accepted, axis)):
        if relation := ontology.match(source, target, axis):
            return {"output_uri": source, "input_uri": target, "relation": relation}
    return None


def _unmatched_reason(
    outputs: list[dict[str, Any]],
    inputs: list[dict[str, Any]],
    axis: str,
    ontology: Edam,
) -> str:
    output_terms = {uri for port in outputs for uri in _concepts(port, axis)}
    input_terms = {uri for port in inputs for uri in _concepts(port, axis)}
    label = "data type" if axis == "data" else "format"
    for side, terms in (("output", output_terms), ("input", input_terms)):
        if not terms:
            return f"No usable EDAM {label} URI is declared on the {side} side."
        if not terms.intersection(ontology.ancestors):
            return f"No declared {side} {label} URI resolved in the saved EDAM terms."
    return f"The declared {label} terms have no supported output-to-input EDAM match."


def _connection_checks(
    entries: dict[str, dict[str, Any]], role: str, ontology: Edam
) -> dict[str, dict[str, Any]]:
    outputs, output_blocker = _ports(entries.get(role, {}), role, "output")
    inputs, input_blocker = _ports(entries.get("workflow", {}), "workflow", "input")
    checks: dict[str, dict[str, Any]] = {
        axis: {
            "aspect": aspect,
            "applicable": True,
            "conclusion": Conclusion.UNKNOWN,
            "reason": " ".join(filter(None, (output_blocker, input_blocker))),
            "evidence": {
                role: ["toolType", "function"],
                "workflow": ["toolType", "function"],
                "ontology": ["iri", "isObsolete", "directAncestor"],
            },
        }
        for axis, aspect in (
            ("data", PredictionAspect.SEMANTIC),
            ("format", PredictionAspect.TECHNICAL),
        )
    }
    best = (False, False, False)
    for (output_ref, output), (input_ref, accepted) in product(outputs, inputs):
        matches = {axis: _match(output, accepted, axis, ontology) for axis in checks}
        data, format_ = matches["data"] is not None, matches["format"] is not None
        score = (data and format_, data, format_)
        if score <= best:
            continue
        best = score
        for axis, check in checks.items():
            match = matches[axis]
            check.update(
                conclusion=Conclusion.SUPPORT if match else Conclusion.UNKNOWN,
                reason="Same concept or output specialises the accepted input."
                if match
                else _unmatched_reason([output], [accepted], axis, ontology),
                pair={"output": role + output_ref, "input": "workflow" + input_ref},
                match=match,
            )
    for axis, check in checks.items():
        if not check["reason"]:
            check["reason"] = _unmatched_reason(
                [port for _, port in outputs],
                [port for _, port in inputs],
                axis,
                ontology,
            )
    return checks


def predict_run(directory: Path) -> list[Path]:
    """Save predictions once, before execution, without constructing components."""
    directory = directory.resolve()
    if (directory / "execution.json").exists():
        raise ValueError("Predict before execution; create a new run.")
    configuration = json.loads((directory / "configuration.json").read_text())
    index = json.loads((directory / "metadata/index.json").read_text())
    names = [choice["id"] for choice in configuration["experiments"]]
    if not names or any(
        not name or Path(name).name != name or name in {".", ".."} for name in names
    ):
        raise ValueError("Expected simple experiment IDs in the saved configuration.")
    outputs = [directory / name / "prediction.json" for name in names]
    if any(output.exists() for output in outputs):
        raise FileExistsError("Existing predictions are preserved; create a new run.")
    ontology, ontology_source = _read_ontology(directory / "metadata", index)
    environment = capture_environment()
    environment_path = directory / "prediction_environment.json"
    with environment_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(environment, indent=2) + "\n")
    for name, output in zip(names, outputs, strict=True):
        entries, sources = {}, {}
        for role in _ROLES:
            rows = [
                (i, row)
                for i, row in enumerate(index["components"])
                if row["experiment"] == name and row["role"] == role
            ]
            sources[role] = {
                "index": "../metadata/index.json",
                "rows": [i for i, _ in rows],
            }
            if len(rows) == 1:
                entry, source = _read_entry(directory / "metadata", rows[0][1])
                entries[role] = entry
                sources[role].update(source)
        prediction = {
            "created_at": datetime.now(UTC).isoformat(),
            "environment": "../prediction_environment.json",
            "metadata": sources,
            "ontology": ontology_source,
            **predict_interoperability(entries, environment, ontology),
        }
        with output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(prediction, indent=2) + "\n")
    return outputs


def _read_entry(
    metadata: Path, row: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    if row["status"] != MetadataStatus.COLLECTED:
        return {}, {"status": row["status"]}
    entry = (metadata / row["directory"] / "entry.json").resolve()
    if not entry.is_relative_to(metadata):
        raise ValueError("Metadata entry must stay inside the run metadata directory.")
    source = {"entry": "../metadata/" + str(entry.relative_to(metadata))}
    try:
        value = json.loads(entry.read_text())
    except (OSError, ValueError):
        return {}, {**source, "status": "unreadable_entry"}
    if not isinstance(value, dict):
        return {}, {**source, "status": "invalid_entry"}
    return value, {**source, "status": row["status"]}


def _read_ontology(
    metadata: Path, index: dict[str, Any]
) -> tuple[Edam, dict[str, Any]]:
    if "ontology" not in index:
        raise ValueError(
            "Collect metadata with EDAM term responses in a new run first."
        )
    responses = []
    source: dict[str, Any] = {
        "index": "../metadata/index.json#/ontology",
        "unreadable": [],
    }
    for row in index["ontology"]["requests"]:
        if row["status"] != MetadataStatus.COLLECTED or not row["term"]:
            continue
        path = (metadata / row["response"]).resolve()
        if not path.is_relative_to(metadata):
            raise ValueError("EDAM response must stay inside the metadata directory.")
        try:
            response = json.loads(path.read_text())
            if (
                not isinstance(response, dict)
                or edam_uri(response.get("iri")) != row["term"]
            ):
                raise ValueError("OLS response does not identify the requested term.")
            responses.append(response)
        except (OSError, ValueError) as error:
            source["unreadable"].append(
                {"response": row["response"], "error": str(error)}
            )
    return Edam.from_responses(responses), source
