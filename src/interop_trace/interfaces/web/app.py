"""A local NiceGUI view over configured runs and their saved evidence."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from nicegui import run, ui

from interop_trace.classification import assess_run
from interop_trace.experiments import load_experiments
from interop_trace.experiments.records import TABLE_FIELDS
from interop_trace.interfaces.web.runs import (
    RunBrowser,
    SavedRun,
    console_log,
    file_preview,
)
from interop_trace.status import ExecutionStatus


def serve(directory: Path, port: int = 8080) -> None:
    """Serve one shared launcher on localhost; page selections remain per-tab."""
    ui.select.default_props("dense options-dense")
    ui.table.default_props("dense")
    ui.expansion.default_props("dense")
    ui.card.default_classes("p-3 gap-2")
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
        self.busy = False
        ui.label("Interop Trace").classes("text-3xl font-semibold")
        ui.label("Run interoperability experiments and inspect their evidence.")
        self._launcher()
        self._results()
        ui.timer(1.0, self.refresh)

    def _launcher(self) -> None:
        with ui.card().classes("w-full"):
            ui.label("Create a run").classes("text-xl font-medium")
            self.name = ui.input("Run name", on_change=self._selection_changed).mark(
                "run-name"
            )
            ui.label("Choose experiments; use the header checkbox to select all.")
            self.problem = ui.label().classes("text-red-700")
            self.summary = ui.label()
            self.choices = _table(
                ("id", "source", "dataset", "database", "workflow", "benchmark")
            )
            self.choices.set_selection("multiple").on_select(self._selection_changed)
            self.choices.mark("experiment-choices")
            self.create_button = ui.button("Create run", on_click=self.create).mark(
                "create-run"
            )
            self.create_button.disable()

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
            with ui.row():
                self.start_button = ui.button(
                    "Run experiments", on_click=self.start, icon="play_arrow"
                ).mark("start-run")
                self.assess_button = ui.button(
                    "Assess results", on_click=self.assess
                ).mark("assess-run")
            self.start_button.disable()
            self.assess_button.disable()
            self.experiments = _table(TABLE_FIELDS)
            self._file_explorer()

    def _file_explorer(self) -> None:
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
            ui.button("Download file", on_click=self.download, icon="download").mark(
                "download-file"
            )

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
        self.create_button.set_enabled(
            bool(self.choices.selected)
            and bool(self.name.value.strip())
            and not self.busy
        )

    async def _perform[T](self, action: Callable[..., T], *args: Any) -> T | None:
        if self.busy:
            return None
        self.busy = True
        self.create_button.disable()
        self.start_button.disable()
        self.assess_button.disable()
        try:
            return await run.io_bound(action, *args)
        except Exception as error:
            ui.notify(str(error), type="negative")
        finally:
            self.busy = False
            await self.refresh()
        return None

    async def create(self) -> None:
        output = await self._perform(
            self.browser.create,
            self.name.value.strip(),
            [r["id"] for r in self.choices.rows if r in self.choices.selected],
        )
        if output is not None:
            self.selection.set_value(str(output))
            ui.notify("Run created.", type="positive")

    async def start(self) -> None:
        saved = self.runs.get(self.selection.value)
        if saved is not None:
            output = await self._perform(self.browser.start, saved.directory)
            if output is not None:
                ui.notify("Execution started.", type="positive")

    async def assess(self) -> None:
        saved = self.runs.get(self.selection.value)
        if saved:
            outputs = await self._perform(assess_run, saved.directory)
            if outputs is not None:
                ui.notify(f"Saved {len(outputs)} assessment(s).", type="positive")

    async def refresh(self) -> None:
        history = await run.io_bound(self.browser.history)
        if history is None:
            return
        self.runs = {str(r.directory): r for r in history}
        options = {
            key: f"{r.directory.name} · {r.status or 'unavailable'}"
            for key, r in self.runs.items()
        }
        _options(self.selection, options)
        self._selection_changed()
        await self.show_details()

    async def show_details(self) -> None:
        self.start_button.disable()
        self.assess_button.disable()
        saved = self.runs.get(self.selection.value)
        if saved is None:
            self.status.set_text("No saved runs yet.")
            self.location.set_text("")
            self.experiments.rows = []
            self.experiments.update()
            _options(self.file_group, {})
            _options(self.artifact, {})
            await self.show_file()
            return
        self.status.set_text(f"Status: {saved.status or 'unavailable'}")
        self.location.set_text(str(saved.directory))
        self.experiments.rows = list(saved.experiments)
        self.experiments.update()
        self.start_button.set_enabled(
            not self.busy
            and not self.browser.active
            and saved.status == ExecutionStatus.NOT_STARTED
            and not (saved.directory / "execution.json").exists()
        )
        self.assess_button.set_enabled(
            not self.busy
            and saved.status == ExecutionStatus.FINISHED
            and any(
                r["status"] == ExecutionStatus.FINISHED
                and not (saved.directory / r["id"] / "classification.json").exists()
                for r in saved.experiments
            )
        )
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
