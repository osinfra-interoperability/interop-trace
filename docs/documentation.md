# Build and view the documentation

Install the documentation dependencies:

```bash
poetry install --extras "docs"
```

Preview the documentation locally:

```bash
poetry run zensical serve
```

Build the static site and treat warnings as errors:

```bash
poetry run zensical build --strict
```

The local preview is available at <http://127.0.0.1:8000/> by default. The
static site is written to `site/`.

## Continuous integration

The documentation workflow runs on pushes to any branch and pull requests targeting
`main`. It generates the component tables from the layer registries before building
the site. Only pushes to `main` deploy the site to GitHub Pages.

CI does not commit generated Markdown back to the repository. Tests check that the
committed tables match the registries. When changing registrations, regenerate and
include the refreshed tables in the same change:

```bash
poetry run python scripts/update_component_tables.py
```
