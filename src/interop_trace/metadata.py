"""Preserve public component descriptions independently of execution."""

import json
import shutil
from pathlib import Path
from urllib.parse import quote

from interop_trace.downloads import DownloadCache


def snapshot_biotools(
    biotools_id: str, *, output_dir: Path, cache: DownloadCache
) -> Path:
    """Save a bio.tools response unchanged alongside its source provenance.

    IDs are explicit and case is preserved. The output directory must be new.
    Cached responses retain their original retrieval time; snapshot copies
    remain available after the download cache is cleared.
    """
    if not biotools_id.strip() or biotools_id in {".", ".."}:
        raise ValueError("Provide a bio.tools entry ID.")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    download = cache.fetch(
        f"https://bio.tools/api/tool/{quote(biotools_id, safe='')}?format=json",
        name=f"bio.tools:{biotools_id}",
        kind="metadata",
        filename="entry.json",
    )
    shutil.copyfile(download.path, output_dir / "entry.json")
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
