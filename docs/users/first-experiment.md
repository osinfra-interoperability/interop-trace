# First experiment

This laptop experiment connects **PRIDE + UniProt → Sage → peptide evaluation**.
It searches one small processed peak list from
[PXD000001](https://www.ebi.ac.uk/pride/archive/projects/PXD000001), an Erwinia
sample with four protein spikes. Sage reads the compressed MGF directly;
no RAW conversion or separate Sage installation is needed.

From the repository root, with Python 3.12+ and Poetry installed:

```bash
poetry install
poetry run interop-trace run erwinia_sage --output results/simple-001
```

Use a **new output directory** each time. If `results/simple-001` already exists,
choose another name. Add `--check` to validate configuration without downloads or
execution. Every experiment requires an evaluator.

## Inputs and download sizes

Sizes were checked on **18 October 2026**, before downloading the measurement.

| Input | Download |
| --- | --- |
| `PRIDE_Exp_Complete_Ac_22134.pride.mgf.gz` | 5,984,662 bytes (5.71 MiB), verified by HTTP HEAD and actual file size |
| UniProt FASTA | 2,138,744 bytes (2.04 MiB) in the verified run |
| Sage 0.14.7 | About 6.6 MB on Apple silicon, only if not already cached |

The PRIDE catalogue reports an outdated 16,448,103-byte measurement size; the
[download server](https://ftp.pride.ebi.ac.uk/pride/data/archive/2012/03/PXD000001/generated/PRIDE_Exp_Complete_Ac_22134.pride.mgf.gz)
reports the actual compressed size above. This is the only selected measurement.
The RAW, mzXML and full project are not downloaded. These sizes document the
verified files; the provider does not enforce a download-size limit.

The database query includes the Erwinia strain SCRI 1043 (taxonomy 218491) and
spikes P00924, P02769, P00489 and P62894. The verified UniProt response contains
4,467 entries, including the background proteome rather than just expected positives.
Downloads reuse the existing PRIDE provider and shared cache. UniProt is a live
query: a later fresh download can differ; its release is recorded in each run.

## Search and evaluation

Native Sage settings follow the [deposited Mascot settings](https://ftp.pride.ebi.ac.uk/pride/data/archive/2012/03/PXD000001/F063721.dat):
trypsin with two missed cleavages, ±25 ppm precursor and ±0.2 Da fragment tolerances,
fixed TMT6plex labels on N-termini/lysine and methylthio on cysteine, plus variable
methionine oxidation and TMT6plex on tyrosine. Retention-time prediction is disabled.

The [deposited reference results](https://ftp.pride.ebi.ac.uk/pride/data/archive/2012/03/PXD000001/F063721.dat-mztab.txt)
provide four selected reference peptides, one per spike:

| Spike | Reference peptide |
| --- | --- |
| Yeast enolase, P00924 | `GNPTVEVELTTEK` |
| Bovine albumin, P02769 | `HLVDEPQNLIK` |
| Rabbit phosphorylase, P00489 | `EIWGVEPSR` |
| Bovine cytochrome c, P62894 | `TGPNLHGLFGR` |

These were chosen before running Sage. The benchmark configuration includes their
fixed TMT labels in Sage's exact sequence notation. Evaluation counts their recovery
among rank-one target matches before and after `spectrum_q <= 0.01`.
The verified laptop run recovered **all four**, including at that threshold.

This is consistency with selected deposited identifications, not independent
proof of accuracy or FDR calibration. The processed peak list and selected
reference peptides do not represent an unbiased full-RAW benchmark. This experiment
does not score the project's TMT reporter ratios or ProteoBench LFQ quantification.

## Where results go

Under the selected output directory:

| File | Evidence |
| --- | --- |
| `configuration.json` | Original YAML, component choices and package version |
| `erwinia_sage/dataset/pride.json` | PRIDE catalogue, selected source and download record |
| `erwinia_sage/database/uniprot.json` | Query, release and retrieval time |
| `erwinia_sage/workflow/sage-settings.json` | Exact input settings copy executed by Sage |
| `erwinia_sage/workflow/sage.command.json` | Command arguments, working directory and thread override |
| `erwinia_sage/workflow/results.json` | Sage's effective settings, including defaults and input overrides |
| `erwinia_sage/workflow/version.txt` | Version reported by the actual executable |
| `erwinia_sage/workflow/sage.log` | Native log and warnings |
| `erwinia_sage/workflow/results.sage.tsv` | Native peptide-spectrum matches |
| `erwinia_sage/evaluation/expected_peptides.json` | Reference recovery and threshold |
| `erwinia_sage/experiment.json` | Execution status, artifact paths and metrics |

New runs save the input snapshot and command records; older runs retain only
the files recorded at the time. Inputs remain in the shared cache rather than
being duplicated under results. The run is therefore not a self-contained archive:
clearing the cache removes its inputs. Locally computed content hashes, the code
revision and a complete dependency/environment snapshot are not currently recorded.

See [configuration](experiments.md) for other combinations and
[components](components.md) for parameter scope.
