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
    datasets/     # Dataset, DatasetProvider and PrideProvider
    databases/    # Database and DatabaseProvider
    workflows/    # Workflow and WorkflowResult
    evaluation/   # Benchmark and EvaluationResult
tests/
    test_system.py  # Module entry-point help check
    test_sage.py    # Sage subprocess behaviour using a local test executable
    test_sage_download.py # Sage release selection, reuse and extraction
    conftest.py     # Offline HTTP transport; Pooch and Requests still run normally
    test_uniprot.py # UniProt queries and release records using offline responses
    test_pride.py   # PRIDE selection, source records, reuse and failures
    test_downloads.py # HTTP metadata, cache reuse, failure cleanup and deletion scope
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

The contracts are typed interfaces and data records. `PrideProvider` retrieves
selected public dataset files and records their source metadata. `UniProtProvider`
retrieves cached database files and records the original source release.
`SageWorkflow` is a concrete local workflow implementation. Download storage uses Pooch; the Sage
wrapper uses the Python standard library.
The data records do not read files or perform runtime validation.
Their fields cannot be reassigned, but contained mappings are not deeply immutable.
Implementations are responsible for checking inputs and raising exceptions on
failure; satisfying a Python protocol alone does not establish scientific validity.

## Download storage

`DownloadCache` is shared infrastructure, independent of the four domain protocols.
Components explicitly call `fetch(url, name=..., kind=..., metadata=...,
metadata_headers=...)`.
It reuses a completed file and its original provenance, or downloads and registers
a new response. HTTP transfers use Pooch with a 60-second timeout and the
`interop-trace` user agent.

| Argument | Purpose |
| --- | --- |
| `name` | Component name, such as `sage` or `uniprot` |
| `kind` | Component type, such as `workflow` or `database` |
| `filename` | Local basename for a new download; defaults to `content` |
| `metadata` | Known source information, such as Sage's requested release version |
| `metadata_headers` | Mapping from record fields to response header names, such as `release` to `X-UniProt-Release` |

Selected headers are captured during the same GET request through a response hook.
Redirects use the final response's headers. Missing headers become `None`; mapped
headers take precedence over literal metadata for matching fields. Metadata is
registered only after the content has downloaded successfully. Cache hits retain
the original metadata even if the caller supplies different values.
Name and kind are stored separately from source metadata. Older records gain
missing labels on reuse; existing labels, source versions and download times are
preserved. The cache listing displays kind as `type` and uses `unknown` for missing
labels.

`download_sage(version, cache_dir=...)` uses the same cache for a pinned GitHub
release archive. Pooch handles HTTP transfers and archive extraction. Extracted
files live beside the archive under `extracted/`, so the same clear command removes
both. Missing extracted files are restored without downloading the archive again.
The helper returns a path for the existing `SageWorkflow` interface; manual
executable paths remain supported. The cache records the requested release tag,
while `version.txt` in each workflow run records the executable's own version string.

Each exact URL has its own directory under `objects/`, containing the payload and
`download.json`. PRIDE measurements retain their filenames and extensions; the
project catalogue uses `files.json`. Existing Sage and UniProt payloads use
`content`. Cache reuse retains the original stored filename. The directory key is
a hash of the request URL, not a checksum of file contents. Metadata records the
source, path, size, download time and reported
version. The registry record is written after a successful transfer.
Missing or size-changed files and unreadable records are treated as cache misses.

[Pooch](https://www.fatiando.org/pooch/latest/api/generated/pooch.retrieve.html)
handles temporary files, transfer completion and cleanup after transfer failures.
A shared HTTP downloader captures selected response headers and rejects empty
files. The wrapper keeps the JSON registry, presence and size checks, and
cache ownership marker. Retrieval uses `known_hash=None`; cached files are not
hashed on reuse. Reported PRIDE checksums are stored as source metadata without
verifying the payload against them.

Clearing removes the managed `objects/` directory and any `pending/` directory left
by the previous cache implementation. It requires the ownership marker. Recorded
paths are informational; they never control deletion of files outside the cache.
Use clearing between runs. Per-run metadata is stored separately by the provider.

## Generated automation

- `docs.yml`
- `metadata.yml`
- `quality.yml`
- `tests.yml`
