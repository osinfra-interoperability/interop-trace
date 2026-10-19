# Configure experiments

Experiment YAML files live directly in `experiments/`. Each file can contain
one or several experiments; files organize related work, while IDs select what
to execute. Component YAML files hold reusable settings:

```text
experiments/
  simple.yaml
  components/
    datasets.yaml
    databases.yaml
    workflows.yaml
    benchmarks.yaml
  settings/
    sage/
      erwinia_tmt.json
```

`simple.yaml` selects profiles from the shared component files:

```yaml
components:
  datasets: components/datasets.yaml
  databases: components/databases.yaml
  workflows: components/workflows.yaml
  benchmarks: components/benchmarks.yaml

experiments:
  - id: erwinia_sage
    dataset: erwinia_tmt
    database: erwinia_and_spikes
    workflow: sage_erwinia_tmt
    benchmark: erwinia_spike_peptides
```

Profile names identify a particular set of settings; `type` selects the registered
implementation. For example, `sage_erwinia_tmt` uses `type: sage`. Add another named
profile for different search settings, then reference it from experiments in any
file. Shared profiles are edited once and reused without copying files.

Each component definition has a registered `type` and implementation-specific
`parameters`. For example, the database file contains:

```yaml
erwinia_and_spikes:
  type: uniprot
  parameters:
    query: >-
      (organism_id:218491) OR (accession:P00924) OR (accession:P02769)
      OR (accession:P00489) OR (accession:P62894)
    format: fasta
```

Use the [catalogue](components.md) for parameters. Workflow search settings stay
in the workflow's native configuration, such as Sage JSON. File paths resolve
relative to the YAML file declaring them, including paths in component parameters.

Each experiment selects **one** dataset, database, workflow and benchmark.
A dataset can contain several measurements. Evaluation is a required step;
missing or null benchmark selections are rejected before downloads or execution.

## Run and inspect

```bash
poetry run interop-trace experiments
poetry run interop-trace run erwinia_sage --check
poetry run interop-trace run erwinia_sage --output results/run-001
poetry run interop-trace run --all --check
```

Pass several IDs after `run` to combine experiments from different files. IDs
must be unique across all files; unknown or repeated selections are rejected.
Use `--all` to run every discovered experiment, including any large reference
experiments you have added. Provide IDs or `--all`, never both.

Discovery reads only immediate `*.yaml` and `*.yml` files, in filename order.
It does not descend into `components/` or `settings/`. For another collection,
pass `--directory /path/to/experiments` to `run` or `experiments`.

The complete catalogue is validated before selection. `--check` validates YAML,
names and constructor parameters without downloads, remote availability checks,
native-tool validation or importing optional scorers.

The runner executes the selected experiments sequentially, in CLI argument order.
For `--all`, it uses filename order and each file's experiment order. Downloads
are shared; workflow results are separate.
Choose combinations whose data and result formats suit their consumers; there is
no automatic format conversion or expansion into every possible combination.

The new output directory contains `configuration.json` with selected IDs,
source paths and the original experiment/component YAML contents. Only files
referenced by the selection are included; source YAML can also contain unselected
experiments. Each experiment has an `experiment.json` recording stages, timestamps,
status and artifact paths. Provider reports record original download provenance;
workflow outputs preserve native settings and logs. Each evaluated run includes
metrics and report paths.

If an experiment fails, its remaining stages are skipped and the next experiment
starts. Its `experiment.json` keeps the failed stage and error; logs and partial
outputs remain available. After the batch, the CLI lists successes and failures,
saves their IDs and errors in run-level `summary.json`, and exits with code `1`
if any experiment failed (`0` otherwise).

Invalid run configuration stops execution before experiments start. `Ctrl+C`
stops the batch and preserves the interrupted experiment's failure record; later
experiments do not start and no final batch summary is written.
Use a new output directory to rerun; cached downloads remain reusable.
Execution status and benchmark quality are separate: completed evaluation can
report poor recovery.
