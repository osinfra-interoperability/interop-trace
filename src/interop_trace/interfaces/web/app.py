"""A local NiceGUI view over configured runs and their saved evidence."""

from datetime import UTC, datetime
from pathlib import Path

from nicegui import run, ui

from interop_trace.experiments import load_experiments
from interop_trace.interfaces.web.runs import (
    RunBrowser,
    SavedRun,
    console_log,
    file_preview,
)


def serve(directory: Path, port: int = 8080) -> None:
    """Serve one shared launcher on localhost; page selections remain per-tab."""
    browser = RunBrowser(directory)

    @ui.page("/")
    async def index() -> None:
        page = _Dashboard(browser)
        await page.preview()
        await page.refresh()

    ui.run(host="127.0.0.1", port=port, title="Interop Trace", reload=False, show=False)


class _Dashboard:
    def __init__(self, browser: RunBrowser) -> None:
        self.browser = browser
        self.runs: dict[str, SavedRun] = {}
        ui.label("Interop Trace").classes("text-3xl font-semibold")
        ui.label("Run interoperability experiments and inspect their evidence.")
        self._launcher()
        self._results()
        ui.timer(1.0, self.refresh)

    def _launcher(self) -> None:
        with ui.card().classes("w-full"):
            ui.label("Start a run").classes("text-xl font-medium")
            ui.label("Choose experiments; use the header checkbox to select all.")
            self.problem = ui.label().classes("text-red-700")
            self.summary = ui.label()
            self.choices = _table(
                ("id", "source", "dataset", "database", "workflow", "benchmark")
            )
            self.choices.set_selection("multiple").on_select(self._selection_changed)
            self.choices.mark("experiment-choices")
            self.start_button = ui.button(
                "Run", on_click=self.start, icon="play_arrow"
            ).mark("start-run")
            self.start_button.disable()

    def _results(self) -> None:
        with ui.card().classes("w-full"):
            ui.label("Runs and results").classes("text-xl font-medium")
            self.selection = ui.select(
                {},
                label="Saved run",
                on_change=self.show_details,
            ).classes("w-full")
            self.status = ui.label()
            self.location = ui.label().classes("text-sm text-gray-600")
            self.experiments = _table(("id", "status", "stage", "elapsed"))
            with ui.expansion("Files and provenance").classes("w-full"):
                self.file_group = (
                    ui.select({}, label="File group", on_change=self.show_details)
                    .classes("w-full")
                    .mark("file-group")
                )
                self.artifact = (
                    ui.select({}, label="Output file", on_change=self.show_file)
                    .classes("w-full")
                    .mark("output-file")
                )
                ui.label("Preview: first 32 KiB; logs show the last 32 KiB.")
                self.artifact_content = ui.codemirror().classes("w-full h-80")
                self.artifact_content.disable()
                ui.button(
                    "Download file", on_click=self.download, icon="download"
                ).mark("download-file")

    async def preview(self) -> None:
        self.problem.set_text("")
        self.choices.rows = []
        self.choices.selected = []
        try:
            configuration = await run.io_bound(
                load_experiments, self.browser.directory / "experiments"
            )
            if configuration is None:
                return
            self.choices.rows = [
                {**choice, "source": Path(choice["source"]).name}
                for choice in configuration.snapshot["experiments"]
            ]
        except Exception as error:
            self.problem.set_text(str(error))
        self.choices.update()
        self._selection_changed()

    def _selection_changed(self) -> None:
        self.summary.set_text(
            f"Selected: {len(self.choices.selected)} "
            f"of {len(self.choices.rows)} experiments"
        )
        self.start_button.set_enabled(
            bool(self.choices.selected) and not self.browser.active
        )

    async def start(self) -> None:
        self.start_button.disable()
        output = None
        try:
            output = await run.io_bound(
                self.browser.start,
                [r["id"] for r in self.choices.rows if r in self.choices.selected],
            )
        except Exception as error:
            ui.notify(str(error), type="negative")
        finally:
            await self.refresh()
        if output is not None:
            self.selection.set_value(str(output))
            ui.notify("Run started.", type="positive")

    async def refresh(self) -> None:
        history = await run.io_bound(self.browser.history)
        if history is None:
            return
        self.runs = {str(r.directory): r for r in history}
        options = {
            key: f"{r.directory.name} · {r.status}" for key, r in self.runs.items()
        }
        _options(self.selection, options)
        self._selection_changed()
        await self.show_details()

    async def show_details(self) -> None:
        saved = self.runs.get(self.selection.value)
        if saved is None:
            self.status.set_text("No saved runs yet.")
            return
        self.status.set_text(f"Status: {saved.status}")
        self.location.set_text(str(saved.directory))
        self.experiments.rows = [
            {
                "id": r["id"],
                "status": r.get("status", "unknown"),
                "stage": _stage(r.get("stage", "")),
                "elapsed": _elapsed(r, saved.status == "running"),
            }
            for r in saved.experiments
        ]
        self.experiments.update()
        await self._show_files(saved)

    async def _show_files(self, saved: SavedRun) -> None:
        _options(
            self.file_group,
            {
                ".": "Run-level files",
                **{r["id"]: f"Experiment: {r['id']}" for r in saved.experiments},
            },
        )
        group = self.file_group.value
        directory = saved.directory / group
        files = (
            await run.io_bound(
                lambda: sorted(
                    p
                    for p in directory.glob("*" if group == "." else "**/*")
                    if p.is_file()
                )
            )
            or []
        )
        if (
            self.selection.value != str(saved.directory)
            or self.file_group.value != group
        ):
            return
        artifacts = {str(p): str(p.relative_to(directory)) for p in files}
        console = console_log(saved.directory)
        if group == "." and console.is_file():
            artifacts[str(console)] = "Console log"
        _options(self.artifact, artifacts)
        await self.show_file()

    async def show_file(self) -> None:
        source = self.artifact.value
        if source not in self.artifact.options:
            self.artifact_content.props["language"] = None
            self.artifact_content.set_value("No output file selected.")
            return
        text = await run.io_bound(file_preview, Path(source))
        if text is not None and self.artifact.value == source:
            self.artifact_content.props["language"] = {
                ".json": "JSON",
                ".yaml": "YAML",
                ".yml": "YAML",
                ".xml": "XML",
                ".toml": "TOML",
            }.get(Path(source).suffix.lower())
            self.artifact_content.set_value(text)

    def download(self) -> None:
        if self.artifact.value in self.artifact.options:
            ui.download.file(Path(self.artifact.value))


def _table(fields: tuple[str, ...]) -> ui.table:
    return ui.table(
        columns=[
            {"name": f, "label": f.replace("_", " ").title(), "field": f}
            for f in fields
        ],
        rows=[],
        row_key="id",
    ).classes("w-full")


def _options(element: ui.select, options: dict[str, str]) -> None:
    if element.options != options:
        value = element.value
        element.set_options(
            options, value=value if value in options else next(iter(options), None)
        )


def _stage(value: str) -> str:
    if value.startswith("setup:"):
        return "Preparing " + value.split(":", 1)[1]
    return {"workflow": "Workflow", "evaluation": "Evaluation"}.get(
        value, value.capitalize()
    )


def _elapsed(record: dict[str, object], live: bool) -> str:
    try:
        start = datetime.fromisoformat(str(record["started_at"]))
        finished_at = record.get("finished_at")
        if not finished_at and not live:
            return "—"
        finish = (
            datetime.fromisoformat(str(finished_at))
            if finished_at
            else datetime.now(UTC)
        )
        return f"{int((finish - start).total_seconds())} s"
    except (KeyError, ValueError, TypeError):
        return "—"
