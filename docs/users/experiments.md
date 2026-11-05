# Configure experiments

Experiment YAML files live directly in `experiments/`. Each can contain several
experiments with globally unique IDs. Reusable component settings live in
`experiments/components/`; native workflow settings live in `experiments/settings/`.

Each experiment selects one dataset, database, workflow and required benchmark.
A dataset can contain several measurements. For example, `simple.yaml` contains:

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
    acceptance:
      expected_recovery_at_threshold:
        min: 1.0
```

## Component profiles

Each component reference names a profile in the corresponding component file.
Profiles select a registered `type` and implementation-specific `parameters`:

```yaml
erwinia_and_spikes:
  type: uniprot
  parameters:
    query: >-
      (organism_id:218491) OR (accession:P00924) OR (accession:P02769)
      OR (accession:P00489) OR (accession:P62894)
    format: fasta
```

Reuse a profile across experiments, or add a profile for different settings.
Paths resolve relative to the YAML file containing them. Workflow search settings
remain in native files, such as Sage JSON. See [components](components.md) for
parameters and supported formats; the runner does not convert inputs or generate
all possible component combinations.

## Acceptance criteria

Optional `acceptance` entries set inclusive, finite numeric `min` and/or `max`
bounds on named benchmark metrics. In the example, classification requires full
reference-peptide recovery at the configured confidence threshold.

Evaluation produces metrics; classification checks the saved criteria against
them. Passing means those criteria were met, not that all results are
scientifically correct. Missing criteria or unavailable metrics leave the outcome
unknown unless an error or another failed criterion establishes failure.

## Selection and validation

```bash
poetry run interop-trace experiments
poetry run interop-trace run erwinia_sage --check
poetry run interop-trace run --all --check
```

Selection uses IDs, not filenames. Pass several IDs to run them in that order,
or `--all` to use filename order followed by experiment order within each file.
Discovery reads only immediate `*.yaml` and `*.yml` files. Use `--directory` for
another experiment folder.

The complete catalogue is validated before selection. `--check` validates YAML,
references, parameters and criteria without downloads or native-tool execution;
it does not establish remote availability or scientific compatibility.

A created run saves the YAML and criteria it uses. Editing configuration affects
new runs. Native settings and input paths remain references until execution.
See [CLI commands](usage.md) or the [local interface](interface.md) to run and assess.
