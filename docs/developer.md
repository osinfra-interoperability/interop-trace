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
    datasets/     # Dataset and DatasetProvider
    databases/    # Database and DatabaseProvider
    workflows/    # Workflow and WorkflowResult
    evaluation/   # Benchmark and EvaluationResult
tests/
    test_system.py  # Module entry-point help check
```

The installed command and module entry point both call `cli.main`.

## Component contracts

Each domain package defines its protocol and data record in `base.py` and exports
both from `__init__.py`. They use only the Python standard library.

| Protocol | Method | Returns |
| --- | --- | --- |
| `DatasetProvider` | `prepare(output_dir=...)` | Measurement paths and optional sample metadata |
| `DatabaseProvider` | `prepare(output_dir=...)` | A protein FASTA path |
| `Workflow` | `run(dataset, database, output_dir=...)` | Native output format and named file paths |
| `Benchmark` | `evaluate(result, dataset, database, output_dir=...)` | Named metrics and optional report paths for one run |

The protocols describe configured components: source selection, software versions,
analysis settings and benchmark expectations belong to each implementation.
There is no shared parameter dictionary or parameter schema.

Providers return existing absolute paths. Workflows preserve their native output
formats; benchmarks must understand those formats and the experimental design.
The dataset and database passed to a benchmark must be the inputs for that run.
Benchmark expectations are distinct from the sequence database's candidate proteins.

These are typed interfaces and data records, not working providers or analysis
implementations. The dataclasses do not read files or perform runtime validation.
Their fields cannot be reassigned, but contained mappings are not deeply immutable.
Implementations are responsible for checking inputs and raising exceptions on
failure; satisfying a Python protocol alone does not establish scientific validity.

## Generated automation

- `docs.yml`
- `metadata.yml`
- `quality.yml`
- `tests.yml`
