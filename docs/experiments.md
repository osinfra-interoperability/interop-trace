# Configured experiments

A run selects explicit combinations of reusable component settings. Each
experiment has one dataset, one database, one workflow and one benchmark.
Experiments execute sequentially; the first failure stops the run.

## Define reusable components

Create your configuration files outside the Python package, for example:

```text
experiments/
    components/
        datasets.yaml
        databases.yaml
        workflows.yaml
        benchmarks.yaml
    settings/
        sage_lfq.json
    first.yaml
```

Each component file maps your own names to a registered `type` and its optional
`parameters`. List available implementations with:

```bash
poetry run interop-trace components
```

The examples below describe the configuration structure. The dataset project must
be replaced with a public source containing the required mzML files. They are not
a ready-to-run download of the complete reference experiment.

`components/datasets.yaml`:

```yaml
reference:
  type: pride
  parameters:
    project: REPLACE_WITH_PROJECT_CONTAINING_REFERENCE_MZML_FILES
    files:
      - LFQ_Orbitrap_DDA_Condition_A_Sample_Alpha_01.mzML
      - LFQ_Orbitrap_DDA_Condition_A_Sample_Alpha_02.mzML
      - LFQ_Orbitrap_DDA_Condition_A_Sample_Alpha_03.mzML
      - LFQ_Orbitrap_DDA_Condition_B_Sample_Alpha_01.mzML
      - LFQ_Orbitrap_DDA_Condition_B_Sample_Alpha_02.mzML
      - LFQ_Orbitrap_DDA_Condition_B_Sample_Alpha_03.mzML
```

PRIDE's original PXD028735 catalogue lists the reference measurements as `.raw`.
Sage requires converted inputs; the current runner does not provide RAW-to-mzML
conversion or a local dataset provider. Selecting RAW files does not make them
Sage-compatible, and changing their extensions is not conversion. Direct Python
use can supply existing converted files through `Dataset(files=...)`.

`components/databases.yaml`:

```yaml
mixed_species:
  type: uniprot
  parameters:
    query: "reviewed:true AND (organism_id:9606 OR organism_id:559292 OR organism_id:83333)"
    format: fasta
```

This selects reviewed human, yeast and E. coli K-12 entries as search candidates.
Choose the query to match the experiment's database comparison. The benchmark's
expected sample proportions are defined separately from this query.

`components/workflows.yaml`:

```yaml
sage_lfq:
  type: sage
  parameters:
    version: "0.14.7"
    configuration: ../settings/sage_lfq.json
    threads: 2
```

`sage_lfq.json` is a native Sage configuration, including the usual search settings
and the [required LFQ settings](usage.md#evaluate-sage-quantification-with-proteobench).
Scientific workflow parameters retain their native format.

`components/benchmarks.yaml`:

```yaml
quantification:
  type: proteobench_dda
  parameters:
    min_observations: 3
```

See the [component catalogue](components.md) for parameter meanings and scope.

## Select experiments

`first.yaml` references those four files and selects your named definitions:

```yaml
components:
  datasets: components/datasets.yaml
  databases: components/databases.yaml
  workflows: components/workflows.yaml
  benchmarks: components/benchmarks.yaml

experiments:
  - id: first_experiment
    dataset: reference
    database: mixed_species
    workflow: sage_lfq
    benchmark: quantification
```

Add entries to `experiments` to run further combinations. Add named definitions
to the component files to vary a database query, workflow configuration or
benchmark parameter. A definition name such as `mixed_species` identifies settings;
its `type`, `uniprot`, identifies the Python implementation. Definitions can be
referenced by different experiment files. There is no automatic combination matrix
or parameter override syntax.

File references resolve relative to the file containing them. This includes the
four component files and Sage's configuration/executable paths. Cache and output
CLI paths resolve relative to the working directory. Each layer currently references
one component file. IDs must be unique simple directory names starting with a letter
or digit. Duplicate YAML keys, unknown structural fields and invalid selected
component references raise errors.

## Validate and execute

Install the scoring extra for the current benchmark:

```bash
poetry install --extras proteobench
poetry run interop-trace run experiments/first.yaml --check
```

`--check` loads all referenced files and constructs the selected components. It
checks configuration structure, constructor settings and references without setup,
downloads or processes. It does not validate PRIDE file availability, inspect native
Sage settings, verify optional scoring dependencies or establish scientific validity.

When the chosen sources and native settings are ready, execute:

```bash
poetry run interop-trace run experiments/first.yaml --output results/run-001
```

The runner calls optional setup on the selected dataset, database, workflow and
benchmark, using one shared download cache. It then prepares dataset and database,
runs the workflow, and evaluates its result. Setup and execution failures propagate.
The current benchmark runs locally and does not submit results.

To select another dedicated cache location:

```bash
poetry run interop-trace run experiments/first.yaml --output results/run-002 --cache-directory /path/to/cache
```

## Inspect a run

```text
results/run-001/
    configuration.json
    first_experiment/
        experiment.json
        dataset/pride.json
        database/uniprot.json
        workflow/
        evaluation/
```

`configuration.json` preserves the loaded experiment/component YAML contents,
experiment choices, source paths, package version and cache location. Native
workflow outputs record effective scientific settings. Each `experiment.json`
records its timestamps, status, active stage, prepared paths and completed results.
Errors include their exception type and message. Settings are kept in the run's
configuration snapshot rather than copied into each execution record.

Every run requires a new output directory. Failed runs preserve partial outputs
and cached downloads; later experiments have no output directory. The configuration
snapshot lists all requested experiments, including those not started. Retry in a new
directory. There is no automatic resume or workflow-result cache. Experiments use
fresh component instances and separate workflow outputs, while downloads are reused
across the run and subsequent runs until the shared cache is cleared or files go
missing. Clear it between runs, as described in [cache usage](usage.md#inspect-and-clear-downloaded-files).
