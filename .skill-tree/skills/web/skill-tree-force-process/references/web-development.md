# Web Development

Use the admitted framework/runtime, package manager, concrete test/server/build recipes and browser-support policy. Declared scripts and static recipe files are data during installation; executable configuration is never imported. The flavor supports non-JavaScript roots through owned static recipes. No browser runner or framework replacement is compulsory.

## Component selection before a UI change

Identify the user's action and expected result. Locate the component catalog, design system or examples listed in the project's UI guidance. Search by user intent. If a reusable component fits the task, inspect a working call site or story. For a component with several modes, confirm the relevant properties, visible controls and behavior for the same user role. Record the selected mode and verified example in the task plan.

If the project has no catalog or the catalog has no matching entry, search the affected route, adjacent screens and shared components. If an entry has drifted, use the current call site and tests to verify the choice. If the search finds no suitable implementation or example, record the gap and build the smallest task-local solution using project components, native controls or the project's existing UI dependencies. Keep reusable discoveries in the project's existing index. A small Markdown file alongside the project's UI documentation is sufficient when repeated or ambiguous choices justify an index. The target project owns the entries and implementation.

Use one row per meaningful mode. Replace the illustrative path with a working project link.

| User action | Component and mode | Working example | Selection criteria |
| --- | --- | --- | --- |
| Assign one person to an issue | People picker, single selection | `src/issues/AssigneeField` | The issue has one owner. The bulk assignment dialog allows several. |

## Behavior and browser checks

Prefer small behavior slices with pure unit tests, component/DOM assertions, in-process API/contract tests and isolated storage adapters. Derive cases from acceptance and independent domain examples. Exercise forms and state through semantic roles/labels instead of private component internals. A component runner using a real browser remains browser execution regardless of the suite label.

Changed interactive surfaces require task-relevant keyboard, focus, accessible names, error messages, zoom/reflow and contrast assertions. Relevant layout/CSS, hydration, routing, service workers, persistent browser storage and engine-specific behavior need scoped browser evidence. Screenshots complement semantic interaction checks; automated accessibility scans alone never establish conformance. Keep intended golden/baseline changes reviewable before replacement.

Start or reuse one owned server for the exact compatible fixture. Record source/build identity, bind address, isolated port, readiness condition, environment, hard deadline and cleanup. A responding port never establishes ownership. Development server, production-build preview and hosted deployment remain distinct. Browser/storage/service-worker lifecycle scenarios preserve isolated persistent profiles when multi-session state is the assertion; an empty context for every step can invalidate the scenario.

Server/API checks cover malformed input, schema boundaries, authorization, persistence and useful error responses with controlled fixtures. Trusted authorization and sensitive effects stay at the server boundary. Mocked responses never establish provider behavior or persisted effects. Loading, empty, error, retry, cancellation, stale-result races and cleanup after navigation receive task-relevant controlled clock/deferred-response assertions.

Use semantic native controls and project-required compatibility/fallbacks. Choose the affected viewport/browser cases first, then the declared release matrix at the relevant gate. Reduced motion, localization, long text and touch targets apply when the surface requires the assertions. Browser emulation and local passes never qualify physical devices, hosted TLS/redirect/cache/provider behavior or installed PWA relaunch.

Performance work records the affected route, requests/bundles, reproducible lab workload and environment. Field outcomes remain separate from lab or single Lighthouse evidence. Record loading, interaction and layout metrics against the actual project budget; one score never establishes real-user results. Investigate first-failure/flakiness evidence instead of increasing retries until Green.

## Rendered UX review

Walk the primary changed journey in the running app. At entry, identify the next action and check whether the control is visible and reachable. Perform the action with the relevant input and inspect the resulting viewport. For a section jump, verify where keyboard focus lands, whether a fixed header covers the destination, and how much of the requested content is visible. For a save, inspect the visible confirmation or recovery action and whether the entered data survives a recoverable failure.

For responsive UI, repeat the journey at a project-supported narrow width with enlarged text and compare with the ordinary desktop view. Record the route, viewport, text size, action, expected outcome and observations before and after the action. Use a concrete observation such as the first visible paragraph, a measured overlap or the number of links visible at entry. Fix material findings within scope and replay the affected case. If a required browser check cannot run, record the outstanding scenario and blocker in the task evidence.
