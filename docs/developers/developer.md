# Development guide

Keep each change small and preserve evidence needed to explain interoperability
outcomes. Implementations own their scientific settings and format interpretation;
the runner coordinates their execution.

## Setup and checks

```bash
poetry install --all-extras
poetry run pre-commit install
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy src
poetry run python -m pytest
poetry run python scripts/update_component_tables.py --check
poetry run zensical build --strict
```

Tests run offline with controlled HTTP responses and local subprocess fixtures.
ProteoBench tests exercise the installed scoring library on synthetic tables; they
skip without the extra. These tests validate adapters, not scientific performance
on the published reference measurements. The [first experiment](../users/first-experiment.md)
is the separate real-data integration example.

See [CONTRIBUTING.md](https://github.com/osinfra-interoperability/interop-trace/blob/main/CONTRIBUTING.md)
for branch, commit and review policy.

## Boundaries

Each domain package has contracts in `base.py`, a registry in `registry.py`, and
explicit implementation exports in `__init__.py`.

| Package | Contract | Responsibility |
| --- | --- | --- |
| `datasets` | `DatasetProvider.prepare` | Return measurement paths and optional sample metadata |
| `databases` | `DatabaseProvider.prepare` | Return a database path and native format identifier |
| `workflows` | `Workflow.run` | Consume inputs and preserve native result files |
| `evaluation` | `Benchmark.evaluate` | Score results against explicit reference expectations |

`components.py` provides `Registry` and the optional `RequiresSetup` protocol.
Components needing external resources implement `setup(cache=...)`; constructors
and registration never download. Preparation/execution raises if required setup
has not completed. Repeat setup after clearing cached resources.

`downloads.py` provides shared Pooch transfers, extraction support and provenance
records. Reuse is based on URL, file presence and size, not content checksums.
Components supply their name, kind and source metadata when fetching.

`experiments/config.py` loads safe YAML, rejects duplicate keys and resolves
references through typed registries. Each experiment gets fresh component instances.
`experiments/runner.py` performs setup, dataset/database preparation, workflow and
evaluation sequentially. It records stages and re-raises failures,
including interruptions. Later experiments do not start after a failure.
`interfaces/cli.py` exposes this orchestration and cache commands.

`interface.py` adds an optional NiceGUI page. `run_browser.py` launches the same CLI
in a subprocess and reads existing output records; it has no NiceGUI dependency.
One launcher is shared by browser tabs, while each tab owns its selections.
There is no separate execution or scoring implementation in the UI. Interaction
tests use NiceGUI's browserless user simulation and controlled subprocess responses;
they skip without the `ui` extra.

Records carry native formats and paths; they do not convert or inspect files.
Consumers interpret them. Sage delegates input compatibility to its executable;
benchmarks enforce the result schema and reference design they require.
Search databases contain candidates; benchmark expectations come from independent
references. Do not infer scientific validity from protocol conformance or exit codes.

## Add a component

1. Implement the appropriate protocol in its domain package. Keep native settings
   as constructor arguments; there is no universal scientific parameter schema.
2. Add `setup(cache=...)` only if external resources are needed. Reuse
   `DownloadCache.fetch` rather than introducing another downloader.
3. Decorate the constructor with `@registry.register`, declaring its name, summary,
   documentation anchor and any path parameters. Paths are resolved relative to
   the component YAML file.
4. Import/export the implementation in its package's `__init__.py`. Keep optional
   scientific imports inside execution; listing components must remain lightweight.
5. Document parameters and scope in [components](../users/components.md), and test meaningful
   success/failure boundaries without network downloads.

The runner uses the protocols, so a new implementation normally needs no runner
changes. Benchmark metrics have implementation-specific meanings and are not
implicitly comparable between evaluators. See the [API](reference.md) for signatures.

## Generated component tables

```bash
poetry run python scripts/update_component_tables.py
```

The script updates only marked README/catalogue sections from the registries.
The pre-commit hook runs it automatically; if files change, review and stage them,
then retry the commit. Poetry must be on `PATH` for local hooks.
Tests reject stale committed tables. Documentation CI generates tables before
building, without bot commits; see [documentation builds](documentation.md).
