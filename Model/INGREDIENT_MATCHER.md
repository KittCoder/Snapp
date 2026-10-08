# Ingredient matcher

The v3.7 matcher classifies purchased food identity and required attributes before lexical/vector ranking. Family/subfamily, species/cut, state/form, dietary identity, material variants and nonfood/prepared-food boundaries are hard constraints. Similarity cannot override a failed structural gate. Substitution mode is explicit and separate from exact shopping. Cached and forced matches are revalidated.

Final local diagnostic status: DEMO_SAFE_BUT_NOT_PRODUCTION_FROZEN. Replayed assistant QA (300 deliberately adversarial cases, not independent certification): prior 15 WRONG → 3 corrected, 12 safely abstained, zero remaining known wrong; prior 38 SHOULD_HAVE_MATCHED → 11 recovered, 27 still rejected, zero newly wrong. Labels were preserved. No additional holdout was generated.

Validation: 545 Python test methods, 6 frontend recipe-detail tests, and all 2,064 permanent matcher regression records pass. Full fixed population: 6232 accepted / 2645 rejected, 29.80% no-match. Frozen name-rule precision/recall proxies: 98.03% / 85.01%. These proxies are not human accuracy measurements. Cheese/tomato selections stay stable; strict salt-pork identities safely abstain where necessary.

Run unit tests with `.venv/bin/python -m unittest discover -s Model/tests`. Generic structural regressions live in `Model/evaluation/*regressions.jsonl`. Diagnostic/review tooling is under `scripts/`; it requires separately generated local artifacts. Generated populations, QA labels, audit reports and large proxy benchmarks stay local/ignored. Review labels must never be synthesized from matcher scores.

Known limitations: incomplete product metadata and purchased-head recognition, ambiguous compound scope, limited substitution policy and confidence not calibrated by independent human QA. Missing requested attributes cause abstention. The matcher is a demo candidate, not production frozen.
