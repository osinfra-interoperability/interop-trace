# Development guide

Keep changes small and preserve evidence of interoperability outcomes. Components
own their native settings and input interpretation; orchestration and assessment
stay outside their implementations.

## Setup and checks

```bash
poetry install --all-extras
poetry run pre-commit install
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy src
poetry run python -m pytest
poetry run zensical build --strict
```

Tests run offline with controlled HTTP responses and local subprocess fixtures.
Optional ProteoBench tests exercise its installed scorer on synthetic tables;
UI tests use NiceGUI's user simulation. They validate software behavior, not
scientific accuracy. See [CONTRIBUTING.md](https://github.com/osinfra-interoperability/interop-trace/blob/main/CONTRIBUTING.md)
for branch, commit and review policy.

## Component boundaries

Each domain package defines its protocol in `base.py`, registrations in
`registry.py`, and implementation exports in `__init__.py`.

| Package | Contract | Responsibility |
| --- | --- | --- |
| `datasets` | `DatasetProvider.prepare` | Measurement paths and optional sample metadata |
| `databases` | `DatabaseProvider.prepare` | Database path and native format identifier |
| `workflows` | `Workflow.run` | Consume inputs and preserve native outputs |
| `evaluation` | `Benchmark.evaluate` | Metrics and reports against reference expectations |

`components.py` provides typed registries and the optional `RequiresSetup`
protocol. Constructors and registration never download. Components needing
external resources implement `setup(cache=...)`, using `DownloadCache.fetch` from
`downloads.py` for shared transfers and provenance.

Consumers interpret supplied records and enforce their own requirements.
`errors.py` provides descriptive exceptions for existing boundary checks. Use
`add_note()` for observed context and `raise ... from error` when translating an
exception. Report facts about inputs, rather than diagnosing another component's
implementation. Search databases supply candidates, not benchmark ground truth.

## Runs and assessment

`experiments/config.py` validates YAML, resolves profiles and checks numeric
acceptance bounds. `catalogue.py` discovers root-level YAML files and selects
globally unique IDs. Every experiment gets fresh component instances.

- `create_run` saves selected YAML, criteria and initial records without setup.
- `execute_run` uses that snapshot once, records the platform, then performs
  setup, input preparation, workflow execution and evaluation sequentially.
  Ordinary experiment errors preserve evidence and allow the batch to continue;
  invalid configuration and interruptions stop execution.
- `classification.py` reads saved errors and metrics, applies acceptance criteria
  and writes assessments without changing execution records. Its diagnostic
  placeholder leaves the originating stage unknown.

`run_experiments` combines creation and execution. `experiments/records.py`
projects saved JSON into the UI table and `experiments.csv`; JSON records hold
full evidence. The CLI and optional NiceGUI interface share this orchestration.
`interfaces/web/runs.py` launches the CLI and reads outputs without importing
NiceGUI. Core packages never import interfaces.

Unmet acceptance criteria are assessment outcomes, not execution exceptions.
Metric meanings belong to their benchmark; criteria refer to metric names without
inspecting implementations. Passing criteria does not establish general scientific
validity. See [assessment behavior](../users/usage.md#assessment-results).

## Add a component

1. Implement the relevant protocol and keep native settings as constructor
   arguments. Add `setup(cache=...)` only for external resources.
2. Register the implementation with `@registry.register`, including its name,
   summary, documentation anchor and any path parameters.
3. Export it from the package's `__init__.py`. Keep optional scientific imports
   inside execution so catalogue listing stays lightweight.
4. Document parameters and scope in [components](../users/components.md), and test
   meaningful success/failure boundaries without network downloads.

New implementations normally need no runner changes. Pre-commit updates the
component tables; review and stage any generated changes before retrying a commit.
See [documentation maintenance](documentation.md) for table generation and CI,
and the [API reference](reference.md) for signatures.
