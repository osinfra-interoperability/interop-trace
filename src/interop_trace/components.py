"""Shared setup contract and explicit, decorator-populated component registries."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

from interop_trace.downloads import DownloadCache


@runtime_checkable
class RequiresSetup(Protocol):
    """A component whose resources must be resolved before execution.

    Setup may download through the supplied cache and must be safe to repeat.
    Construction and registration must not perform setup or network requests.
    """

    def setup(self, *, cache: DownloadCache) -> None:
        """Resolve resources or raise, without producing experiment reports."""
        ...


@dataclass(frozen=True)
class ComponentEntry[T]:
    """An implementation's constructor and public catalogue information.

    ``paths`` identifies constructor parameters resolved relative to their
    component definition file. Other parameters retain their native values.
    """

    factory: Callable[..., T]
    summary: str
    documentation: str
    paths: tuple[str, ...] = ()


class Registry[T](dict[str, ComponentEntry[T]]):
    """One layer's explicitly imported implementations, keyed by stable name."""

    def register[F: Callable[..., Any]](
        self,
        name: str,
        *,
        summary: str,
        documentation: str,
        paths: tuple[str, ...] = (),
    ) -> Callable[[F], F]:
        """Register a constructor without instantiating or setting it up."""

        def decorate(factory: F) -> F:
            if name in self:
                raise ValueError(f"Component {name!r} is already registered.")
            self[name] = ComponentEntry(
                cast(Callable[..., T], factory), summary, documentation, paths
            )
            return factory

        return decorate

    def create(self, name: str, parameters: dict[str, object], *, base_dir: Path) -> T:
        """Construct an implementation, resolving only its declared path settings."""
        try:
            entry = self[name]
        except KeyError:
            raise ValueError(
                f"Unknown component {name!r}; choose from {sorted(self)}."
            ) from None
        settings = dict(parameters)
        for key in entry.paths:
            if key in settings:
                value = settings[key]
                if not isinstance(value, (str, Path)):
                    raise ValueError(f"{name}.{key} must be a file path.")
                settings[key] = (base_dir / value).resolve()
        try:
            return entry.factory(**settings)
        except TypeError as error:
            raise ValueError(f"Invalid settings for {name!r}: {error}") from error
