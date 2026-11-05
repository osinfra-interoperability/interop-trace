# Local interface

From the repository root:

```bash
poetry install --extras ui
poetry run interop-trace ui
```

Open <http://127.0.0.1:8080/>. For another checkout or port, use
`--directory /path/to/checkout --port 8090`.

## Create a run

Enter a run name, check the experiments to include, and click **Create run**.
Names start with a letter or digit and use letters, digits, dots, underscores or
hyphens. An existing name is never overwritten.

Creation saves the selected experiment/component YAML in `configuration.json`,
initial `not_started` experiment records and the run table in `experiments.csv`.
It does not download resources or execute tools. Native settings and input paths
remain references; their execution provenance is recorded when the tools run.

## Execute and assess

Choose a **Saved run**. Its experiment table and stage actions appear together:

- **Run experiments** executes the created run once, including its configured
  benchmarks. Status, stage and error columns update as execution progresses.
- **Assess results** processes finished experiments after execution ends. The
  [deterministic rules](usage.md#separate-run-stages) classify recorded errors and
  compare saved evaluation metrics with experiment acceptance criteria. Existing
  assessments are preserved; runs without criteria remain `unknown` when no
  error is recorded.

The UI and `experiments.csv` use the same table projection. Execution and
assessment update the saved CSV; the individual JSON records remain authoritative.
Assessment columns stay empty until an assessment is saved.

`not_started`, `running` and `finished` describe execution, not scientific success.
Recorded errors appear separately. A component error skips that experiment's
remaining stages; the next experiment still runs. Missing process information is
shown as **unavailable**. See [CLI commands](usage.md) for the same stages.

## Inspect files

Expand **Files and provenance**. **File group** selects run-level files or an
experiment; **Output file** selects the file to preview or download. The table is
available as `experiments.csv`, and each saved assessment as `classification.json`
inside its experiment folder.

Previews show the first 32 KiB of text, or the last 32 KiB for logs. JSON, YAML,
XML and TOML have syntax highlighting. Binary files can be downloaded. The UI
console log is saved beside the run directory as `<run-name>.console.log` and
appears with run-level files; native tool logs stay inside their experiments.

## Limits

One execution can be active per UI server. Creating another run does not start
it. Closing the browser leaves execution running; keep the server terminal open.
Use a new run name to repeat execution; downloaded resources remain cached.
ProteoBench configurations require `poetry install --extras "ui proteobench"`.
