# Replaying the signed-out reader acceptance

Use a disposable checkout of Habitica Tool containing commit `51ac91982f61b5bde7cebc26629c2e2e621a4a24`. Export `HABITICA_REPO` with the checkout path and set `ARTIFACTS` to the directory containing `verify.cjs`. Install the verified Playwright version `1.64.0-alpha-1789764292000` in the Node module search path, or export `PLAYWRIGHT_PATH` with the module location. The observer uses the bundled Playwright PNG decoder for contrast sampling. The run used .NET SDK 8.0.125 and the installed Chrome channel with a local signed-out session.

```sh
git -C "$HABITICA_REPO" switch --detach 51ac91982f61b5bde7cebc26629c2e2e621a4a24
git -C "$HABITICA_REPO" apply "$ARTIFACTS/consumer.patch"
trial_output=$(mktemp -d)
cd "$HABITICA_REPO"
dotnet publish src/Habitica.WebApp/Habitica.WebApp.csproj -c Release -o "$trial_output/site"
python3 "$ARTIFACTS/serve.py" "$trial_output/site/wwwroot"
```

In a second shell, export the printed loopback origin as `TRIAL_ORIGIN` and export both `ARTIFACTS` and `HABITICA_REPO`. The observer loads `playwright` through Node’s module resolver by default. The observer reads original policy text from the base Git commit and records assertions and observations from eight fresh browser contexts.

```sh
trial_output=$(mktemp -d)
node "$ARTIFACTS/verify.cjs" "$TRIAL_ORIGIN" "$trial_output/results.json" "$trial_output/images"
```

The retained application patch only contains the consumer's product source changes. The portable profile installation, component discovery and source selection were evaluated in the separate installed-profile run. Browser controls use visible labels and role semantics. Local scheme initialization is the only preload step. Each keyboard jump records both the early focus observation and a bounded stable position. The first few rendered frames can precede asynchronous scroll on the Blazor route.

## Verifying the acceptance checks

The [initial independent run](independent.json) records the 152 assertions exercised during the agent trial. The [review replay](review-replay.json) records the checks from the current observer. A passing result requires a visible title and three visible shortcuts on entry, an explicit return control, and visible paragraph text beginning below the toolbar after Personal Notes and Return. A missing or unreadable chooser contrast sample fails the cell. The measured reading-space values remain observations.

For a negative control, copy the published `site/wwwroot` to a separate directory, append one rule set from the table to the copied `css/app.css`, and run the server and observer against the copy. Each modified fixture should exit with status 1 and identify the affected checks. The original published tree supplies the passing control.

| Control | CSS appended to the copied stylesheet | Expected failed checks |
| --- | --- | --- |
| Missing return control | `.privacy-return { display: none !important; }` | Explicit return and readable return section |
| Shortcuts and paragraph starts outside the viewport | `.privacy-reader .settings-section-nav { margin-block-start: 110vh !important; } .privacy-reader h2:is(#optional-cloud-workspace,#personal-notes) + p { margin-block-start: 120vh !important; }` | Visible entry shortcuts and both readable paragraph starts |
| Chooser color outside the observer's RGB sampler | `.privacy-appearance select { color: color(display-p3 .4 .4 .4) !important; -webkit-text-fill-color: color(display-p3 .4 .4 .4) !important; }` | Chooser text contrast |
