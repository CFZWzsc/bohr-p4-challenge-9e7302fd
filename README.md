# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-9e7302fd` (track: `academic-review`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable pipeline and all supporting documents. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `methods-and-statistics-audit`
- Summary: Use when a manuscript's methods and statistics must be reviewed for inferential defensibility, requiring checks of control, randomisation, blinding, sample size, power, named tests, p-value reporting, effect sizes, confidence intervals, multiplicity, missing data, contradictions between significance wording and p-values, and explicit unverifiable items.

## Contents

| File |
|------|
| `SKILL.md` |
| `docs/ERROR_HANDLING.md` |
| `examples/demo-case/case.json` |
| `examples/quickstart.md` |
| `references/output-contract.md` |
| `references/peer-review-checklist.md` |
| `scripts/review_core.py` |
| `scripts/review_ext.py` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/sk_entry.py --input /input --work /app/work --out /app/output
```

A single deterministic pass reads `/input`, computes the deliverable and writes a
contract-complete `/app/output/result.json` plus the human-readable review files
described in `SKILL.md`. The same input always produces byte-identical output; no
network access is used, and fields the materials cannot support are reported
explicitly instead of being left empty.

## Notes

- Pure Python standard library; no network access required.
- Every claim is anchored to paragraph-level evidence; unknown items are reported
  in `uncertainty` instead of being fabricated.
