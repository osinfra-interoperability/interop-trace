# Local interface

From the repository root:

```bash
poetry install --extras ui
poetry run interop-trace ui
```

Open <http://127.0.0.1:8080/>. Use `--directory /path/to/checkout --port 8090`
for another checkout or port.

## Create, predict, execute and assess

1. Select experiments, enter a new run name and click **Create run**. This saves
   the configuration, initial experiment records and `experiments.csv` without
   downloading or executing anything.
2. Choose the **Saved run** and click **Collect metadata** to save its public
   descriptions. Unavailable references are recorded in the metadata index.
3. Click **Predict interoperability** before execution to compare the saved
   declarations for the selected run. The table shows overall, semantic, technical
   and host predictions, each with its evidence coverage.
   See [prediction scope](usage.md#metadata-predictions).
4. Click **Run experiments**. Its experiment table
   updates as execution and evaluation proceed.
5. Click **Assess results** after execution ends. This classifies recorded errors
   and checks saved acceptance criteria. See [assessment outcomes](usage.md#assessment-results).

The table is also saved as `experiments.csv`; individual JSON records hold the
full evidence. Metadata collection and prediction can be skipped for execution.
Existing metadata, predictions and assessments are preserved. To repeat
collection or execution, or apply changed settings, create a new run.

## Inspect files

Expand **Files and provenance**. Choose a run-level or experiment **File group**,
then an **Output file** to preview or download. Each experiment's
`classification.json` contains its assessment and criterion checks.
Its `prediction.json` contains the pre-run checks, supporting references and
semantic, technical and host summaries.
`prediction_environment.json` is a run-level file.
Collected descriptions, OLS term responses and their index appear in the
**Metadata** file group.

JSON, YAML, XML and TOML have syntax highlighting. Previews show the first 32 KiB
of text or the last 32 KiB of logs; download a file for its complete contents.
The UI console log is saved beside the run directory as `<run-name>.console.log`;
native tool logs stay inside each experiment.

## Execution limits

One execution can be active per server; experiments within it run sequentially.
Closing the browser leaves execution running, but the server terminal must stay
open. Downloads remain cached between runs. For ProteoBench, install the combined
extras with `poetry install --extras "ui proteobench"`.
