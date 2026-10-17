# Developer guide

## Architecture

The project metadata describes its public functions, interfaces, quality tools,
and collaboration policy. Keep implementation code and tests in clearly owned
locations, and keep generated public files synchronized with that metadata.

## Development setup

```bash
poetry install --all-extras
```

## Local checks

| Check | Command |
| --- | --- |
| Format | `poetry run ruff format --check .` |
| Lint | `poetry run ruff check .` |
| Type check | `poetry run mypy src` |
| Tests | `poetry run python -m pytest` |

See `CONTRIBUTING.md` in the repository root for the complete contribution policy.

## Package layout

The Python package uses a `src` layout:

```text
src/interop_trace/
    __init__.py   # Package version metadata
    __main__.py   # Module entry point
    cli.py        # Shared command-line application
tests/
    test_system.py  # Module entry-point help check
```

The installed command and module entry point both call `cli.main`.

## Generated automation

- `docs.yml`
- `metadata.yml`
- `quality.yml`
- `tests.yml`
