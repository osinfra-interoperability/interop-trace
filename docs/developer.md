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
    downloads.py  # Managed download storage and registry
    datasets/     # Dataset and DatasetProvider
    databases/    # Database and DatabaseProvider
    workflows/    # Workflow and WorkflowResult
    evaluation/   # Benchmark and EvaluationResult
tests/
    test_system.py  # Module entry-point help check
    test_sage.py    # Sage subprocess behaviour using a local test executable
    test_uniprot.py # UniProt download behaviour using offline responses
    test_downloads.py # Cache reuse, failure cleanup and deletion scope
    test_cache_cli.py # Cache inspection and clearing commands
```

The installed command and module entry point both call `cli.main`.

## Component contracts

Each domain package defines its protocol and data record in `base.py` and exports
both from `__init__.py`. They use only the Python standard library.

| Protocol | Method | Returns |
| --- | --- | --- |
| `DatasetProvider` | `prepare(output_dir=...)` | Measurement paths and optional sample metadata |
| `DatabaseProvider` | `prepare(output_dir=...)` | A database path and its format identifier |
| `Workflow` | `run(dataset, database, output_dir=...)` | Native output format and named file paths |
| `Benchmark` | `evaluate(result, dataset, database, output_dir=...)` | Named metrics and optional report paths for one run |

The protocols describe configured components: source selection, software versions,
analysis settings and benchmark expectations belong to each implementation.
There is no shared parameter dictionary or parameter schema.

Providers return existing absolute paths. Database formats are explicit, for
example `fasta` or `uniprot_xml`; consumers decide how to handle them. The record
performs no conversion. `SageWorkflow` delegates input interpretation to Sage
without checking declared formats or file extensions.
Workflows preserve their native output formats; benchmarks must understand those
formats and the experimental design.
The dataset and database passed to a benchmark must be the inputs for that run.
Benchmark expectations are distinct from the sequence database's candidate proteins.

The contracts are typed interfaces and data records. `UniProtProvider` retrieves
cached database files and records the original source release. `SageWorkflow` is a
concrete local workflow implementation. Both use the Python standard library.
The data records do not read files or perform runtime validation.
Their fields cannot be reassigned, but contained mappings are not deeply immutable.
Implementations are responsible for checking inputs and raising exceptions on
failure; satisfying a Python protocol alone does not establish scientific validity.

## Download storage

`DownloadCache` is shared infrastructure, independent of the four domain protocols.
`fetch(url, downloader)` reuses a completed file or calls the supplied downloader
with the URL and a staging path. The downloader writes the bytes and returns source
metadata such as a release or software version. This keeps source-specific HTTP
handling in the provider.

Each exact URL has its own directory under `objects/`, containing `content` and
`download.json`. The directory key is a hash of the request URL, not a checksum of
file contents. Metadata records the source, path, size, download time and reported
version. Files and metadata are published together after a successful transfer.
Missing or size-changed files and unreadable records are treated as cache misses.

The cache uses JSON records and the standard library. Clearing removes its managed
`objects/` and `pending/` directories and requires the ownership marker. Recorded
paths are informational; they never control deletion of files outside the cache.
Use clearing between runs. Per-run metadata is stored separately by the provider.

## Generated automation

- `docs.yml`
- `metadata.yml`
- `quality.yml`
- `tests.yml`
