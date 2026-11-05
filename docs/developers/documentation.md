# Documentation maintenance

Install dependencies and preview locally at <http://127.0.0.1:8000/>:

```bash
poetry install --extras docs
poetry run zensical serve
```

Build the site in `site/`, treating warnings as errors:

```bash
poetry run zensical build --strict
```

## Component tables

Registry changes update marked sections in the README and component reference:

```bash
poetry run python scripts/update_component_tables.py
```

Pre-commit runs this automatically and requires Poetry on `PATH`. Review and
stage generated changes, then retry the commit. Tests reject stale tables.

## Continuous integration

Documentation builds run on branch pushes and pull requests to `main`. CI
generates component tables before building, without committing them back.
Only pushes to `main` deploy to GitHub Pages.
