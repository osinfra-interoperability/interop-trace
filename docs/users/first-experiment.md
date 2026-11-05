# First experiment

This small laptop experiment connects **PRIDE + UniProt → Sage → peptide
recovery**. It uses a processed MGF peak list from
[PXD000001](https://www.ebi.ac.uk/pride/archive/projects/PXD000001), an Erwinia
sample with four protein spikes. Sage is installed automatically and reads the
compressed measurement directly.

From the repository root, with Python 3.12+ and Poetry installed:

```bash
poetry install
poetry run interop-trace run erwinia_sage --output results/simple-001
poetry run interop-trace classify results/simple-001
```

Choose a new output directory for each run. Add `--check` to validate the
configuration without downloading or executing anything. The same actions are
available in the [local interface](interface.md).

## Inputs

Sizes verified on **18 October 2026**:

| Resource | Download size |
| --- | --- |
| PRIDE `PRIDE_Exp_Complete_Ac_22134.pride.mgf.gz` | 5,984,662 bytes (5.71 MiB) |
| UniProt FASTA | 2,138,744 bytes (2.04 MiB) in the verified run |
| Sage 0.14.7 | About 6.6 MB on Apple silicon |

Only this measurement is downloaded, not the RAW files or full project. The
PRIDE catalogue lists its uncompressed size; the
[download server](https://ftp.pride.ebi.ac.uk/pride/data/archive/2012/03/PXD000001/generated/PRIDE_Exp_Complete_Ac_22134.pride.mgf.gz)
reports the compressed size above. The provider does not enforce a size limit.

The UniProt query includes Erwinia SCRI 1043 (taxonomy 218491) and the four spike
proteins below. A fresh query may change with UniProt releases; each download's
release is recorded. Resources are reused from the shared cache.

## Evaluation and assessment

Native Sage settings are in `experiments/settings/sage/erwinia_tmt.json`, based on
[the deposited search settings](https://ftp.pride.ebi.ac.uk/pride/data/archive/2012/03/PXD000001/F063721.dat).
The [deposited results](https://ftp.pride.ebi.ac.uk/pride/data/archive/2012/03/PXD000001/F063721.dat-mztab.txt)
supply one selected reference peptide per spike:

| Protein | Peptide |
| --- | --- |
| Yeast enolase, P00924 | `GNPTVEVELTTEK` |
| Bovine albumin, P02769 | `HLVDEPQNLIK` |
| Rabbit phosphorylase, P00489 | `EIWGVEPSR` |
| Bovine cytochrome c, P62894 | `TGPNLHGLFGR` |

Evaluation counts recovery among rank-one target matches, including Sage's fixed
TMT labels, before and after `spectrum_q <= 0.01`. Classification requires all
four at that threshold. The verified laptop run met this criterion.
This establishes consistency with selected deposited identifications, not overall
accuracy, independent FDR validation or TMT quantification accuracy.

Other configured IDs are `erwinia_comet` and `erwinia_msamanda`. They use the same
inputs and require all four sequences without confidence filtering. See
[component prerequisites](components.md), including Rosetta for Amanda on Apple
silicon. These experiments exercise separate interoperability connections.

## Saved evidence

Each run contains:

| Location | Contents |
| --- | --- |
| `configuration.json` | Selected components, original YAML and package version |
| `environment.json`, `execution.json`, `summary.json` | Runner platform, execution lifecycle and batch errors |
| `experiments.csv` | Summary table for the run |
| `<experiment>/experiment.json` | Stages, errors, acceptance criteria and evaluation metrics |
| `<experiment>/classification.json` | Assessment, criterion checks and diagnosis placeholder |
| `<experiment>/dataset/`, `database/` | Source, query, release and download records |
| `<experiment>/workflow/` | Native settings, commands, logs, version information and outputs |
| `<experiment>/evaluation/` | Reference recovery report |

Execution and assessment populate these files at their respective stages. Inputs
and tools remain in the cache; clearing it preserves reports but removes those
resources. Runs are not self-contained archives, and do not record a Git revision,
full dependency snapshot or locally verified input hashes.

See [configuration](experiments.md) to define experiments and
[CLI commands](usage.md) to manage runs and downloads.
