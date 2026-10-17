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

The listing shows each file's status, size, source URL, local path, reported version
and original download time. Each stored file also has a readable `download.json`
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
storage through `DownloadCache`; UniProt and Sage currently use it.
