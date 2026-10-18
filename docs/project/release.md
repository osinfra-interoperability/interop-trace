# Releases

`project.version` in `pyproject.toml` is the source of the installed package version.
Run records include that version; provider and workflow reports separately identify
external data releases and executable versions where available.

When changing the package version, update `pyproject.toml` and run the
[development checks](../developers/developer.md#setup-and-checks). The metadata workflow checks
public software metadata. Source changes are available in the
[repository history](https://github.com/osinfra-interoperability/interop-trace/commits/).
