# CLI and downloads

Install from a source checkout with Python 3.12+ and Poetry:

```bash
poetry install
poetry run interop-trace --help
poetry run interop-trace components
poetry run interop-trace experiments
```

Start with [the first experiment](first-experiment.md), then use
[configuration](experiments.md) for other combinations.
`poetry run python -m interop_trace` exposes the same CLI.

## Separate run stages

Create a run without downloads or execution, then execute its saved selection:

```bash
poetry run interop-trace run erwinia_sage --prepare-only --output results/my-run
poetry run interop-trace execute results/my-run
poetry run interop-trace classify results/my-run
```

Without `--prepare-only`, `run` creates and executes in one command as before.
Execution uses the saved YAML and can start only once per run. Environment
information is collected at execution time. `experiments.csv` records the same
experiment table as the [UI](interface.md).

`classify` accepts a run directory or a single finished experiment directory.
It saves `classification.json` for finished experiments, including those without
exceptions, and skips existing assessments when processing a run. The assessor
uses deterministic rules on the recorded error:

| Evidence | Outcome | Category |
| --- | --- | --- |
| Permission error | `failure` | `permission` |
| Executable architecture/format error (`EBADARCH` or `ENOEXEC`) | `failure` | `environment` |
| Nonzero subprocess exit | `failure` | `process_error` |
| Other recorded error | `failure` | `unknown` |
| Interruption or no recorded error | `unknown` | `unknown` |

Each assessment saves method `deterministic`, the rule identifier and evidence
references to fields in `experiment.json`. Categories describe observed errors, not
proven underlying causes or inherent component incompatibility. Logs are not
interpreted and no external services are called. Original records remain
unchanged. Exit code `0` means the command completed, not scientific success.

Assessment values use string enums: `AssessmentOutcome` defines `success`,
`failure` and `unknown`; `AssessmentCategory` defines the categories above.
An assessment outcome is separate from execution status: completing execution
does not establish scientific success.

## Download cache

From the repository root, components reuse downloads in `.interop_trace/cache/`.
They record the source URL, name, type, byte count, retrieval time and available
release metadata. Inspect or clear downloads with:

```bash
poetry run interop-trace cache list
poetry run interop-trace cache clear
```

Clearing asks for confirmation; add `--yes` for scripts. Clear **between runs**:
experiment records refer to cached input files. Clearing preserves experiment
outputs and their provenance records, but removes the underlying cached inputs
and downloaded Sage installation.

Matching URLs reuse files if their presence and size agree with the record.
Reuse does not verify checksums or check for source updates. A live UniProt query
can return a different release after clearing; recorded versions identify the
stored response, not a permanently pinned source. Archive needed inputs separately
when exact long-term reproduction matters.

For a different dedicated cache, use the same directory for execution and inspection:

```bash
poetry run interop-trace run erwinia_sage --output results/run-002 --cache-directory /path/to/cache
poetry run interop-trace cache list --directory /path/to/cache
poetry run interop-trace cache clear --directory /path/to/cache
```

The cache uses Pooch for transfers and extraction. An ownership marker protects
unrelated nonempty directories from being used or cleared as caches.

For direct Python use, see the [API reference](../developers/reference.md). The experiment
runner coordinates component setup automatically.
