# Interop Trace

[![CI](https://github.com/thatmariia/interop_trace/actions/workflows/tests.yml/badge.svg)](https://github.com/thatmariia/interop_trace/actions/workflows/tests.yml)
[![Documentation](https://img.shields.io/badge/docs-online-blue)](https://thatmariia.github.io/interop_trace/)

Test interoperability between bioinformatics datasets, databases, workflows and
benchmarks. Explicit configurations select combinations; each run records sources,
settings, native outputs and failures. Proteomics is the first application.

## Run the first experiment

With Python 3.12+ and Poetry installed, from a source checkout:

```bash
poetry install
poetry run interop-trace run experiments/runs/simple.yaml --output results/simple-001
```

This uses a public PRIDE processed peak list (5.98 MB), an Erwinia-and-spikes
UniProt database (2.14 MB in the verified run), and a pinned Sage binary
(about 6.6 MB on Apple silicon). Downloads are cached and Sage is installed
automatically. All four selected deposited reference peptides were recovered at
the configured 1% spectrum q-value threshold. This checks interoperability and
reference-result consistency, not overall search accuracy.
See [the first experiment](docs/first-experiment.md) for verified sizes and outputs.

## Available components

<!-- components:start -->

| Layer | Component |
| --- | --- |
| datasets | [`pride`](docs/components.md#pride) |
| databases | [`uniprot`](docs/components.md#uniprot) |
| workflows | [`sage`](docs/components.md#sage) |
| benchmarks | [`expected_peptides`](docs/components.md#expected-peptides) |
| benchmarks | [`proteobench_dda`](docs/components.md#proteobench-dda) |

<!-- components:end -->

Generated from the registries. See [parameters and scope](docs/components.md).

## Documentation

- **Users:** [first experiment](docs/first-experiment.md),
  [configuration](docs/experiments.md), [CLI and cache](docs/usage.md).
- **Developers:** [development guide](docs/developer.md),
  [API reference](docs/reference.md), [documentation builds](docs/documentation.md).

Every experiment selects an evaluator. Runs use new output directories and share
downloaded resources. Components preserve native formats; interoperability failures remain
visible rather than being silently converted.

## Contributing

```bash
poetry install --all-extras
poetry run pre-commit install
```

See [the developer guide](docs/developer.md) for checks and
[CONTRIBUTING.md](CONTRIBUTING.md) for review policy.

## Citation and license

Cite using [CITATION.cff](CITATION.cff). Licensed under
[Apache-2.0](LICENSE).
