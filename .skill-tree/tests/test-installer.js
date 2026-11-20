const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
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
  if(!args.includes("--help")&&!args.includes("--list")&&!args.includes("--flavor"))args=["--flavor","general",...args];
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
  assert.match(result.stdout, /general, web, unity/);

  assert.match(result.stdout, /skill-tree-create-documents-snapshot/);
  assert.match(result.stdout, /skill-tree-add-pending-task/);

});

test("dry-run all succeeds without installing", () => {
  const target = tmpdir();
  const result = run(["--dry-run", "--all", "--project", "--target", target]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /dry-run/);
  assert.equal(fs.existsSync(path.join(target, ".agents", "skills", "skill-tree-repo-documentation")), false);
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
    for (const file of ["references/pending-task-intake.md", "references/pending-task-format.md"]) {
      assert.deepEqual(fs.readFileSync(path.join(installed, file)), fs.readFileSync(path.join(root, "skills", "general", name, file)));
    }
    assert.deepEqual(fs.readdirSync(path.join(target, ".agents", "skills")), [name]);
    const verified = run(["--verify", "--only", "codex", "--project", "--target", target, "--skills", name]);
    assert.equal(verified.status, 0, verified.stderr);
  } finally {
    fs.rmSync(target, { recursive: true, force: true });
  }
});

test("global specialization is rejected without touching HOME", () => {
  const home=tmpdir();try{const result=run(["--only","claude-code","--global","--copy"],{env:{HOME:home}});assert.notEqual(result.status,0);assert.equal(fs.existsSync(path.join(home,".claude")),false);}finally{fs.rmSync(home,{recursive:true,force:true});}
});

test("copy mode refuses overwrite without force and force replaces", () => {
  const target = tmpdir();
  let result = run(["--only", "codex", "--project", "--target", target, "--copy", "--skills", "skill-tree-repo-documentation"]);
  assert.equal(result.status, 0, result.stderr);
  result = run(["--only", "codex", "--project", "--target", target, "--copy", "--skills", "skill-tree-repo-documentation"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /current|no-op/);
  result = run(["--only", "codex", "--project", "--target", target, "--copy", "--force", "--skills", "skill-tree-repo-documentation"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /current|no-op/);
});

test("symlink specialization is rejected before writes", () => {
 const target=tmpdir();try{const result=run(["--only","codex","--target",target,"--symlink"]);assert.notEqual(result.status,0);assert.equal(fs.existsSync(path.join(target,".skill-tree")),false);}finally{fs.rmSync(target,{recursive:true,force:true});}
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
  assert.ok(fs.existsSync(path.join(target, ".skill-tree/installation/.backups")));
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

test("owned manager regenerates only a missing registered AGENTS.md", () => {
  const target = fs.realpathSync(tmpdir());
  const name = "skill-tree-implement-all";
  const bridge = path.join(target, "AGENTS.md");
  const state = path.join(target, ".skill-tree/documents/future.json");
  const owned = path.join(target, ".agents/skills", name, "SKILL.md");
  const local = (...args) => spawnSync(process.execPath, [path.join(target, ".skill-tree/installation/manager.js"), ...args],
    { cwd: target, encoding: "utf8", timeout: 15000 });
  const workflow = (...args) => spawnSync("python3", ["-B", path.join(target, ".agents/skills", name, "scripts/workflow-state.py"), ...args],
    { cwd: target, encoding: "utf8", timeout: 15000 });
  const output = result => result.stdout + result.stderr;
  function inventory(directory = target, relative = "", result = {}) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const key = relative + entry.name;
      if (key === "AGENTS.md") continue;
      const full = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        result[key] = "directory";
        inventory(full, key + "/", result);
      } else {
        result[key] = createHash("sha256").update(fs.readFileSync(full)).digest("hex");
      }
    }
    return result;
  }
  try {
    fs.writeFileSync(bridge, "# Repository-specific rules\n\nDeliberately discarded instructions.\n");
    let result = run(["--only", "codex", "--target", target, "--with-init", "--skills", name]);
    assert.equal(result.status, 0, output(result));
    const original = fs.readFileSync(bridge, "utf8");
    const begin = original.indexOf("<!-- BEGIN skill-tree-skills -->");
    assert(begin >= 0);
    const generated = original.slice(begin);
    assert.equal(spawnSync("git", ["init", "--quiet", target]).status, 0);
    fs.mkdirSync(path.dirname(state), {recursive:true});
    fs.writeFileSync(path.join(path.dirname(state), "future.md"),
      "# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n");
    const request = path.join(target, "request.json");
    fs.writeFileSync(request, JSON.stringify({title:"Retain work",description:"Preserve pending work.",
      expected_behavior:"The fixture queue keeps the original task."}));
    result = workflow("intake", target, "--input", request);
    assert.equal(result.status, 0, output(result));
    result = workflow("workspace-setup", target);
    assert.equal(result.status, 0, output(result));
    const exactState = fs.readFileSync(state);
    const stored = JSON.parse(exactState);
    assert.equal(stored.schema, 3);
    assert.equal(stored.tasks.length, 1);
    const history = path.join(target, ".skill-tree/history");
    fs.mkdirSync(history, {recursive:true});
    fs.writeFileSync(path.join(history, "retained.json"), '{"status":"historical"}\n');
    fs.mkdirSync(path.join(target, "work/empty"), {recursive:true});
    fs.writeFileSync(path.join(target, "work/unrelated.txt"), "Owner file.\n");
    const before = inventory();

    fs.unlinkSync(bridge);
    result = local("--verify");
    assert.notEqual(result.status, 0, output(result));
    assert.match(output(result), /Modified or missing owned bridge: AGENTS.md/);
    result = local("--regenerate-agents", "--dry-run");
    assert.equal(result.status, 0, output(result));
    assert.deepEqual(JSON.parse(result.stdout).changed, ["AGENTS.md"]);
    assert.equal(fs.existsSync(bridge), false);
    assert.deepEqual(inventory(), before);

    const installedBytes = fs.readFileSync(owned);
    fs.appendFileSync(owned, "\nCompeting package edit.\n");
    result = local("--regenerate-agents");
    assert.notEqual(result.status, 0, output(result));
    assert.match(output(result), /locally modified package/);
    assert.equal(fs.existsSync(bridge), false);
    fs.unlinkSync(owned);
    result = local("--regenerate-agents", "--dry-run");
    assert.notEqual(result.status, 0, output(result));
    assert.match(output(result), /skill-tree-implement-all\/SKILL\.md/);
    fs.writeFileSync(owned, installedBytes);

    const receipt = path.join(target, ".skill-tree/installation/profile.json");
    const installedProfile = fs.readFileSync(receipt);
    const unregistered = JSON.parse(installedProfile);
    delete unregistered.bridges["AGENTS.md"];
    fs.writeFileSync(receipt, JSON.stringify(unregistered));
    result = local("--regenerate-agents", "--dry-run");
    assert.notEqual(result.status, 0, output(result));
    assert.match(output(result), /No owned Codex bridge is registered/);
    fs.writeFileSync(receipt, installedProfile);

    const rid = "WR-cedae5ca-1e04-49df-b652-c86d5ef427bc";
    stored.run_registry.runs[rid] = {id:rid, phase:"implement"};
    fs.writeFileSync(state, JSON.stringify(stored));
    result = local("--regenerate-agents", "--dry-run");
    assert.notEqual(result.status, 0, output(result));
    assert.match(output(result), /Active controller/);
    assert.equal(fs.existsSync(bridge), false);
    fs.writeFileSync(state, exactState);

    const journal = path.join(target, ".skill-tree/installation/.journal.json");
    fs.writeFileSync(journal, '{"schema":1,"entries":[]}\n');
    result = local("--regenerate-agents");
    assert.notEqual(result.status, 0, output(result));
    assert.match(output(result), /recovery is required/i);
    assert.equal(fs.readFileSync(journal, "utf8"), '{"schema":1,"entries":[]}\n');
    assert.equal(fs.existsSync(bridge), false);
    fs.unlinkSync(journal);

    const fault = path.join(target, "stage-fault.cjs");
    fs.writeFileSync(fault, `
      const fs = require("node:fs");
      const open = fs.openSync;
      const writeFile = fs.writeFileSync;
      let staged, descriptor;
      fs.openSync = function(file, ...args) {
        const fd = open(file, ...args);
        if (typeof file === "string" && file.includes(".skill-tree-agents-recovery-") && file.endsWith("AGENTS.md")) {
          staged = file;
          descriptor = fd;
        }
        return fd;
      };
      fs.writeFileSync = function(file, ...args) {
        writeFile(file, ...args);
        if (file !== descriptor || !staged) return;
        if (process.env.SKILL_TREE_TEST_STAGE_REPLACEMENT) {
          fs.unlinkSync(staged);
          fs.symlinkSync(process.env.SKILL_TREE_TEST_STAGE_REPLACEMENT, staged);
        } else writeFile(staged, "Damaged staged file.\\n");
      };
    `);
    const regenerateWithFault = (env = process.env) => spawnSync(process.execPath,
      ["--require", fault, path.join(target, ".skill-tree/installation/manager.js"), "--regenerate-agents"],
      { cwd: target, encoding: "utf8", timeout: 15000, env });
    result = regenerateWithFault();
    assert.notEqual(result.status, 0, output(result));
    assert.match(output(result), /Staged AGENTS.md bytes changed before publication/);
    assert.equal(fs.existsSync(bridge), false);
    if (process.platform !== "win32") {
      const sameBytes = path.join(target, "work", "matching-content.txt");
      fs.writeFileSync(sameBytes, generated);
      result = regenerateWithFault({ ...process.env, SKILL_TREE_TEST_STAGE_REPLACEMENT: sameBytes });
      assert.notEqual(result.status, 0, output(result));
      assert.match(output(result), /Staged AGENTS.md file identity changed before publication/);
      assert.equal(fs.existsSync(bridge), false);
      assert.equal(fs.statSync(sameBytes).nlink, 1);
      assert.equal(fs.readFileSync(sameBytes, "utf8"), generated);
      fs.unlinkSync(sameBytes);
    }
    fs.unlinkSync(fault);
    assert.deepEqual(inventory(), before);

    if (process.platform !== "win32") {
      fs.symlinkSync("unavailable-file.md", bridge);
      result = local("--regenerate-agents");
      assert.notEqual(result.status, 0, output(result));
      assert.equal(fs.readlinkSync(bridge), "unavailable-file.md");
      fs.unlinkSync(bridge);
    }
    result = local("--regenerate-agents");
    assert.equal(result.status, 0, output(result));
    assert.equal(fs.readFileSync(bridge, "utf8"), generated);
    assert.deepEqual(inventory(), before);
    assert.equal(local("--verify").status, 0);

    fs.writeFileSync(bridge, "New owner instructions.\n");
    result = local("--regenerate-agents");
    assert.notEqual(result.status, 0, output(result));
    assert.match(output(result), /AGENTS.md already exists/);
    assert.equal(fs.readFileSync(bridge, "utf8"), "New owner instructions.\n");
  } finally {
    fs.rmSync(target, {recursive:true,force:true});
  }
});

test("verify mode detects installed skill", () => {
  const target = tmpdir();
  let result = run(["--only", "codex", "--project", "--target", target, "--copy", "--skills", "skill-tree-implement-next-future-task"]);
  assert.equal(result.status, 0, result.stderr);
  result = run(["--verify", "--only", "codex", "--project", "--target", target, "--skills", "skill-tree-implement-next-future-task"]);
  assert.equal(result.status, 0, result.stderr);
});

test("reported missing installation inputs have usable recovery guidance", () => {
  const target = tmpdir();
  const args = ["--only", "codex", "--target", target, "--with-init", "--skills", "skill-tree-process-future-pending"];
  try {
    const installed = run(args);
    assert.equal(installed.status, 0, installed.stdout + installed.stderr);
    const cases = [
      [".skill-tree/installation/profile.json", /restore the matching ownership receipt/i],
      [".agents/skills/skill-tree-process-future-pending/SKILL.md", /restore the matching owned package/i],
      [".skill-tree/installation/source/src/init-rules/skill-tree-skills.md", /restore the missing file from the matching maintenance generation/i],
      ["AGENTS.md", /restore the registered instruction file/i],
    ];
    for (const [relative, guidance] of cases) {
      const file = path.join(target, relative);
      const saved = fs.readFileSync(file);
      fs.unlinkSync(file);
      try {
        for (const mode of ["--verify", "--dry-run"]) {
          const result = run([...args, mode]);
          const output = result.stdout + result.stderr;
          assert.notEqual(result.status, 0, output);
          assert.ok(output.includes(relative), output);
          assert.match(output, guidance);
          assert.equal(fs.existsSync(file), false);
        }
      } finally {
        fs.writeFileSync(file, saved);
      }
    }
    assert.equal(run([...args, "--verify"]).status, 0);
  } finally {
    fs.rmSync(target, { recursive: true, force: true });
  }
});

test("composition names the missing authored resource behind a declared output", () => {
  const source = tmpdir();
  try {
    for (const directory of ["config", "templates", "domains", "common"]) {
      fs.cpSync(path.join(root, directory), path.join(source, directory), { recursive: true });
    }
    const relative = "common/references/snapshot-rules.md";
    const input = path.join(source, relative);
    const bytes = fs.readFileSync(input);
    fs.unlinkSync(input);
    const composer = require("../lib/composer.js");
    const profile = { flavor: "general", facts: {}, recipes: {}, gaps: [] };
    assert.throws(() => composer.compose(source, profile, ["skill-tree-create-documents-snapshot"]), {
      message: /Restore the referenced source file: common\/references\/snapshot-rules\.md/,
    });
    assert.equal(fs.existsSync(input), false);
    fs.writeFileSync(input, bytes);
    fs.unlinkSync(path.join(source, "config/resource-map.json"));
    assert.throws(() => composer.compose(source, profile, ["skill-tree-create-documents-snapshot"]), {
      message: /Missing composition input: config\/resource-map\.json\. Restore the matching source file/,
    });
  } finally {
    fs.rmSync(source, { recursive: true, force: true });
  }
});

test("uninstall removes selected skill only", () => {
  const target = tmpdir();
  let result = run(["--only", "codex", "--project", "--target", target, "--copy"]);
  assert.equal(result.status, 0, result.stderr);
  result = run(["--uninstall", "--only", "codex", "--project", "--target", target, "--skills", "skill-tree-process-future-pending"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(fs.existsSync(path.join(target, ".agents", "skills", "skill-tree-process-future-pending")), false);
  assert.ok(fs.existsSync(path.join(target, ".agents", "skills", "skill-tree-repo-documentation", "SKILL.md")));
});

test("upstream paths reject uncomposed installation", () => {
 const result=run(["--dry-run","--agent","qwen-code","--source","https://github.com/example/repo","--skills","skill-tree-process-future-pending"]);
 assert.notEqual(result.status,0);assert.match(result.stderr,/unsupported/);
});

test("partial provider failure returns non-zero and keeps other rows", () => {
  const target = tmpdir();
  const fileDest = path.join(target, "not-a-directory");
  fs.writeFileSync(fileDest, "x", "utf8");
  const result = run(["--only", "codex", "--only", "generic", "--project", "--target", fileDest, "--copy", "--skills", "skill-tree-process-future-pending"]);
  assert.notEqual(result.status,0);
  assert.match(result.stderr+result.stdout,/directory|ENOTDIR/);
});

for (const [name, mode] of [["skill-tree-work-through-next", "next"], ["skill-tree-implement-all", "all"]]) {
  test(`${name} installs alone and completes a temporary fixture run`, () => {
    const target = tmpdir();
    try {
      const installation = run(["--only", "codex", "--project", "--target", target, "--copy", "--skills", name]);
      assert.equal(installation.status, 0, installation.stderr);
      assert.deepEqual(fs.readdirSync(path.join(target, ".agents", "skills")), [name]);
      const docs = path.join(target, ".skill-tree", "documents");
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
      command("begin", [], {task_id:selected.id});
      const attempt=command("prepare-check", [], {task_id:selected.id,check_id:"behavior"});
      command("record-check", [], {task_id:selected.id,check_id:"behavior",attempt_id:attempt.attempt_id,result:"pass",classification:"executed-control",actual_lane:"static",environment_identity:attempt.environment_identity,assertions:[{assertion:"Preserve isolated state.",result:"pass"}],cleanup:"No product process was launched.",evidence:["test-report.json"]});
      command("implemented", [], {task_id:selected.id});
      command("complete", [], {
        task_id: selected.id,
        outcome: "The fixture preserves isolated state.",
        acceptance: [{ criterion: "Preserve isolated state.", result: "pass", evidence: ["test-report.json"] }],
        source_fingerprints: { "source.cs": hash }
      });
      command("finish");
      assert.equal(command("index").active_run, null);
      assert.equal(command("history", ["--id", selected.id])[0].disposition, "completed");
      assert.ok(fs.existsSync(path.join(target, ".skill-tree", "skill-tree.json")));
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
test('root shell launcher exposes the composed logical catalog and PowerShell points to the owned entrypoint',()=>{
 const result=spawnSync('sh',[path.join(root,'../install.sh'),'--list'],{encoding:'utf8',timeout:10000});assert.equal(result.status,0,result.stderr);assert.match(result.stdout,/Flavors: general, web, unity/);assert.match(result.stdout,/skill-tree-work-through-next/);assert.match(fs.readFileSync(path.join(root,'../install.ps1'),'utf8'),/\.skill-tree\/bin\/install\.js/);
});
