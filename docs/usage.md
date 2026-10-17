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
