# Disposable Mechanics catalog exchange

The fixture exports selected records from the existing Markdown seed and two synthetic editorial cards. Each record retains an exact scoped identifier, revision, type, source reference and SHA-256 digest for the delimited Markdown bytes. The fixture retains language and vocabulary context for aliases. The structured exchange validates field types against a closed schema before verifying exact references and editorial decisions. [JSON Schema structural-validation reference](https://json-schema.org/draft/2020-12/json-schema-validation)

The catalog, vocabulary and overlay form an immutable version set. A single disposable-store writer prepares all three members before an atomic active-pointer replacement. A verified rollback selects a previous coherent set by digest. Repeating the original batch leaves the stored bytes unchanged. A changed batch or record revision is rejected. Redirects expose suggested successors while the accepted placement preserves the historical revision. The split requires an explicit target choice.

Run `python3 -B .skill-tree/examples/game-design/mechanics-exchange/catalog.py` from the repository root for the report on standard output. The runner creates and removes a temporary store. Run `python3 -B .skill-tree/tests/test-mechanics-catalog-exchange.py` to verify the independent oracle and retained report.
