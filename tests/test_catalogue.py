"""Generate catalogue tables from registrations while preserving surrounding prose."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from interop_trace.components import Registry
from scripts.update_component_tables import component_table, update_catalogue


def test_tables_show_registered_components_without_construction(
    monkeypatch: pytest.MonkeyPatch, http_transport: Mock
) -> None:
    registry: Registry[object] = Registry()
    factory = Mock()
    registry.register(
        "example", summary="Example component", documentation="components.md#example"
    )(factory)
    monkeypatch.setattr(
        "scripts.update_component_tables.REGISTRIES", {"datasets": registry}
    )
    table = component_table(detailed=True)
    assert (
        "| datasets | [`example`](components.md#example) | Example component |" in table
    )
    factory.assert_not_called()
    http_transport.assert_not_called()


def test_update_and_check_preserve_text_outside_markers(tmp_path: Path) -> None:
    (tmp_path / "docs/users").mkdir(parents=True)
    content = "Before\n<!-- components:start -->\nold\n<!-- components:end -->\nAfter\n"
    for relative in ("README.md", "docs/users/components.md"):
        (tmp_path / relative).write_text(content)
    with pytest.raises(ValueError, match="stale"):
        update_catalogue(tmp_path, check=True)
    assert (tmp_path / "README.md").read_text() == content
    update_catalogue(tmp_path)
    update_catalogue(tmp_path, check=True)
    assert (tmp_path / "README.md").read_text().startswith("Before\n")
    assert (tmp_path / "README.md").read_text().endswith("\nAfter\n")
    assert (
        component_table(link_prefix="docs/users/")
        in (tmp_path / "README.md").read_text()
    )


def test_committed_tables_match_registries() -> None:
    update_catalogue(Path(__file__).resolve().parents[1], check=True)
