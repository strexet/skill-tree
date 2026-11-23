# Installed web UX workflow qualification

## Ordinary task

A fresh agent received an isolated Habitica Tool checkout and the following product request, translated from Russian. The supplied task contained no component names, catalog paths, layout measurements or research results.

> On the public /privacy page, provide shortcuts to Personal Notes, Habitica credentials and Private sync. Near the beginning of the page, let the reader choose a built-in theme under “Reading appearance”, retain the choice after reload, and return to the first section using “Return to reading”. Support the keyboard and preserve the policy text.

The app source came from Habitica Tool commit `51ac91982f61b5bde7cebc26629c2e2e621a4a24`. The [fixture-only catalog correction](project-catalog.patch) linked three real consumers in the existing project UI manifest before installation. Catalog discovery and reuse were tested with a populated project catalog. The target's own instructions already pointed to the manifest. The acceptance run tests the combined installed workflow and project guidance. The earlier controlled comparison owns the separate effectiveness measurements.

## Installation

Run the following from the Skill Tree source checkout with a disposable target:

```sh
node .skill-tree/bin/install.js --target "$target" --only codex --flavor web --copy --with-init --non-interactive --dry-run
node .skill-tree/bin/install.js --target "$target" --only codex --flavor web --copy --with-init --non-interactive
node .skill-tree/bin/install.js --target "$target" --only codex --verify
(cd "$target" && node .skill-tree/installation/manager.js --verify)
```

The installer and the owned manager verified three cases. A first install into a minimal web repository left project documents absent. The real-app baseline received a new installation after managed uninstall removed eleven old packages. A separate clone verified a direct update from 0.4.0. All 23 web packages in each checkout contained the same canonical reference. The [installation receipts for the blind task](install.json) cover reference `05143051`. Review clarified that a populated catalog can lack a matching entry. All three installation cases were repeated with final reference `c0efa57d`. [Final installation receipts](final-install.json)

## Discovery before editing

Before editing, the agent named the Color Schemes entry in the project UI manifest and reported checking SignIn, Dashboard and Settings. The agent selected `ColorSchemePanel` with `Compact` and `PresetsOnly` from the signed-out SignIn page. The initial plan also identified the fixed toolbar, keyboard landing position and first paragraph as browser checks.

For the final reference, a second fresh agent received a planning request for a ready-made theme on the public privacy page. The fixture omitted the catalog row linking the picker to working examples. The remaining UX documentation and the actual app code were intact. The agent traced the signed-out SignIn call site, compared the Dashboard and Settings modes, and identified the two properties and expected anonymous behavior. The supplementary check covered component selection only.

## Browser result

The real app ran in isolated local Chrome profiles. The original archive contained unfinished controllers with machine-local worktrees outside the fixture. A nested test copy retained the same app, installed packages and project UI catalog and started a fresh local queue. The consumer processed and selected just the privacy task. The fixture controller completed the privacy task on local commit `7d9cdadd09360f1d2e049349564f06a5a38342b6`.

The initial component tests passed. On the first rendered build the consumer observed that all four jumps scrolled but kept focus on the originating link. The independent observer reproduced the issue in both themes at both widths and text sizes. A separate narrow-screen observation found the open native selector extended beyond the viewport. The consumer fixed focus transfer, selector wrapping and mobile padding. [Agent's first observation](agent-before.json) · [Independent first pass](first-pass.json)

The consumer verified exact text and order for all nine headings and sixteen policy paragraphs, and sampled fourteen control contrast ratios. [Policy comparison](policy.json) · [Contrast samples](contrast.json)

The agent then exercised the repaired page at 360 × 800 and 1280 × 900 with 16 and 32 px root text in Gryphy Light and Obsidian Glow. All 32 actions focused the intended heading and exposed paragraph text. The agent's [final browser observations](agent-final.json), [mobile entry](phone-entry.png) and [mobile destination](phone-notes.png) record the reader's view.

The independent Release run used a 900 px viewport height in all eight configurations. On the enlarged phone the heading and all three shortcuts fit on entry. The Personal Notes paragraph had 572 px of reading space, with 54.9% of the paragraph visible. Return to reading exposed 511 px and 53.5% of the first paragraph. At 1280 px and ordinary text the corresponding paragraphs were fully visible. All 24 section jumps reached focus, all eight returns reached the first section, and all eight theme selections persisted after reload. The observer recorded no off-origin requests or HTTP errors. [Independent browser receipt](independent.json) · [Replay the tested product patch](replay.md)

Focus and scroll settle at different times on the Blazor route. The observer recorded the early geometry and waited for the focused heading's position to stabilize before assessing readability. A single early sample classified working jumps as offscreen on the final app. The retained observer includes both observations. The local Chrome measurements cover the scripted desktop browser and emulated viewports. Participant usability, physical devices and screen readers remain unmeasured.
