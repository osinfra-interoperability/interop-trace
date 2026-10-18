# CLI and downloads

Install from a source checkout with Python 3.12+ and Poetry:

```bash
poetry install
poetry run interop-trace --help
poetry run interop-trace components
```

Start with [the first experiment](first-experiment.md), then use
[configuration](experiments.md) for other combinations.
`poetry run python -m interop_trace` exposes the same CLI.

## Download cache

From the repository root, components reuse downloads in `.interop_trace/cache/`.
They record the source URL, name, type, byte count, retrieval time and available
release metadata. Inspect or clear downloads with:

```bash
poetry run interop-trace cache list
poetry run interop-trace cache clear
```

Clearing asks for confirmation; add `--yes` for scripts. Clear **between runs**:
experiment records refer to cached input files. Clearing preserves experiment
outputs and their provenance records, but removes the underlying cached inputs
and downloaded Sage installation.

Matching URLs reuse files if their presence and size agree with the record.
Reuse does not verify checksums or check for source updates. A live UniProt query
can return a different release after clearing; recorded versions identify the
stored response, not a permanently pinned source. Archive needed inputs separately
when exact long-term reproduction matters.

For a different dedicated cache, use the same directory for execution and inspection:

```bash
poetry run interop-trace run experiments/runs/simple.yaml --output results/run-002 --cache-directory /path/to/cache
poetry run interop-trace cache list --directory /path/to/cache
poetry run interop-trace cache clear --directory /path/to/cache
```

The cache uses Pooch for transfers and extraction. An ownership marker protects
unrelated nonempty directories from being used or cleared as caches.

For direct Python use, see the [API reference](reference.md). The experiment
runner coordinates component setup automatically.
