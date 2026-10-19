# Compare search engines

These experiments reuse the [first experiment's](first-experiment.md) small
PRIDE measurement, UniProt database and four deposited reference peptides.
Definitions are in `experiments/search-engines.yaml`; native settings are under
`experiments/settings/comet/` and `experiments/settings/msamanda/`.

From the repository root:

```bash
poetry install
poetry run interop-trace run erwinia_comet --output results/comet-001
poetry run interop-trace run erwinia_msamanda --output results/amanda-001
```

Or run both sequentially in one new directory:

```bash
poetry run interop-trace run erwinia_comet erwinia_msamanda --output results/engines-001
```

Both IDs also appear as checkboxes in the [local interface](interface.md).
Use `--check` to validate the configuration without downloads or execution.
Existing inputs are reused. Comet downloads about 4.1 MB on Apple Silicon;
Amanda downloads about 46.3 MB on macOS. Gzip decompression creates one additional
16.45 MB MGF in the shared cache, reused by both tools.

**Amanda's macOS executable is Intel-only and requires Rosetta on Apple Silicon.**
The application does not install Rosetta. Its Intel Linux and Windows bundles
include the .NET runtime. See [component prerequisites](components.md#msamanda).

## What is evaluated

Both searches translate the deposited design into native settings: trypsin with
two missed cleavages, 25 ppm precursor tolerance, 0.2 Da fragment settings, fixed
TMT6plex on peptide N-termini/lysine, fixed methylthio on cysteine, and variable
methionine oxidation/TMT6plex on tyrosine. Scoring and unspecified defaults remain
engine-specific; these are comparable search intentions, not identical algorithms.

`evaluation/expected_peptides.json` reports recovery among rank-one target matches,
using amino-acid sequences and ignoring modifications. It lists matched and missing
reference peptides and labels the confidence filter as `none`.
**These native results are unfiltered; no 1% FDR claim is made.** Their scores are
not Sage spectrum q-values. The existing `erwinia_sage` experiment keeps its exact
modified-sequence matching and 1% spectrum q-value report.

Comet recovered all four reference sequences in a cached-input laptop run.
Amanda's bundle, commands, settings and reader have offline tests; an actual
Amanda search has not been verified on this Apple Silicon laptop without Rosetta.
Recovery alone does not measure overall accuracy or establish that engines agree.

## Saved evidence

Each experiment has its own `dataset/`, `database/`, `workflow/`, `evaluation/`
and `experiment.json` under the run directory. Workflow files include:

- Comet: `comet.params`, numbered `.comet.txt` results, logs and command records.
- Amanda: original/resolved XML settings, enzyme/modification definitions,
  numbered `.msamanda.csv` results, runtime data, logs and command records.

Native outputs remain unchanged. The input and binary downloads stay in the shared
cache; clearing it removes those resources without deleting run reports.
