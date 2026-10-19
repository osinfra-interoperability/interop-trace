# Technical reference

## Implementation language

Python >=3.12.

## Interfaces

- CLI help, experiment selection, component listing and cache commands through
  `interop-trace` or `python -m interop_trace`.
- Optional local NiceGUI interface through `interop-trace ui`, using the same
  experiment catalogue and CLI runner.
- Package version through `interop_trace.__version__`.
- Component protocols and records, exported by the four domain subpackages.

## Python API

::: interop_trace

::: interop_trace.interfaces.cli

## Setup and registration

::: interop_trace.components

::: interop_trace.registries

## Experiments

::: interop_trace.experiments.config

::: interop_trace.experiments.catalogue

::: interop_trace.experiments.runner

## Local run browser

::: interop_trace.interfaces.web.runs

## Datasets

::: interop_trace.datasets.base

::: interop_trace.datasets.pride

## Databases

::: interop_trace.databases.base

::: interop_trace.databases.uniprot

## Workflows

::: interop_trace.workflows.base

::: interop_trace.workflows.sage

## Evaluation

::: interop_trace.evaluation.base

::: interop_trace.evaluation.expected_peptides

::: interop_trace.evaluation.proteobench

## Download cache

::: interop_trace.downloads
