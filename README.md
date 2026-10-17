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
UniProt databases and running Sage. See [the usage examples](docs/usage.md).
The CLI exposes help.

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
```
See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution and code-review policy.

## Citation

If you use this software, cite it using [`CITATION.cff`](CITATION.cff).

## Legal and Licensing

This project is licensed under `https://spdx.org/licenses/Apache-2.0`. See `LICENSE` for the full license text.
