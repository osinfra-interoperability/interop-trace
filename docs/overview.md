# Project scope

Interop Trace investigates whether independently developed bioinformatics
components can exchange usable data. Experiments make the selected sources,
formats, software and parameters explicit, then retain native outputs and failure
records so outcomes can be explained and compared.

The current implementation covers proteomics: HTTP/PRIDE measurements, UniProt
exports, Sage searches and optional evaluation. The small example establishes a
working combination; it does not certify other datasets, formats or tools.
Scientific benchmarking requires reference expectations appropriate to the data.

Experiments execute locally and sequentially. There is no automatic format
conversion, compatibility matrix, workflow-result reuse or benchmark leaderboard
submission. Python 3.12+ is required; native workflows have their own platform
requirements. See [components](components.md) for supported scope.
