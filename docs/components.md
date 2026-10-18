# Components and scope

Component YAML definitions select a registered `type` and its `parameters`.
Listing or constructing components never downloads resources. The runner calls
setup before execution where needed. These tables are generated from the registries.

<!-- components:start -->

| Layer | Component | Description |
| --- | --- | --- |
| datasets | [`pride`](components.md#pride) | Selected public PRIDE measurements |
| databases | [`uniprot`](components.md#uniprot) | Query-based UniProtKB exports |
| workflows | [`sage`](components.md#sage) | Local proteomics search and LFQ |
| benchmarks | [`expected_peptides`](components.md#expected-peptides) | Expected-peptide recovery from Sage target matches |
| benchmarks | [`proteobench_dda`](components.md#proteobench-dda) | Q Exactive DDA precursor-ion quantification |

<!-- components:end -->

## pride

| Parameter | Meaning |
| --- | --- |
| `project` | Public PRIDE project accession |
| `files` | Nonempty list of exact, distinct filenames |

Retrieves selected measurements from a public project. Preparation writes
`pride.json` with catalogue and file metadata. It preserves filenames, native
formats and compression. It does not convert RAW to mzML or infer sample metadata.
Published checksums are recorded without verifying downloaded contents.
Select files explicitly and check their sizes in PRIDE before running.

## uniprot

| Parameter | Meaning |
| --- | --- |
| `query` | Nonempty [UniProt query](https://www.uniprot.org/help/api_queries) |
| `format` | Native export format; defaults to `fasta` |

Preparation returns the cached response and writes `uniprot.json`, recording the
query and original release headers. Other exports, such as XML, are allowed;
consumers decide whether they can read them. Cache reuse does not check for newer
releases. The database supplies search candidates, not benchmark ground truth.

## sage

| Parameter | Meaning |
| --- | --- |
| `configuration` | Path to native Sage JSON settings |
| `version` | Release tag; defaults to `"0.14.7"` |
| `executable` | Optional existing executable instead of a download |
| `threads` | Positive integer; defaults to `2` |

Quote version strings. Paths resolve relative to the component YAML file.
Setup downloads and extracts a pinned [Sage release](https://github.com/lazear/sage/releases/tag/v0.14.7)
for supported macOS (Intel/ARM), Linux (x86-64/ARM64) or Windows (x86-64) systems.
A supplied executable skips downloading. Selected dataset and database paths
override inputs in the native JSON. Sage interprets formats and search settings;
the wrapper does not validate declared compatibility or convert files.

Each run preserves native outputs, `sage.log` and `version.txt`. The official
0.14.7 Apple silicon binary reports `sage 0.14.6`; we preserve both the requested
release and executable response. A nonzero exit records a workflow failure.
Native warnings and confidence estimates still require interpretation after a
successful exit.

## Expected peptides

| Parameter | Meaning |
| --- | --- |
| `peptides` | Nonempty list of distinct exact peptide strings |
| `max_q_value` | Spectrum q-value threshold in [0, 1]; defaults to `0.01` |

`expected_peptides` reads Sage's `results.sage.tsv`, selecting rank-one target
matches (`rank=1`, `label=1`). It reports how many expected peptides appear before
and after filtering on `spectrum_q`, counting each peptide once. Modified sequences
must use Sage's exact output notation. An empty, correctly headed table gives zero
recovery; missing columns or invalid target q-values raise an error.

`expected_peptides.json` records the reference, threshold, matching and missing
peptides, source table and metrics. Expectations must come from an independent
reference. This diagnostic does not estimate precision, FDR or quantification
accuracy, and unlisted peptides are not assumed incorrect. No extras are needed.

## ProteoBench DDA

| Parameter | Meaning |
| --- | --- |
| `min_observations` | Minimum observations across all six runs; integer 1–6, default `3` |

Install with `poetry install --extras proteobench`.
`proteobench_dda` uses ProteoBench 0.18.6 to score Sage's `lfq.tsv` and `results.json`
for the [published Q Exactive DDA HYE design](https://proteobench.readthedocs.io/en/stable/modules/dda/dda-ion-qexactive/).
It requires all six runs from [PXD028735](https://www.ebi.ac.uk/pride/archive/projects/PXD028735):

```text
LFQ_Orbitrap_DDA_Condition_A_Sample_Alpha_01.mzML
LFQ_Orbitrap_DDA_Condition_A_Sample_Alpha_02.mzML
LFQ_Orbitrap_DDA_Condition_A_Sample_Alpha_03.mzML
LFQ_Orbitrap_DDA_Condition_B_Sample_Alpha_01.mzML
LFQ_Orbitrap_DDA_Condition_B_Sample_Alpha_02.mzML
LFQ_Orbitrap_DDA_Condition_B_Sample_Alpha_03.mzML
```

`.mzML.gz` is also accepted. Preserve `_HUMAN`, `_YEAST` and `_ECOLI` protein flags;
expected A/B intensity ratios are 1, 2 and 0.25. Enable Sage LFQ while keeping
charge states separate in its native configuration:

```json
{"quant": {"lfq": true, "lfq_settings": {"combine_charge_states": false}}}
```

The adapter does not add confidence filtering or impute missing intensities.
Reports contain metrics and provenance (`proteobench.json`), a per-ion table
(`ions.tsv`) and copies of packaged settings. Metrics cover quantified ion count,
ratio error and within-condition variation; undefined metrics are named separately.
Evaluation is local, with no leaderboard submission or reference download.

This adapter cannot score the first experiment's MGF peptide-identification output. ProteoBench also offers a
[small offline walkthrough](https://proteobench.readthedocs.io/en/stable/contributing/local-usage/)
using bundled **precomputed MaxQuant output**. That exercises its scorer on a laptop,
but does not rerun Sage on a smaller version of the six-run reference experiment.
