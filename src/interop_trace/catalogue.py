"""The four built-in layer registries, shared by configuration and documentation."""

from pathlib import Path
from typing import Any

from interop_trace.components import Registry
from interop_trace.databases.registry import registry as databases
from interop_trace.datasets.registry import registry as datasets
from interop_trace.evaluation.registry import registry as benchmarks
from interop_trace.workflows.registry import registry as workflows

REGISTRIES: dict[str, Registry[Any]] = {
    "datasets": datasets,
    "databases": databases,
    "workflows": workflows,
    "benchmarks": benchmarks,
}

_START = "<!-- components:start -->"
_END = "<!-- components:end -->"


def component_table(*, detailed: bool = False, link_prefix: str = "") -> str:
    """Render installed registrations without constructing or setting up tools."""
    lines = ["| Layer | Component |", "| --- | --- |"]
    if detailed:
        lines = ["| Layer | Component | Description |", "| --- | --- | --- |"]
    for layer, registry in REGISTRIES.items():
        for name, entry in sorted(registry.items()):
            link = f"[`{name}`]({link_prefix}{entry.documentation})"
            cells = [layer, link, *([entry.summary] if detailed else [])]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def update_catalogue(root: Path, *, check: bool = False) -> None:
    """Update only marked README and documentation tables, or check for drift."""
    replacements = []
    for path, detailed, prefix in (
        (root / "README.md", False, "docs/"),
        (root / "docs/components.md", True, ""),
    ):
        content = path.read_text(encoding="utf-8")
        if content.count(_START) != 1 or content.count(_END) != 1:
            raise ValueError(f"Expected one component catalogue marker pair in {path}.")
        before, _, rest = content.partition(_START)
        _, separator, after = rest.partition(_END)
        if not separator:
            raise ValueError(f"Component catalogue markers are out of order in {path}.")
        table = component_table(detailed=detailed, link_prefix=prefix)
        updated = f"{before}{_START}\n\n{table}\n\n{_END}{after}"
        if updated != content:
            replacements.append((path, updated))
    if check and replacements:
        raise ValueError(
            "Component tables are stale; run interop-trace components --update-docs."
        )
    for path, updated in replacements:
        path.write_text(updated, encoding="utf-8")
