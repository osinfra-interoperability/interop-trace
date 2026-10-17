# Interop Trace

[![CI](https://github.com/thatmariia/interop_trace/actions/workflows/tests.yml/badge.svg)](https://github.com/thatmariia/interop_trace/actions/workflows/tests.yml) [![Documentation](https://img.shields.io/badge/docs-online-blue?labelColor=gray)](https://thatmariia.github.io/interop_trace/) ![Tool Type](https://img.shields.io/badge/tool%20type-Command--line%20tool%20%7C%20Library-blue?labelColor=gray)

Tracing interoperability across bioinformatics databases and workflows.

Documentation: https://thatmariia.github.io/interop_trace/

## Purpose

A research software project for empirically testing interoperability across bioinformatics databases and workflows. It runs controlled database–workflow configurations against reference benchmarks, traces where interoperability succeeds or breaks, and produces evidence about the causes of incompatibility.


## Purpose Categories

- Integration & interfacing
- Data analysis

## Research Topics

- [bioinformatics](http://edamontology.org/topic_0091) - [database management](http://edamontology.org/topic_3489) - [proteomics](http://edamontology.org/topic_0121)

## Installation

Install from a source checkout:

```bash
poetry install
```

## Usage

```bash
poetry run python -m interop_trace --help
```

The package provides component contracts and Python interfaces for retrieving
PRIDE datasets and UniProt databases, downloading and running Sage, and evaluating
its LFQ results with ProteoBench's Q Exactive DDA benchmark.
See [the usage examples](docs/usage.md).

## Available components

<!-- components:start -->

| Layer | Component |
| --- | --- |
| datasets | [`pride`](docs/components.md#pride) |
| databases | [`uniprot`](docs/components.md#uniprot) |
| workflows | [`sage`](docs/components.md#sage) |
| benchmarks | [`proteobench_dda`](docs/components.md#proteobench-dda) |

<!-- components:end -->

The tables are generated from the layer registries. See the
[component catalogue](docs/components.md) for parameters and scope.

## Configured experiments

Reusable YAML files define components; an experiment file selects one of each
layer. A run executes the listed experiments sequentially:

```bash
poetry run interop-trace run experiments/first.yaml --check
poetry run interop-trace run experiments/first.yaml --output results/run-001
```

Create the configuration files using [the experiment guide](docs/experiments.md).
`--check` validates configuration without downloads or execution. Each run uses a
new directory and records settings, status and results. Downloads share the cache;
workflow outputs remain separate. The runner does not convert measurement formats.

ProteoBench evaluation is optional:

```bash
poetry install --extras proteobench
```

It requires the benchmark's published six-run mixture design and Sage LFQ output;
it does not apply to arbitrary datasets or download measurements automatically.

Inspect downloads or clear them before a fresh run:

```bash
poetry run interop-trace cache list
poetry run interop-trace cache clear
```

Downloads are reused from `.interop_trace/cache/`. Clearing asks for confirmation;
use `--yes` for scripts.

## Documentation

- User guide: installation, configuration, usage, and examples
- Developer guide: development, tests, contribution, and reference

## Development

Set up the development environment with:

```bash
poetry install --all-extras
```
Run the configured checks:

```bash
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy src
poetry run python -m pytest
poetry run python scripts/update_component_tables.py --check
```
See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution and code-review policy.

## Citation

If you use this software, cite it using [`CITATION.cff`](CITATION.cff).

## Legal and Licensing

This project is licensed under `https://spdx.org/licenses/Apache-2.0`. See `LICENSE` for the full license text.
