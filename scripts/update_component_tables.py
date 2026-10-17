"""Regenerate marked component tables in the checkout's README and documentation."""

import argparse
from pathlib import Path

from interop_trace.registries import REGISTRIES

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
            "Component tables are stale; run "
            "poetry run python scripts/update_component_tables.py."
        )
    for path, updated in replacements:
        path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--check", action="store_true", help="Check tables without writing."
    )
    args = parser.parse_args()
    try:
        update_catalogue(args.root, check=args.check)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print("Component tables are current.")


if __name__ == "__main__":
    main()
