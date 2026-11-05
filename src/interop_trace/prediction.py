"""A conservative baseline over frozen public metadata and a planned host."""

import json
from datetime import UTC, datetime
from itertools import permutations
from pathlib import Path
from typing import Any

from interop_trace.environment import capture_environment
from interop_trace.status import MetadataStatus
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
    entries: dict[str, dict[str, Any]], environment: dict[str, str]
) -> dict[str, Any]:
    """Compare declarations only; execution records are never prediction inputs.

    Coverage counts evaluable applicable checks, not confidence or probability.
    Support is limited to these checks. Populated declarations are treated as
    alternatives; a conflict may reflect incomplete metadata rather than failure.
    """
    checks = {
        "workflow_platform": _platform_check(entries.get("workflow", {}), environment),
        "input_interfaces": _interface_check(entries),
    }
    applicable = [c["conclusion"] for c in checks.values() if c["applicable"]]
    conclusion = Conclusion.UNKNOWN
    if Conclusion.CONFLICT in applicable:
        conclusion = Conclusion.CONFLICT
    elif applicable and all(c == Conclusion.SUPPORT for c in applicable):
        conclusion = Conclusion.SUPPORT
    return {
        "conclusion": conclusion,
        "failure_probability": None,
        "evidence_coverage": (
            sum(c != Conclusion.UNKNOWN for c in applicable) / len(applicable)
            if applicable
            else None
        ),
        "assumption": "Populated declarations are compared as allowed alternatives; "
        "a conflict is not proof of execution failure.",
        "checks": checks,
    }


def _strings(value: Any) -> set[str]:
    return (
        set(value)
        if isinstance(value, list) and all(isinstance(v, str) for v in value)
        else set()
    )


def _platform_check(
    entry: dict[str, Any], environment: dict[str, str]
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "applicable": True,
        "conclusion": Conclusion.UNKNOWN,
        "reason": "Missing or ambiguous host/platform declarations.",
        "evidence": {
            "workflow": ["toolType", "operatingSystem"],
            "environment": ["operating_system"],
        },
    }
    types = _strings(entry.get("toolType"))
    if types & _REMOTE:
        if types <= _REMOTE:
            result.update(
                applicable=False,
                reason="Only remote interfaces are declared; "
                "local OS support is inapplicable.",
            )
        return result
    host = {"Darwin": "Mac", "Linux": "Linux", "Windows": "Windows"}.get(
        environment.get("operating_system", "")
    )
    systems = _strings(entry.get("operatingSystem"))
    if host and systems and systems <= {"Mac", "Linux", "Windows"}:
        result.update(
            conclusion=Conclusion.SUPPORT if host in systems else Conclusion.CONFLICT,
            reason=f"Host {host}; advertised systems: {', '.join(sorted(systems))}.",
        )
    return result


def _ports(
    entry: dict[str, Any], direction: str, count: int
) -> list[tuple[str, set[str]]] | None:
    """Require one unambiguous function; portals do not identify file exports."""
    if _strings(entry.get("toolType")) & _PORTALS:
        return None
    functions = entry.get("function")
    if (
        not isinstance(functions, list)
        or len(functions) != 1
        or not isinstance(functions[0], dict)
    ):
        return None
    ports = functions[0].get(direction)
    if not isinstance(ports, list) or len(ports) != count:
        return None
    result = []
    for port in ports:
        if not isinstance(port, dict) or not isinstance(port.get("data"), dict):
            return None
        data = port["data"].get("uri")
        formats = port.get("format")
        if (
            not isinstance(data, str)
            or not data
            or not isinstance(formats, list)
            or not formats
        ):
            return None
        if any(
            not isinstance(f, dict) or not isinstance(f.get("uri"), str) or not f["uri"]
            for f in formats
        ):
            return None
        result.append((data, {f["uri"] for f in formats}))
    return result


def _interface_check(entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "applicable": True,
        "conclusion": Conclusion.UNKNOWN,
        "reason": "Requires one function per entry, one output per producer and "
        "two workflow inputs, with data and format URIs. "
        "Portal descriptions do not identify selected exports.",
        "evidence": {role: ["toolType", "function"] for role in _ROLES},
    }
    dataset = _ports(entries.get("dataset", {}), "output", 1)
    database = _ports(entries.get("database", {}), "output", 1)
    inputs = _ports(entries.get("workflow", {}), "input", 2)
    if dataset is None or database is None or inputs is None:
        return result
    matches = any(
        all(
            output[0] == port[0] and output[1] & port[1]
            for output, port in zip(dataset + database, assignment, strict=True)
        )
        for assignment in permutations(inputs)
    )
    result.update(
        conclusion=Conclusion.SUPPORT if matches else Conclusion.CONFLICT,
        reason="Distinct workflow inputs match both producers by exact data URI "
        "and overlapping format URIs."
        if matches
        else "No distinct-input assignment matches the declared data and format "
        "URIs. No ontology hierarchy or conversion is inferred.",
    )
    return result


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
            **predict_interoperability(entries, environment),
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
