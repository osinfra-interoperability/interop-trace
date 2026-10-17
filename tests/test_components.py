"""Check registration, construction and the optional setup boundary."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from interop_trace.components import Registry, RequiresSetup
from interop_trace.downloads import DownloadCache


def test_registration_and_construction_do_not_run_setup(tmp_path: Path) -> None:
    registry: Registry[object] = Registry()
    events: list[str] = []

    @registry.register("example", summary="Example", documentation="components.md")
    class Component:
        def setup(self, *, cache: DownloadCache) -> None:
            events.append(str(cache.root))

    assert registry["example"].factory is Component
    component = registry.create("example", {}, base_dir=tmp_path)
    assert isinstance(component, RequiresSetup)
    assert not events
    component.setup(cache=DownloadCache(tmp_path / "cache"))
    assert events == [str(tmp_path / "cache")]
    assert not isinstance(object(), RequiresSetup)


def test_only_declared_paths_are_resolved(tmp_path: Path) -> None:
    registry: Registry[object] = Registry()
    constructor = Mock()
    registry.register(
        "example", summary="Example", documentation="components.md", paths=("file",)
    )(constructor)
    settings: dict[str, object] = {"file": "../input.json", "query": "some/string"}
    registry.create("example", settings, base_dir=tmp_path)
    constructor.assert_called_once_with(
        file=(tmp_path / "../input.json").resolve(), query="some/string"
    )
    assert settings["file"] == "../input.json"


def test_duplicate_and_unknown_names_fail(tmp_path: Path) -> None:
    registry: Registry[object] = Registry()
    register = registry.register("example", summary="Example", documentation="x.md")
    register(object)
    with pytest.raises(ValueError, match="already registered"):
        register(object)
    with pytest.raises(ValueError, match="Unknown component"):
        registry.create("missing", {}, base_dir=tmp_path)
