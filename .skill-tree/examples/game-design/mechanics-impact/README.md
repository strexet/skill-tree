# Disposable Mechanics impact query

The deterministic atlas pins two revisions of the same rule. A consuming placement writes a `uses-rule` edge to the exact rule revision. A check writes a `validates-placement` edge to an observed placement and a derived placement may write an `extends-placement` edge to the parent placement. The query reverses validated links. The report retains one reproducible trace and every verified direct dependency for each affected record. Historical and unaffected records retain the original evidence locators.

The fixture treats hierarchy cycles as an application-level exclusion and records each rejected edge. Missing revisions, foreign scopes and invalid endpoint types stay visible in the unresolved list. The fixture reads exact dependencies and leaves similarity ranking outside the traversal. [W3C SKOS Reference §8.6.8](https://www.w3.org/TR/skos-reference/#semantic-relations)

Run `python3 -B .skill-tree/examples/game-design/mechanics-impact/query.py` from the repository root to regenerate the report on standard output. Run `python3 -B .skill-tree/tests/test-mechanics-catalog-impact.py` to check the independent oracle and retained report.
