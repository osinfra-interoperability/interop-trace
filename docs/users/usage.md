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
poetry run interop-trace metadata collect results/run-002
poetry run interop-trace predict results/run-002
poetry run interop-trace execute results/run-002
poetry run interop-trace classify results/run-002
```

Without `--prepare-only`, `run` creates and executes in one command. A created
run executes once, using its saved YAML. The same stages are available in the
[local interface](interface.md).

## Metadata predictions

`predict` saves each experiment's `prediction.json` before execution, using only
collected public descriptions and the current host snapshot in
`prediction_environment.json`. It neither runs tools nor reads their results.
Metadata collection and prediction can be skipped when just executing a run.

Two checks compare advertised workflow OS support and declared producer outputs
against workflow inputs. Interface matching requires exact data URIs and
overlapping format URIs, one function per entry and distinct workflow inputs.
Broad portal descriptions do not identify the selected file exports.

- `support`: all applicable checks agree.
- `conflict`: at least one populated declaration disagrees under these rules.
- `unknown`: insufficient or ambiguous declarations prevent a conclusion.

Populated declarations are treated as allowed alternatives. A conflict can reflect
incomplete metadata; support covers only these checks. Missing declarations stay
unknown. Clearly remote-only workflows exclude the local OS check.
`evidence_coverage` is the fraction of applicable checks that could be evaluated,
**not confidence or a probability**. `failure_probability` stays `null`.
Conclusions do not block execution; exit code `0` means predictions were saved.

Predictions retain reasons, consulted fields and snapshot references. Architecture,
runtime requirements, ontology relationships, conversions and scientific accuracy
are not checked. PRIDE/UniProt portal entries currently leave the input-interface
check unknown. Predictions are never overwritten; create a new run to repeat them.

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

## Public metadata

Collect the references saved with a created run, before or after execution:

```bash
poetry run interop-trace metadata collect results/run-002
```

This saves `metadata/index.json`, linking experiment roles and profiles to
snapshots under `metadata/biotools/<entry-id>/`. Shared IDs use one snapshot.
Collection also queries the [OLS API](https://www.ebi.ac.uk/ols4/api-docs) for the
EDAM data/format terms appearing in these descriptions. Only the relevant JSON
responses and ontology version information are saved under `metadata/edam/`;
the full ontology is not downloaded. The index records request URLs and original
retrieval times. Responses are cached by URL, so clearing the cache is required
to collect fresh descriptions. Saved responses, rather than a pinned release,
provide the evidence used for reproduction.
The index distinguishes `collected`, `missing_reference`, `not_found` (HTTP 404)
and `retrieval_failed`, retaining error details. Other entries are still collected
after a retrieval failure; the command then exits with code `1`. Collection leaves
execution and assessment records unchanged. Existing metadata is never overwritten.

For an individual bio.tools entry:

```bash
poetry run interop-trace metadata biotools Sage-proteomics --output results/metadata-sage-001
```

Use the exact entry ID: `Sage-proteomics` is the proteomics engine; `sage` is a
different resource. Each new folder contains the response as indented JSON in
`entry.json`, preserving its fields and values, and its source URL, ID and original
retrieval time in `source.json`.
Snapshots survive cache cleanup. Cached entries are reused without checking for
updates, retaining their original retrieval time. Use `--cache-directory` for a
dedicated metadata cache that can be cleared independently of tool/input downloads.

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
