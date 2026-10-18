"""Check the Sage process boundary without downloading or running scientific data."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.downloads import DownloadCache
from interop_trace.workflows import SageWorkflow


@pytest.fixture
def executable(tmp_path: Path) -> Path:
    """Provide a real subprocess that records arguments and emits native files."""
    path = tmp_path / "fake sage"
    path.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('sage test-version')\n"
        "    sys.exit(0)\n"
        "args = sys.argv[1:]\n"
        "output = Path(args[args.index('--output_directory') + 1])\n"
        "record = {'args': args, 'cwd': os.getcwd(),\n"
        "          'threads': os.environ.get('RAYON_NUM_THREADS'),\n"
        "          'settings': Path(args[0]).read_text()}\n"
        "(output / 'invocation.json').write_text(json.dumps(record))\n"
        "print('sage stdout', flush=True)\n"
        "print('sage stderr', file=sys.stderr, flush=True)\n"
        "if os.environ.get('FAKE_SAGE_FAIL'):\n"
        "    sys.exit(7)\n"
        "(output / 'results.json').write_text('{}')\n"
        "(output / 'results.sage.tsv').write_text('header\\n')\n"
        "if os.environ.get('FAKE_SAGE_LFQ'):\n"
        "    (output / 'lfq.tsv').write_text('header\\n')\n"
    )
    path.chmod(0o755)
    return path


@pytest.fixture
def inputs(tmp_path: Path) -> tuple[Dataset, Database, Path]:
    folder = tmp_path / "inputs with spaces"
    folder.mkdir()
    configuration = folder / "settings.json"
    configuration.write_text('{"mzml_paths": ["do-not-use.mzML"]}')
    files = (folder / "first.measurement", folder / "second.measurement")
    for path in files:
        path.write_text("measurements interpreted by the tool")
    database = folder / "proteins.data"
    database.write_text("sequences interpreted by the tool")
    return Dataset(files), Database(database, format="tool-decides"), configuration


@pytest.mark.parametrize("quantification", [False, True])
def test_run_passes_inputs_and_collects_native_files(
    workflow: SageWorkflow,
    inputs: tuple[Dataset, Database, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    quantification: bool,
) -> None:
    dataset, database, configuration = inputs
    if quantification:
        monkeypatch.setenv("FAKE_SAGE_LFQ", "1")
    output = tmp_path / "results with spaces"
    result = workflow.run(dataset, database, output_dir=output)

    record = json.loads(result.files["invocation.json"].read_text())
    args = record["args"]
    assert args[0] == str(output / "sage-settings.json")
    assert result.files["sage-settings.json"].read_bytes() == configuration.read_bytes()
    assert args[args.index("--fasta") + 1] == str(database.path)
    assert args[-2:] == [str(path) for path in dataset.files]
    assert record["cwd"] == str(configuration.parent)
    assert record["threads"] == "3"
    saved_command = json.loads(result.files["sage.command.json"].read_text())
    assert saved_command["command"] == [str(workflow.executable), *args]
    assert saved_command["cwd"] == record["cwd"]
    assert saved_command["environment"] == {"RAYON_NUM_THREADS": record["threads"]}
    version_command = json.loads(result.files["version.command.json"].read_text())
    assert version_command["command"] == [str(workflow.executable), "--version"]
    assert "--disable-telemetry-i-dont-want-to-improve-sage" in args
    assert result.format == "sage"
    assert result.files["results.json"].is_absolute()
    assert "results.sage.tsv" in result.files
    assert ("lfq.tsv" in result.files) == quantification
    assert "sage test-version" in result.files["version.txt"].read_text()
    assert "sage stdout" in result.files["sage.log"].read_text()
    assert "sage stderr" in result.files["sage.log"].read_text()


def test_search_uses_snapshot_if_original_settings_change(
    workflow: SageWorkflow,
    inputs: tuple[Dataset, Database, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset, database, configuration = inputs
    original = configuration.read_text()
    execute = workflow._execute

    def edit_original(command: list[str], log_path: Path, cwd: Path) -> None:
        configuration.write_text("{}")
        execute(command, log_path, cwd)

    monkeypatch.setattr(workflow, "_execute", edit_original)
    result = workflow.run(dataset, database, output_dir=tmp_path / "snapshot")
    record = json.loads(result.files["invocation.json"].read_text())
    assert record["settings"] == original
    assert configuration.read_text() != original


def test_failure_preserves_log(
    workflow: SageWorkflow,
    inputs: tuple[Dataset, Database, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset, database, configuration = inputs
    monkeypatch.setenv("FAKE_SAGE_FAIL", "1")
    output = tmp_path / "failed"

    with pytest.raises(subprocess.CalledProcessError) as error:
        workflow.run(dataset, database, output_dir=output)

    assert error.value.returncode == 7
    assert "sage stderr" in (output / "sage.log").read_text()
    assert (output / "sage-settings.json").read_bytes() == configuration.read_bytes()
    assert json.loads((output / "sage.command.json").read_text())["command"][1] == str(
        output / "sage-settings.json"
    )


def test_existing_results_are_preserved(
    workflow: SageWorkflow, inputs: tuple[Dataset, Database, Path], tmp_path: Path
) -> None:
    dataset, database, configuration = inputs
    output = tmp_path / "existing"
    output.mkdir()
    previous_log = output / "sage.log"
    previous_log.write_text("previous run")

    with pytest.raises(FileExistsError):
        workflow.run(dataset, database, output_dir=output)

    assert previous_log.read_text() == "previous run"


def test_empty_dataset_cannot_fall_back_to_configuration(
    workflow: SageWorkflow, inputs: tuple[Dataset, Database, Path], tmp_path: Path
) -> None:
    _, database, configuration = inputs
    output = tmp_path / "empty"

    with pytest.raises(ValueError, match="at least one measurement"):
        workflow.run(Dataset(()), database, output_dir=output)

    assert not output.exists()


@pytest.fixture
def workflow(
    executable: Path, inputs: tuple[Dataset, Database, Path], tmp_path: Path
) -> SageWorkflow:
    workflow = SageWorkflow(configuration=inputs[2], executable=executable, threads=3)
    workflow.setup(cache=DownloadCache(tmp_path / "cache"))
    return workflow
