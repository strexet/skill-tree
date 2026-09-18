const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const cli = path.join(root, "bin", "install.js");

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "skill-tree-test-"));
}

function run(args, options = {}) {
  return spawnSync(process.execPath, [cli, ...args], {
    cwd: root,
    text: true,
    encoding: "utf8",
    env: { ...process.env, ...(options.env || {}) },
  });
}

test("--help succeeds", () => {
  const result = run(["--help"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Usage:/);
});

test("--list succeeds without writes", () => {
  const result = run(["--list"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /claude-code/);
  assert.match(result.stdout, /skill-tree-repo-documentation/);
  assert.match(result.stdout, /skill-tree-repo-documentation-audit/);
  assert.match(result.stdout, /skill-tree-unity-repo-documentation/);
  assert.match(result.stdout, /skill-tree-unity-repo-documentation-audit/);
  assert.match(result.stdout, /skill-tree-create-documents-snapshot/);
  assert.match(result.stdout, /skill-tree-add-pending-task/);
  assert.match(result.stdout, /skill-tree-unity-create-documents-snapshot/);
});

test("dry-run all succeeds without installing", () => {
  const target = tmpdir();
  const result = run(["--dry-run", "--all", "--project", "--target", target]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /dry-run/);
  assert.equal(fs.existsSync(path.join(target, ".agents", "skills", "skill-tree-unity-repo-documentation")), false);
});

test("project-scope copy install preserves unrelated skill", () => {
  const target = tmpdir();
  const unrelated = path.join(target, ".agents", "skills", "unrelated-skill");
  fs.mkdirSync(unrelated, { recursive: true });
  fs.writeFileSync(path.join(unrelated, "SKILL.md"), "---\nname: unrelated-skill\ndescription: keep\n---\n", "utf8");
  const result = run(["--only", "codex", "--project", "--target", target, "--copy", "--skills", "skill-tree-process-future-pending"]);
  assert.equal(result.status, 0, result.stderr);
  assert.ok(fs.existsSync(path.join(target, ".agents", "skills", "skill-tree-process-future-pending", "SKILL.md")));
  assert.ok(fs.existsSync(path.join(unrelated, "SKILL.md")));
});

test("portable pending intake installs alone with self-contained references", () => {
  const target = tmpdir();
  const name = "skill-tree-add-pending-task";
  try {
    const result = run(["--only", "codex", "--project", "--target", target, "--copy", "--skills", name]);
    assert.equal(result.status, 0, result.stderr);
    const installed = path.join(target, ".agents", "skills", name);
    for (const file of ["SKILL.md", "references/pending-task-intake.md", "references/pending-task-format.md", "agents/openai.yaml"]) {
      assert.deepEqual(fs.readFileSync(path.join(installed, file)), fs.readFileSync(path.join(root, "skills", name, file)));
    }
    assert.deepEqual(fs.readdirSync(path.join(target, ".agents", "skills")), [name]);
    const verified = run(["--verify", "--only", "codex", "--project", "--target", target, "--skills", name]);
    assert.equal(verified.status, 0, verified.stderr);
  } finally {
    fs.rmSync(target, { recursive: true, force: true });
  }
});

test("global-scope copy install uses HOME-derived path", () => {
  const home = tmpdir();
  const result = run(["--only", "claude-code", "--global", "--copy", "--skills", "skill-tree-implement-next-future-task"], { env: { HOME: home } });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(fs.existsSync(path.join(home, ".claude", "skills", "skill-tree-implement-next-future-task", "SKILL.md")));
});

test("copy mode refuses overwrite without force and force replaces", () => {
  const target = tmpdir();
  let result = run(["--only", "codex", "--project", "--target", target, "--copy", "--skills", "skill-tree-unity-repo-documentation"]);
  assert.equal(result.status, 0, result.stderr);
  result = run(["--only", "codex", "--project", "--target", target, "--copy", "--skills", "skill-tree-unity-repo-documentation"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /exists/);
  result = run(["--only", "codex", "--project", "--target", target, "--copy", "--force", "--skills", "skill-tree-unity-repo-documentation"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /copied/);
});

test("symlink mode creates symlink where supported", { skip: process.platform === "win32" }, () => {
  const target = tmpdir();
  const result = run(["--only", "codex", "--project", "--target", target, "--symlink", "--skills", "skill-tree-implement-next-future-task"]);
  assert.equal(result.status, 0, result.stderr);
  const installed = path.join(target, ".agents", "skills", "skill-tree-implement-next-future-task");
  assert.equal(fs.lstatSync(installed).isSymbolicLink(), true);
});

test("bridge insertion is idempotent and creates backup on second write", () => {
  const target = tmpdir();
  fs.writeFileSync(path.join(target, "AGENTS.md"), "# Existing\n\nKeep me.\n", "utf8");
  let result = run(["--only", "codex", "--project", "--target", target, "--copy", "--with-init", "--skills", "skill-tree-process-future-pending"]);
  assert.equal(result.status, 0, result.stderr);
  result = run(["--only", "codex", "--project", "--target", target, "--copy", "--force", "--with-init", "--skills", "skill-tree-process-future-pending"]);
  assert.equal(result.status, 0, result.stderr);
  const text = fs.readFileSync(path.join(target, "AGENTS.md"), "utf8");
  assert.equal((text.match(/BEGIN skill-tree-skills/g) || []).length, 1);
  assert.ok(text.includes("Keep me."));
  assert.ok(fs.existsSync(path.join(target, "AGENTS.md.bak")));
});

test("bridge uninstall preserves surrounding content", () => {
  const target = tmpdir();
  fs.writeFileSync(path.join(target, "AGENTS.md"), "# Existing\n", "utf8");
  let result = run(["--only", "codex", "--project", "--target", target, "--copy", "--with-init", "--skills", "skill-tree-process-future-pending"]);
  assert.equal(result.status, 0, result.stderr);
  result = run(["--uninstall", "--only", "codex", "--project", "--target", target, "--with-init", "--skills", "skill-tree-process-future-pending"]);
  assert.equal(result.status, 0, result.stderr);
  const text = fs.readFileSync(path.join(target, "AGENTS.md"), "utf8");
  assert.ok(text.includes("# Existing"));
  assert.equal(text.includes("BEGIN skill-tree-skills"), false);
});

test("verify mode detects installed skill", () => {
  const target = tmpdir();
  let result = run(["--only", "codex", "--project", "--target", target, "--copy", "--skills", "skill-tree-implement-next-future-task"]);
  assert.equal(result.status, 0, result.stderr);
  result = run(["--verify", "--only", "codex", "--project", "--target", target, "--skills", "skill-tree-implement-next-future-task"]);
  assert.equal(result.status, 0, result.stderr);
});

test("uninstall removes selected skill only", () => {
  const target = tmpdir();
  let result = run(["--only", "codex", "--project", "--target", target, "--copy"]);
  assert.equal(result.status, 0, result.stderr);
  result = run(["--uninstall", "--only", "codex", "--project", "--target", target, "--skills", "skill-tree-process-future-pending"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(fs.existsSync(path.join(target, ".agents", "skills", "skill-tree-process-future-pending")), false);
  assert.ok(fs.existsSync(path.join(target, ".agents", "skills", "skill-tree-unity-repo-documentation", "SKILL.md")));
});

test("explicit upstream agent dry-run builds npx command", () => {
  const result = run(["--dry-run", "--agent", "qwen-code", "--source", "https://github.com/example/repo", "--skills", "skill-tree-process-future-pending"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /npx -y skills add/);
  assert.match(result.stdout, /--agent qwen-code/);
});

test("partial provider failure returns non-zero and keeps other rows", () => {
  const target = tmpdir();
  const fileDest = path.join(target, "not-a-directory");
  fs.writeFileSync(fileDest, "x", "utf8");
  const result = run(["--only", "codex", "--only", "generic", "--project", "--target", fileDest, "--copy", "--skills", "skill-tree-process-future-pending"]);
  assert.equal(result.status, 1);
  assert.match(result.stdout, /failed:/);
});

for (const [name, mode] of [["skill-tree-work-through-next", "next"], ["skill-tree-implement-all", "all"]]) {
  test(`${name} installs alone and completes a temporary fixture run`, () => {
    const target = tmpdir();
    try {
      const installation = run(["--only", "codex", "--project", "--target", target, "--copy", "--skills", name]);
      assert.equal(installation.status, 0, installation.stderr);
      assert.deepEqual(fs.readdirSync(path.join(target, ".agents", "skills")), [name]);
      const docs = path.join(target, "skill-tree", "documents");
      fs.mkdirSync(docs, { recursive: true });
      fs.copyFileSync(path.join(root, "tests/fixtures/future/valid.md"), path.join(docs, "future.md"));
      fs.writeFileSync(path.join(target, "source.cs"), "Fixture source.\n");
      fs.writeFileSync(path.join(target, "test-report.json"), JSON.stringify({ fixture: "behavioral-simulation" }));
      const helper = path.join(target, ".agents", "skills", name, "scripts", "workflow-state.py");
      function command(commandName, extra = [], payload = null) {
        let args = [helper, commandName, target, ...extra];
        if (payload !== null) {
          const input = path.join(target, "payload.json");
          fs.writeFileSync(input, JSON.stringify(payload));
          args.push("--input", input);
        }
        const result = spawnSync("python3", args, { cwd: target, encoding: "utf8" });
        assert.equal(result.status, 0, result.stdout + result.stderr);
        return JSON.parse(result.stdout);
      }
      const selected = command("select");
      command("start", ["--mode", mode]);
      assert.equal(command("advance").task_id, selected.id);
      const crypto = require("node:crypto");
      const hash = crypto.createHash("sha256").update(fs.readFileSync(path.join(target, "source.cs"))).digest("hex");
      command("complete", [], {
        task_id: selected.id,
        outcome: "The fixture preserves isolated state.",
        acceptance: [{ criterion: "Preserve isolated state.", result: "pass", evidence: ["test-report.json"] }],
        source_fingerprints: { "source.cs": hash }
      });
      command("finish");
      assert.equal(command("index").active_run, null);
      assert.equal(command("history", ["--id", selected.id])[0].disposition, "completed");
      assert.ok(fs.existsSync(path.join(target, "skill-tree", "skill-tree.json")));
    } finally { fs.rmSync(target, { recursive: true, force: true }); }
  });
}

test("explicit local source accepts the reorganized repository root", () => {
  const target = tmpdir();
  try {
    const result = run(["--source", path.dirname(root), "--only", "codex", "--project", "--target", target, "--copy", "--skills", "skill-tree-add-pending-task"]);
    assert.equal(result.status, 0, result.stderr);
    assert.ok(fs.existsSync(path.join(target, ".agents", "skills", "skill-tree-add-pending-task", "SKILL.md")));
  } finally { fs.rmSync(target, { recursive: true, force: true }); }
});
