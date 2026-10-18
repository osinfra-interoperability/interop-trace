# Configure experiments

Reusable component YAML files hold implementation settings. A run YAML file
selects named definitions. Start with `experiments/simple/` in the repository.

```yaml
components:
  datasets: components/datasets.yaml
  databases: components/databases.yaml
  workflows: components/workflows.yaml
  benchmarks: components/benchmarks.yaml

experiments:
  - id: vat1_sage
    dataset: vat1_spectrum
    database: vat1
    workflow: sage
    benchmark: vat1_peptide
```

Each component definition has a registered `type` and implementation-specific
`parameters`. For example, the database file contains:

```yaml
vat1:
  type: uniprot
  parameters:
    query: accession:Q99536
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
poetry run interop-trace run experiments/simple/run.yaml --check
poetry run interop-trace run experiments/simple/run.yaml --output results/run-001
```

`--check` validates YAML, names and constructor parameters. It does not download,
check remote availability, validate native tool settings or load optional scorers.

Append explicit entries with unique `id` values to run multiple combinations.
The runner constructs all selected components before setup, then executes
experiments sequentially. Downloads are shared; workflow results are separate.
Choose combinations whose data and result formats suit their consumers; there is
no automatic format conversion or expansion into every possible combination.

The new output directory contains `configuration.json` with the original YAML
contents. Each experiment has an `experiment.json` recording stages, timestamps,
status and artifact paths. Provider reports record original download provenance;
workflow outputs preserve native settings and logs. Each evaluated run includes metrics and report paths.

On failure, the CLI exits nonzero and records the failed stage. Partial outputs
remain available and later experiments do not start. Use a new output directory
to rerun; cached downloads remain reusable. Execution status and benchmark quality
are separate: completed evaluation can report poor recovery.
