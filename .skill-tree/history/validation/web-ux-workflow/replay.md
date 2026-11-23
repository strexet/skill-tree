# Replaying the signed-out reader acceptance

Use a disposable checkout of Habitica Tool containing commit `51ac91982f61b5bde7cebc26629c2e2e621a4a24`. Export `HABITICA_REPO` with the checkout path and set `ARTIFACTS` to the directory containing `verify.cjs`. Install Playwright in the Node module search path for the observer script, or export `PLAYWRIGHT_PATH` with the module location. The observer ran .NET SDK 8.0.125 and Playwright with the installed Chrome channel. The browser used a local signed-out session.

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
