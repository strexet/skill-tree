const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const matrix = JSON.parse(fs.readFileSync(path.join(root, "config", "providers.json"), "utf8"));
const installer = require("../bin/install.js");

test("provider ids are unique and Tier 1 complete", () => {
  const ids = matrix.providers.map((provider) => provider.id);
  assert.equal(new Set(ids).size, ids.length);
  for (const id of matrix.tier1Required) {
    assert.ok(ids.includes(id), `missing ${id}`);
  }
});

test("provider profiles and paths are present", () => {
  for (const provider of matrix.providers) {
    assert.match(provider.id, /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
    assert.ok(provider.skillsProfile);
    assert.ok(provider.projectPath !== undefined);
    if (provider.tier !== 3) assert.ok(provider.globalPath !== undefined);
  }
});

test("directory-only probes are soft", () => {
  for (const provider of matrix.providers) {
    const detect = provider.detect || [];
    const directoryOnly = detect.length > 0 && detect.every((probe) => probe.kind === "directory");
    if (directoryOnly) assert.equal(provider.soft, true, provider.id);
  }
});

test("soft providers excluded from --all selection", () => {
  const args = installer.parseArgs(["--all"]);
  const selected = installer.selectedProviders(args, matrix);
  assert.ok(selected.length > 0);
  assert.ok(selected.every((provider) => !provider.soft));
});

test("known Tier 2 passthrough examples present or supported by --agent", () => {
  const examples = ["antigravity", "augment", "bob", "crush", "devin", "droid", "forgecode", "iflow-cli", "rovodev", "tabnine-cli", "trae"];
  const profiles = new Set(matrix.providers.map((provider) => provider.skillsProfile));
  for (const profile of examples) {
    assert.ok(profiles.has(profile), `missing profile ${profile}`);
  }
});

test("fixture duplicate provider id is detectable", () => {
  const fixture = JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures/providers/duplicate-id.json"), "utf8"));
  const ids = fixture.providers.map((provider) => provider.id);
  assert.notEqual(new Set(ids).size, ids.length);
});

test("fixture invalid soft probe is detectable", () => {
  const fixture = JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures/providers/invalid-soft-probe.json"), "utf8"));
  const provider = fixture.providers[0];
  const directoryOnly = provider.detect.every((probe) => probe.kind === "directory");
  assert.equal(directoryOnly, true);
  assert.equal(provider.soft, false);
});
