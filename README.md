# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-9e7302fd` (track: `academic-review`).

This repository contains the complete skill package for this challenge: the skill
definition, the executable entry point and every supporting script needed to run it.
No precomputed answers, no private data and no credentials are included.

## Skill

- Name: `methods-and-statistics-audit`
- Summary: Use when a manuscript's methods and statistics must be reviewed for inferential defensibility, requiring checks of control, randomisation, blinding, sample size, power, named tests, p-value reporting, effect sizes, confidence intervals, multiplicity, missing data, contradictions between significance wording and p-values, and explicit unverifiable items.

## Contents

| File |
|------|
| `SKILL.md` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/run_skill.py --case /input/case.json --output /app/output/result.json
```

The entry point is `SKILL.md`; input and output contracts, error handling and a
minimal usage example are documented there.

## Notes

- Pure Python standard library; no network access required.
- The result JSON keeps the input case id, the main results, per-item evidence,
  a run status and an uncertainty section.
