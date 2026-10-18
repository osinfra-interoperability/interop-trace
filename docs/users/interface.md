# Local interface

From the repository root:

```bash
poetry install --extras ui
poetry run interop-trace ui
```

Open <http://127.0.0.1:8080/> in your browser. The interface runs on your computer.
For a different checkout or port, use `--directory /path/to/checkout --port 8090`.

## Run and inspect

1. Select a YAML configuration from `experiments/runs/`. The table previews its
   experiment and component choices without downloading anything.
2. Click **Run**. The existing CLI executes all experiments in that configuration,
   using the shared cache and a new `results/ui-…/` directory.
3. Watch status, stages, elapsed time and logs. Updates arrive about once per second.
4. Select a saved run to inspect benchmark metrics. Expand **Files and provenance**
   and select an output file to preview its text or download it. The run
   configuration snapshot is displayed separately below.

The [first experiment](first-experiment.md) is a small, verified starting point.
ProteoBench configurations also need its extra:
`poetry install --extras "ui proteobench"`.

## Behavior and limits

One run can be active per UI server. Each run can contain multiple sequential
experiments. Closing or refreshing the browser tab leaves execution running;
keep the terminal server running until the experiment finishes.
Stop the server with `Ctrl+C` after completion. Stopping it during execution may
interrupt the experiment.

Completed and failed CLI runs also appear in history. After restarting the server,
unfinished runs are shown as **unknown** because the interface cannot confirm their
process state. Inspect their records and logs before starting more work.

The interface shows stages rather than estimated percentages or completion times.
Logs are limited to a 32 KiB preview; the complete console log is saved beside the
run directory as `ui-….console.log`. Native workflow logs remain inside the run.
File previews show the first 32 KiB of UTF-8 text; binary files remain downloadable.
Execution completion and scientific quality are separate: interpret each
benchmark's [scope and metrics](components.md).

Configurations remain YAML files. Edit their settings using the
[configuration guide](experiments.md); the interface provides selection and monitoring.
