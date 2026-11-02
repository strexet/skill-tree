# Playwright Fixture

The admitted profile includes Playwright Test 1.x. Use the declared profile recipes, semantic locators, condition-based assertions and isolated controlled data. Preserve relevant failure traces and first-failure evidence. No arbitrary sleeps or indiscriminate browser matrix is required.

The [webServer contract](https://playwright.dev/docs/test-webserver) supports server startup/reuse and timeout/cleanup configuration. Repository/build identity, explicit bind/port, readiness, authorization and ownership still govern reuse. Use the correct development or production-build fixture. Persistent storage/service-worker scenarios retain a dedicated isolated profile across the required steps; mocked network and emulated mobile results retain explicit hosted/device limits.
