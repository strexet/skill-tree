# 3D Creature Pilot Closeout

The [pilot closeout](pilot-closeout.json) records seven accepted criteria for cat and dog r017 and fish Longfin and Roundfin r004. The [paw report](pets-r017-contact/placement-reconciliation.json) records 32 required Walk and Trot cases across both skinned LODs. Gallop measures additional diagnostic cases.

A clean checkout can run the static `creature-catalog-closeout-package` recipe or use the command below.

```sh
python3 .skill-tree/examples/3d/recipes/character/creatures/verify-catalog-pilot.py --project . --control package
```

Package verification checks the reviewed closeout fingerprint and every packaged evidence digest. The verifier checks the identities and completeness of the 4,736 retained Unity observations. Recorded stance windows and stride lengths reproduce all 48 cases, including intervals that cross the loop boundary. The output identifies an archive replay.

The `creature-catalog-native-receipts` recipe checks the exact local Unity archives. The `import` and `motion` controls require `--local-native-archive` and `--queue` with the canonical receipt path resolved from the queue root. The `motion` control also requires the original input and test reports listed in the paw report. The published package carries fingerprints for the retained native files and the historical verifier. Local catalog approval covers the recorded Unity profiles.
