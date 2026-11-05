"""Preserve public component descriptions independently of execution."""

import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

from interop_trace.downloads import DownloadCache
from interop_trace.edam import EDAM_RELEASE, EDAM_URL
from interop_trace.status import MetadataStatus


def _biotools_url(biotools_id: str) -> str:
    return f"https://bio.tools/api/tool/{quote(biotools_id, safe='')}?format=json"


def snapshot_biotools(
    biotools_id: str, *, output_dir: Path, cache: DownloadCache
) -> Path:
    """Save an indented bio.tools response alongside its source provenance.

    IDs are explicit and case is preserved. The output directory must be new.
    Cached responses retain their original retrieval time; snapshot copies
    remain available after the download cache is cleared.
    """
    if not biotools_id.strip() or biotools_id in {".", ".."}:
        raise ValueError("Provide a bio.tools entry ID.")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    download = cache.fetch(
        _biotools_url(biotools_id),
        name=f"bio.tools:{biotools_id}",
        kind="metadata",
        filename="entry.json",
    )
    (output_dir / "entry.json").write_text(
        json.dumps(json.loads(download.path.read_bytes()), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "source.json").write_text(
        json.dumps(
            {
                "source": "bio.tools",
                "biotools_id": biotools_id,
                "url": download.url,
                "retrieved_at": download.downloaded_at,
                "response": "entry.json",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output_dir


def collect_run_metadata(directory: Path) -> Path:
    """Collect saved references once per run, continuing after retrieval errors.

    Only the saved configuration is read; components are not constructed or
    executed. The index links experiment roles and profiles to shared snapshots.
    Existing metadata directories are preserved rather than overwritten.
    """
    directory = directory.resolve()
    configuration = json.loads((directory / "configuration.json").read_text())
    references = configuration.get("metadata_references")
    if not isinstance(references, dict) or not references:
        raise ValueError("Create a run with saved metadata references first.")
    cache = DownloadCache(Path(configuration["cache"]))
    output = directory / "metadata"
    output.mkdir(exist_ok=False)
    index: dict[str, Any] = {"source": "../configuration.json", "components": []}
    collected = {}
    for experiment, components in references.items():
        for component in components:
            biotools_id = component["biotools_id"]
            if biotools_id is None:
                result = {"status": MetadataStatus.MISSING_REFERENCE}
            else:
                if biotools_id not in collected:
                    collected[biotools_id] = _collect_entry(biotools_id, output, cache)
                result = collected[biotools_id]
            index["components"].append(
                {"experiment": experiment, **component, **result}
            )
            (output / "index.json").write_text(
                json.dumps(index, indent=2) + "\n", encoding="utf-8"
            )
    index["ontology"] = _collect_edam(output, cache)
    (output / "index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    return output / "index.json"


def _collect_edam(output: Path, cache: DownloadCache) -> dict[str, Any]:
    result: dict[str, Any] = {"version": EDAM_RELEASE, "url": EDAM_URL}
    try:
        download = cache.fetch(
            EDAM_URL,
            name="EDAM",
            kind="metadata",
            filename="edam.owl",
            metadata={"version": EDAM_RELEASE},
        )
        shutil.copyfile(download.path, output / "edam.owl")
        result.update(
            status=MetadataStatus.COLLECTED,
            response="edam.owl",
            retrieved_at=download.downloaded_at,
        )
    except Exception as error:
        result.update(_retrieval_failure(error))
    return result


def _collect_entry(
    biotools_id: str, output: Path, cache: DownloadCache
) -> dict[str, Any]:
    target = output / "biotools" / quote(biotools_id, safe="")
    result: dict[str, Any] = {
        "url": _biotools_url(biotools_id),
        "directory": str(target.relative_to(output)),
    }
    try:
        snapshot_biotools(biotools_id, output_dir=target, cache=cache)
        result["status"] = MetadataStatus.COLLECTED
    except Exception as error:
        result.update(_retrieval_failure(error))
    return result


def _retrieval_failure(error: Exception) -> dict[str, Any]:
    status = getattr(getattr(error, "response", None), "status_code", None)
    return {
        "status": (
            MetadataStatus.NOT_FOUND
            if status == 404
            else MetadataStatus.RETRIEVAL_FAILED
        ),
        "error": {
            "type": type(error).__name__,
            "message": str(error),
            "http_status": status,
        },
    }
