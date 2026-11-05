# CLI and downloads

From the repository root, with Python 3.12+ and Poetry installed:

```bash
poetry install
poetry run interop-trace --help
poetry run interop-trace components
poetry run interop-trace experiments
```

See [the first experiment](first-experiment.md) for a worked example and
[configuration](experiments.md) for YAML syntax.

## Run and assess

```bash
poetry run interop-trace run erwinia_sage --output results/run-001
poetry run interop-trace classify results/run-001
```

Pass several experiment IDs to `run`, or `--all` for every configured experiment.
Each run needs a new output directory. Downloads are shared; workflow outputs
are kept separately for each experiment.

An experiment error skips its remaining stages and execution continues with the
next experiment. Logs and partial outputs are preserved. Execution exits with
code `1` if any experiment records an error. Invalid configuration and `Ctrl+C`
stop the batch; interruption preserves evidence but produces no final summary.

## Separate run stages

Create a run without downloads or execution, then execute its saved selection:

```bash
poetry run interop-trace run erwinia_sage --prepare-only --output results/run-002
poetry run interop-trace execute results/run-002
poetry run interop-trace classify results/run-002
```

Without `--prepare-only`, `run` creates and executes in one command. A created
run executes once, using its saved YAML. The same stages are available in the
[local interface](interface.md).

## Assessment results

`classify` reads saved records without rerunning tools. It accepts a run directory
or one finished experiment directory, and saves `classification.json`:

| Outcome | Meaning |
| --- | --- |
| `success` | All declared acceptance criteria passed |
| `failure` | A recorded error or an unmet acceptance criterion |
| `unknown` | Interrupted execution, no criteria or unavailable required metrics |

Recorded errors take precedence over metric checks. A definite failed criterion
takes precedence over an unavailable metric. Success means meeting the configured
criteria, not general scientific accuracy; its failure category is `null`.
Execution status (`not_started`, `running`, `finished`) describes lifecycle only.

Assessments include the applied rule, evidence, criterion bounds and observed
values. `detected_stage` identifies where an error surfaced, or `assessment` for
an unmet criterion. Diagnosis currently leaves the originating stage unknown;
logs are not interpreted and no external services are called.

Existing assessments and execution records are preserved. Use a new run after
changing criteria. Exit code `0` from `classify` means the command completed,
regardless of the recorded assessment outcome.

## Download cache

Downloads are reused from `.interop_trace/cache/`:

```bash
poetry run interop-trace cache list
poetry run interop-trace cache clear
```

Clearing asks for confirmation; add `--yes` for scripts. Clear between runs.
This removes cached inputs and tools while preserving run outputs and provenance.
Reuse checks URL, presence and size, not checksums or source updates. A fresh
UniProt query can return another release; archive required cached resources for
exact long-term reproduction.

Use `run --cache-directory /path/to/cache` for another dedicated cache, and
`cache list --directory /path/to/cache` or `cache clear --directory /path/to/cache`
to manage it. See [saved evidence](first-experiment.md#saved-evidence) for run files.
