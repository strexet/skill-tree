const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const cli = path.join(root, "bin", "install.js");

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "unity-skills-test-"));
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
  assert.match(result.stdout, /skill-tree-unity-repo-documentation/);
  assert.match(result.stdout, /skill-tree-unity-repo-documentation-audit/);
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
  assert.equal((text.match(/BEGIN unity-repository-skills/g) || []).length, 1);
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
  assert.equal(text.includes("BEGIN unity-repository-skills"), false);
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
