# First experiment

This small interoperability experiment connects an HTTP dataset and UniProt
database to Sage, then checks the output against an expected peptide.
It uses Sage's published **single measured spectrum** and the human VAT1 protein
(UniProt Q99536). No Sage installation or ProteoBench extra is needed.

From the repository root, with Python 3.12+ and Poetry installed:

```bash
poetry install
poetry run interop-trace run experiments/simple/run.yaml --output results/simple-001
```

The first run downloads a 12 KB mzML, a single-entry FASTA (about 0.5 KB), and
the native Sage release (about 6.6 MB on Apple silicon; size varies by platform).
Subsequent runs reuse those downloads. Use a **new output directory** each time.
The optional `--check` flag validates configuration without downloading or running.

## What to inspect

Under `results/simple-001/`:

| File | Evidence |
| --- | --- |
| `configuration.json` | Selected experiments and original YAML contents |
| `vat1_sage/dataset/http.json` | Measurement source and cached file |
| `vat1_sage/database/uniprot.json` | UniProt query, release and retrieval time |
| `vat1_sage/workflow/sage.log` | Native search log and warnings |
| `vat1_sage/workflow/results.sage.tsv` | Native peptide-spectrum matches |
| `vat1_sage/evaluation/expected_peptides.json` | Expected-peptide recovery |
| `vat1_sage/experiment.json` | Execution status, artifact paths and metrics |

The verified run returned `LQSRPAAPPAPGPGQLTLR` as a rank-one target match, with
`spectrum_q=1`. Thus `matched_expected_peptides` is **1**, but
`matched_expected_peptides_at_threshold` is **0** at the configured 0.01 threshold.
Completion means the components ran together; it does not mean the match passed
confidence filtering. One spectrum cannot establish search accuracy or FDR control.

Every experiment requires an evaluator. UniProt is a live query: clearing the
cache can retrieve a newer release, which is recorded rather than frozen.

## Sources and scope

The [measurement](https://github.com/lazear/sage/blob/99407db6e3754b31a9b88b7316a0aee67293c93f/tests/LQSRPAAPPAPGPGQLTLR.mzML)
is pinned to Sage's v0.14.7 source commit. The expected peptide comes from the
[author's worked example](https://lazear.github.io/sage/); it is not inferred from
the downloaded database. Search settings follow the upstream example with retention
time prediction disabled for this single spectrum.

See [configuration](experiments.md) to change combinations, or
[components](components.md) for supported parameters and benchmark scope.
