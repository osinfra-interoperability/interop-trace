# Usage

Tracing interoperability across bioinformatics databases and workflows.

## Installation

Install from a source checkout:

```bash
poetry install
```

## Command-line help

Both entry points expose the same CLI:

```bash
poetry run interop-trace --help
poetry run python -m interop_trace --help
```

The CLI provides help and download cache management. Analysis runs use the Python interfaces below.

## Run Sage from Python

`download_sage` retrieves a pinned [Sage release](https://github.com/lazear/sage/releases/tag/v0.14.7).
`SageWorkflow` runs that executable with a native
[JSON configuration](https://sage-docs.vercel.app/docs/configuration).
Set the paths below to your settings and input files in `run_sage.py`:

```python
from pathlib import Path

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.workflows import SageWorkflow, download_sage

workflow = SageWorkflow(
    executable=download_sage("0.14.7"),
    configuration=Path("configuration.json"),
)
result = workflow.run(
    Dataset(files=(Path("sample.mzML").resolve(),)),
    Database(path=Path("proteins.fasta").resolve(), format="fasta"),
    output_dir=Path("results/run-001"),
)
print(result.files)
```

Run the script through Poetry:

```bash
poetry run python run_sage.py
```

The first call downloads the release archive into the shared cache and extracts
Sage, its license and README. Later calls reuse both the archive and executable.
A missing executable is restored from the archive without another download.
`download_sage()` defaults to `"0.14.7"`; it never selects a moving `latest` release.
Set `cache_dir=Path("/path/to/dedicated-cache")` to use another cache location.
To use an executable you already manage, pass `executable=Path("/path/to/sage")`.

The helper selects macOS builds for Apple silicon or Intel, Linux builds for ARM64
or x86-64 using musl, and Windows builds for x86-64. Other platforms raise
`ValueError` before downloading. Release URLs and the requested release version
appear in `poetry run interop-trace cache list`; clearing this cache removes both
the archive and extracted files.

The cache's version field identifies the downloaded release tag. Each run's
`version.txt` preserves the executable's own response to `--version`; these can
differ. The official 0.14.7 Apple silicon archive reports `sage 0.14.6` in our
local check. The helper preserves the requested release without relabeling it.

The selected dataset and database override input paths in the JSON configuration.
Sage runs from the configuration's directory and interprets the inputs itself.
The wrapper passes paths without checking database format labels or extensions.
It uses two threads by default; set `threads` on `SageWorkflow` to change this.
An empty dataset raises an error rather than falling back to inputs in the JSON.

Each run requires a new output directory. The returned `WorkflowResult` has
`format="sage"` and maps filenames to absolute paths. It includes `sage.log`,
`version.txt`, and the files written by Sage, including optional quantification
outputs when produced. A nonzero Sage exit raises `subprocess.CalledProcessError`
and preserves the log. A zero exit status reports process completion; interpret
warnings and scientific results separately.

## Evaluate Sage quantification with ProteoBench

Install the optional, pinned ProteoBench library:

```bash
poetry install --extras proteobench
```

`ProteoBenchDDA` implements the benchmark protocol using ProteoBench 0.18.6.
This first implementation scores Sage's precursor-ion LFQ results for the
[Q Exactive DDA module](https://proteobench.readthedocs.io/en/latest/modules/dda/dda-ion-qexactive/).
It evaluates quantification accuracy and yield on the module's published
human/yeast/E. coli mixture. It cannot score an arbitrary PRIDE dataset or the
small Sage demonstration: those experiments do not supply the expected mixture.
It does not download measurements or run Sage automatically.

Use all six published runs from the alpha series of
[PXD028735](https://www.ebi.ac.uk/pride/archive/projects/PXD028735), retaining
these names after conversion to mzML:

```text
LFQ_Orbitrap_DDA_Condition_A_Sample_Alpha_01.mzML
LFQ_Orbitrap_DDA_Condition_A_Sample_Alpha_02.mzML
LFQ_Orbitrap_DDA_Condition_A_Sample_Alpha_03.mzML
LFQ_Orbitrap_DDA_Condition_B_Sample_Alpha_01.mzML
LFQ_Orbitrap_DDA_Condition_B_Sample_Alpha_02.mzML
LFQ_Orbitrap_DDA_Condition_B_Sample_Alpha_03.mzML
```

Compressed `.mzML.gz` names are also supported. Run Sage with LFQ enabled and
charge states kept separate. Include this section in its JSON configuration:

```json
{
  "quant": {
    "lfq": true,
    "lfq_settings": {"combine_charge_states": false}
  }
}
```

This is a configuration fragment; Sage still needs its usual search settings.
Charge-state combination defaults to `true` in Sage 0.14.7; combined output
cannot be evaluated as precursor ions. Use validated LFQ results; the adapter
does not add a q-value filter or impute missing intensities.

After `SageWorkflow.run(...)`, pass its `result` and the same `dataset` and
`database` to the evaluator:

```python
from pathlib import Path

from interop_trace.evaluation import ProteoBenchDDA

evaluation = ProteoBenchDDA(min_observations=3).evaluate(
    result, dataset, database, output_dir=Path("results/evaluation-001")
)
print(evaluation.metrics)
print(evaluation.reports)
```

The evaluator reads `lfq.tsv` and `results.json` from the workflow result.
Protein identifiers must retain the `_HUMAN`, `_YEAST` and `_ECOLI` species flags
used by the packaged Sage parser. Expected A/B intensity ratios are 1, 2 and 0.25,
respectively. These known sample proportions supply the benchmark expectations;
the search database supplies candidate sequences and is recorded as provenance.
Filenames establish the expected design but do not prove that file contents are
the published measurements.

`min_observations` ranges from 1 to 6 and counts observations across all six runs,
rather than requiring that number in each condition. Summary metrics include
`nr_feature` (quantified precursor-ion count), `mean_abs_epsilon_global`
(absolute error in log2 A/B ratios) and `CV_median` (within-condition variation).
More quantified ions and smaller errors describe different aspects of performance;
there is no single overall score.

Each evaluation requires a new output directory and returns absolute report paths:

- `proteobench.json`: numeric metrics, undefined metric names, threshold, library
  version, Sage parameters and the supplied dataset, database and output paths.
- `ions.tsv`: ProteoBench's processed per-ion table, including observation counts
  and expected and measured ratios. The threshold applies to summary metrics;
  this table retains ions below the threshold for inspection.
- `module_settings.toml` and `parse_settings_sage.toml`: copies of the packaged
  benchmark expectations and Sage parsing settings used for the evaluation.

Undefined metrics are omitted from `EvaluationResult.metrics` and named in the
JSON report. For example, ROC AUC is undefined when only one species is present.
An empty scored table raises an error. Unsupported workflow formats, unrelated
run names and combined-charge LFQ outputs also raise errors.
Evaluation uses the installed library locally and does not submit results,
clone leaderboard repositories or apply public-submission validation.

## Retrieve selected PRIDE measurements

`PrideProvider` retrieves named files from a public
[PRIDE project](https://www.ebi.ac.uk/pride/archive/projects/PXD000001).
Choose exact filenames from the project's file list; there is no default selection
that downloads the entire project. The example below selects a published compressed
peak-list file of about 16 MB:

```python
from pathlib import Path

from interop_trace.datasets import PrideProvider

provider = PrideProvider(
    project="PXD000001",
    files=("PRIDE_Exp_Complete_Ac_22134.pride.mgf.gz",),
)
dataset = provider.prepare(output_dir=Path("results/dataset-001"))
```

Save this as `prepare_dataset.py` and run it through Poetry:

```bash
poetry run python prepare_dataset.py
```

`Dataset.files` contains absolute cached paths in the requested order, with their
original filenames and extensions. The provider preserves the submitted contents,
including compression. It does not convert measurements or infer sample metadata;
`Dataset.sample_metadata` is `None`. The consuming workflow interprets the files.

Each preparation requires a new output directory and writes only `pride.json`.
It records the project, cached catalogue and its original retrieval time, plus
each selected file's complete PRIDE metadata, download URL, local path, byte count
and original download time. Published file identifiers, checksums, sizes and dates
are retained when available. Reported checksums are recorded without being verified
against the downloaded content.

Both the project catalogue and selected files use the shared cache, listed as
`pride | type: dataset`. Later preparations reuse them without contacting PRIDE.
Clear the cache between runs to retrieve a fresh catalogue and file contents.
Set `cache_dir` on the provider to use another dedicated cache location.

Empty or duplicate selections fail before requests. Missing or ambiguous filenames,
and unsupported download locations, fail before measurement downloads. Published
HTTP(S) locations are preferred; PRIDE FTP locations use the repository's HTTPS
mirror. HTTP and transfer errors propagate. If a later file fails, successfully
cached files remain reusable, and the output directory contains no completed
`pride.json` record.

## Retrieve a UniProt database

`UniProtProvider` retrieves a query result from the
[UniProtKB REST API](https://www.uniprot.org/help/api_queries). Its `query` and
`format` settings are passed to UniProt. The default export format is `fasta`;
an XML export uses `format="xml"` and returns `Database.format="uniprot_xml"`.

The following example retrieves one entry and records its release:

```python
from pathlib import Path

from interop_trace.databases import UniProtProvider

provider = UniProtProvider(query="accession:P69905", format="fasta")
database = provider.prepare(output_dir=Path("results/database-001"))
```

Use `database` in place of the manually constructed `Database` in the Sage
example. Its path points directly to the shared download cache. Each preparation
requires a new output directory, which holds `uniprot.json` without duplicating
the downloaded database.

`uniprot.json` records the query, format, request URL, cache path, original download
time, reported UniProt release and release date. Missing release headers are
recorded as `null`. Reusing a download preserves its original release information.
Release headers are captured during the database download, without a separate
version request. HTTP errors raise `requests.exceptions.HTTPError`; transfer errors
also propagate. Empty responses fail, and partial downloads
are removed rather than registered as completed files.

## Inspect and clear downloaded files

From the repository root, downloads are stored in the Git-ignored
`.interop_trace/cache/` directory. UniProt automatically checks this cache before
requesting data. Matching URLs, including query and format settings, reuse the same
completed file. If it is missing or its size has changed, the next preparation
downloads it again.

Downloads use [Pooch](https://www.fatiando.org/pooch/latest/), installed automatically
by Poetry. UniProt and Sage share its HTTP downloader and temporary-file cleanup;
the project adds source release records and the cache commands below. Existing
cache entries remain usable.

Inspect the registered downloads:

```bash
poetry run interop-trace cache list
```

The listing shows the component name and type (`sage` / `workflow`, `uniprot` /
`database`, or `pride` / `dataset`), status, size, source URL, local path, reported
version and original download time. Unlabeled entries show `unknown`; older entries gain missing labels
when their component next reuses them, without another download or a change to
their recorded release and download time.

Each stored file also has a readable `download.json`
registry record beside it. Cache reuse checks file presence and size, rather than
reading large files to calculate a checksum on each request. UniProt queries do not
provide an expected checksum, so the response is not verified against one.

To fetch everything again on the next run, clear the download cache:

```bash
poetry run interop-trace cache clear
```

The command displays the cache location and asks for confirmation. For scripts:

```bash
poetry run interop-trace cache clear --yes
```

Clear between workflow runs, because returned database paths refer to cached files.
Clearing removes managed downloads, incomplete transfers and their registry entries.
Experiment outputs and release records in other directories remain available.
A cache ownership marker prevents an unrelated, nonempty folder from being used or
cleared as a cache.

The same URL may return different data after a source update. Existing cache entries
are reused until cleared or missing; listing a cache does not contact the source to
check for newer releases. The recorded version identifies the stored response and
does not select a historical release for a future request.

For another storage location, use the same path in the provider and CLI:

```python
provider = UniProtProvider(
    query="accession:P69905",
    cache_dir=Path("/path/to/dedicated-cache"),
)
```

```bash
poetry run interop-trace cache list --directory /path/to/dedicated-cache
poetry run interop-trace cache clear --directory /path/to/dedicated-cache
```

Use an empty, dedicated directory for a new cache. The default location is relative
to the current working directory. Other downloaded components can share the same
storage through `DownloadCache`; PRIDE, UniProt and Sage currently use it.
