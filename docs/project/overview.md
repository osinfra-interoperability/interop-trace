# Project scope

Interop Trace tests whether configured bioinformatics datasets, databases and
workflows can execute together and meet declared reference criteria. Records
retain the resource versions, settings, platform, native outputs and failures
needed to explain each observation.

The current implementation covers proteomics through the registered
[components](../users/components.md). Runs execute locally and sequentially.
Consumers interpret native formats; no automatic conversion or workflow-result
reuse is performed.

A successful assessment applies to the tested configuration and its criteria,
not every possible connection or general scientific accuracy. Reference evidence
must suit the scientific question. See [the first experiment](../users/first-experiment.md)
for a small worked example and its limits.
