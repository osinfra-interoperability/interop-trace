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
| Catalogue | `poetry run python scripts/update_component_tables.py --check` |

See `CONTRIBUTING.md` in the repository root for the complete contribution policy.

## Package layout

The Python package uses a `src` layout:

```text
src/interop_trace/
    __init__.py   # Package version metadata
    __main__.py   # Module entry point
    cli.py        # Shared command-line application
    downloads.py  # Managed download storage and registry
    components.py # Optional setup protocol and shared registry implementation
    registries.py # Layer registry collection
    datasets/     # Dataset, DatasetProvider and PrideProvider
    databases/    # Database and DatabaseProvider
    workflows/    # Workflow and WorkflowResult
    evaluation/   # Benchmark, EvaluationResult and ProteoBenchDDA
    experiments/  # YAML loading and sequential execution
tests/
    test_system.py  # Module entry-point help check
    test_sage.py    # Sage subprocess behaviour using a local test executable
    test_sage_download.py # Sage release selection, reuse and extraction
    conftest.py     # Offline HTTP transport; Pooch and Requests still run normally
    test_uniprot.py # UniProt queries and release records using offline responses
    test_pride.py   # PRIDE selection, source records, reuse and failures
    test_proteobench.py # Installed ProteoBench scoring on tiny Sage-format tables
    test_downloads.py # HTTP metadata, cache reuse, failure cleanup and deletion scope
    test_cache_cli.py # Cache inspection and clearing commands
    test_components.py # Setup contract, registration and construction
    test_experiment_config.py # YAML structure, references and path resolution
    test_experiment_runner.py # Offline orchestration, processes and failure records
    test_catalogue.py # Registry-driven tables and committed-document drift check
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
process wrapper uses the Python standard library.
`ProteoBenchDDA` implements local evaluation for Sage LFQ results from the six-run
Q Exactive DDA mixture. It uses the optional, pinned ProteoBench library's parser
and scoring functions directly. Imports are deferred until evaluation, so other
components work without this extra. The benchmark settings ship with ProteoBench
and are copied to each evaluation's reports; no separate reference download or
cache entry is needed. The adapter does not instantiate ProteoBench's web modules,
which would initialize leaderboard repositories.

Its tests exercise the installed scoring library with known intensity ratios,
deliberate bias, missing observations and incompatible inputs. They require the
`proteobench` extra and are skipped without it; development and CI install all
extras. Synthetic tables test the integration, rather than establish performance
on the published measurements. No measurement downloads are needed for tests.

## Component setup and registration

`RequiresSetup` is an optional, runtime-checkable protocol shared across layers.
Its `setup(cache=...)` method resolves external resources through the supplied
`DownloadCache`. Components own their setup behavior; the registry does not store
a separate setup callback. Construction and registration never download.

PRIDE and UniProt keep resolved download records after setup. Their `prepare`
methods only return paths and write provenance. Sage resolves a pinned release or
provided executable during setup; `run` performs no installation. These methods
raise if setup has not completed. Repeating setup consults the shared cache; after
clearing the cache, set up existing objects again. ProteoBench does not implement
setup because its settings are bundled with the installed optional package.

Each domain package owns a `registry.py`. Implementations decorate their
constructors with `@registry.register(...)`, supplying a stable identifier, brief
summary, documentation link and any file-path parameter names. Its package
`__init__.py` explicitly imports implementations so their decorators run. Do not
scan directories or import optional scientific libraries eagerly.

To add an implementation, satisfy its domain protocol, implement setup if resources
are needed, decorate the constructor, import the implementation from its package
and document its parameters and scope. Registries construct components using native
constructor arguments; they do not define a common scientific parameter schema.

Regenerate the marked README and documentation tables after changing registrations:

```bash
poetry run python scripts/update_component_tables.py
```

The script defaults to its own checkout; `--root` selects another checkout.
It preserves all text outside the marker pairs. Tests check that committed tables
match the registrations. Table rendering and repository-file editing live in
`scripts/`; the installed application's `components` command only lists entries.

## Experiment execution

`load_configuration` uses PyYAML's safe constructors with duplicate-key rejection.
Reading component files and constructing experiments are separate functions.
Construction names the four fields explicitly and resolves each selected definition
through its typed registry. Instances are fresh for each experiment, before setup.
Component file paths resolve relative to their own files. Experiment choices and
original YAML contents are retained once in the run snapshot; no experiment data
is downloaded while loading.

`run_experiments` executes the optional setup methods and four domain operations
sequentially. It records timestamps, stages and statuses and stops on the first
failure, preserving partial output. Dataset, database and native workflow records
are retained as each stage completes in that experiment's `experiment.json`.
The root `configuration.json` holds the original files and experiment choices;
there is no additional batch status ledger or copied settings per experiment.
Later experiments have no output directory. Runs use new output directories and
share only download storage. The four execution calls appear together in
`_run_experiment`; a small context manager records completion or failure and
re-raises errors, including interruptions.

The offline integration test exercises actual provider setup, Pooch extraction,
a local subprocess emitting synthetic Sage LFQ output and the installed
ProteoBench scorer. It is an orchestration check, not a full scientific reference
experiment or an input-format conversion test.

## Data records

The data records do not read files or perform runtime validation.
Their fields cannot be reassigned, but contained mappings are not deeply immutable.
Implementations are responsible for checking inputs and raising exceptions on
failure; satisfying a Python protocol alone does not establish scientific validity.

## Download storage

`DownloadCache` is shared infrastructure, independent of the four domain protocols.
Components explicitly call `fetch(url, name=..., kind=..., metadata=...,
metadata_headers=...)` during setup.
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
Use clearing between runs. Per-experiment metadata is stored separately by the provider.

## Generated automation

- `docs.yml`
- `metadata.yml`
- `quality.yml`
- `tests.yml`
