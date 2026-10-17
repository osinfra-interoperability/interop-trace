# Component catalogue

These names come from the four layer registries. Each YAML component definition
selects a `type` below and supplies that implementation's `parameters`.
Registering, listing or constructing a component does not download resources.

<!-- components:start -->

| Layer | Component | Description |
| --- | --- | --- |
| datasets | [`pride`](components.md#pride) | Selected public PRIDE measurements |
| databases | [`uniprot`](components.md#uniprot) | Query-based UniProtKB exports |
| workflows | [`sage`](components.md#sage) | Local proteomics search and LFQ |
| benchmarks | [`proteobench_dda`](components.md#proteobench-dda) | Q Exactive DDA precursor-ion quantification |

<!-- components:end -->

## pride

Retrieves explicitly selected files from a public PRIDE project.

| Parameter | Meaning |
| --- | --- |
| `project` | Public project accession |
| `files` | Nonempty list of exact, distinct filenames |

Setup retrieves or reuses the catalogue and selected measurements through the
shared cache. Preparation returns their paths and writes `pride.json`. Files keep
their native format and compression; this provider does not convert RAW to mzML
or infer sample metadata. Published checksums are recorded without verification.

See [PRIDE usage](usage.md#retrieve-selected-pride-measurements).

## uniprot

Retrieves query results from UniProtKB.

| Parameter | Meaning |
| --- | --- |
| `query` | Nonempty UniProt query string, interpreted by UniProt |
| `format` | Export format; defaults to `fasta` |

Setup retrieves or reuses the response and original release headers. Preparation
returns the cached database and writes `uniprot.json`. Cache reuse does not check
for newer releases. The database supplies search candidates; it does not supply
the benchmark's experimental expectations.

See [UniProt usage](usage.md#retrieve-a-uniprot-database).

## sage

Runs local Sage searches and optional quantification with native JSON settings.

| Parameter | Meaning |
| --- | --- |
| `configuration` | Path to a native Sage JSON configuration |
| `version` | Downloaded release tag; defaults to `"0.14.7"` |
| `executable` | Optional existing executable, used instead of downloading a release |
| `threads` | Positive integer; defaults to `2` |

The two path parameters resolve relative to the component YAML file. Quote version
strings. Setup resolves the executable, downloading and extracting the pinned
release if needed. Execution delegates input interpretation to Sage and preserves
native outputs, a log and the executable's own version response.

See [Sage usage](usage.md#run-sage-from-python) and the
[ProteoBench LFQ requirements](usage.md#evaluate-sage-quantification-with-proteobench).

## ProteoBench DDA

Scores Sage LFQ output using the installed ProteoBench 0.18.6 library.

| Parameter | Meaning |
| --- | --- |
| `min_observations` | Integer from 1 to 6; defaults to `3` |

This benchmark supports only the published six-run Q Exactive DDA HYE mixture,
with its expected run names and species flags. Sage must keep charge states
separate. The threshold counts observations across all six runs. Reports preserve
numeric metrics, undefined metric names, the per-ion table and packaged settings.

No setup step or reference download is needed. Install the optional library with
`poetry install --extras proteobench`. Evaluation stays local and does not submit
results or perform public-submission validation.

See [ProteoBench usage](usage.md#evaluate-sage-quantification-with-proteobench).
