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

The CLI currently provides help. No analysis commands are registered.

## Run Sage from Python

`SageWorkflow` runs a local [Sage executable](https://github.com/lazear/sage/releases)
with a native [JSON configuration](https://sage-docs.vercel.app/docs/configuration).
Set the paths below to your executable, settings, and input files in `run_sage.py`:

```python
from pathlib import Path

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.workflows import SageWorkflow

workflow = SageWorkflow(
    executable=Path("/path/to/sage"),
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

The following example retrieves one entry. A temporary directory holds the
working database, while only the release record is retained:

```python
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

from interop_trace.databases import UniProtProvider

provider = UniProtProvider(query="accession:P69905", format="fasta")
with TemporaryDirectory() as temporary:
    database = provider.prepare(output_dir=Path(temporary) / "uniprot")
    copyfile(database.path.parent / "uniprot.json", "uniprot.json")
    # Pass database to SageWorkflow.run(...) here, before leaving this block.
```

Use `database` in place of the manually constructed `Database` in the Sage
example, keeping the workflow call inside the `with` block. When the block ends,
the working database is deleted. The provider keeps no additional cache or archive.

`uniprot.json` records the query, format, request URL, reported UniProt release,
and release date. Missing release headers are recorded as `null`. Requests use
the live API; the recorded release identifies the response and does not pin a
future request to that release.

Each preparation requires a new output directory. The downloaded working file
is named `database`; its representation is described by `Database.format`.
HTTP and transfer errors propagate, empty responses fail, and partial files are
removed rather than returned as completed databases.
