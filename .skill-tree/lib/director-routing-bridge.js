"use strict";

const fs = require("node:fs");
const path = require("node:path");
const composer = require("./composer.js");

const BEGIN = "<!-- BEGIN skill-tree-director-routing -->";
const END = "<!-- END skill-tree-director-routing -->";
const workflowGuidance = [
  'For fresh managed implementation, preview Full Cycle through `project-route` with `"operation": "skill-tree-full-cycle"` before creating a branch or editing product files.',
  "For queue-only intake, use `intake`. For inspection, use `project-read`. For existing prioritized work, route the exact task or approved group through the requested implementation operation.",
  "Begin scoped source edits after Core admits the exact task and isolated worktree. Follow the owner's separate publication and merge authorization."
];
const previousBlock = [
  BEGIN,
  "For requests about a project in this workspace, use the Skill Tree Director first.",
  "Read `.skill-tree/.director/workspace.json` and invoke the installed Setup entry named in `setup_entry`. Run `project-route` before opening a product queue, reading project files, or choosing a child skill. Use `project-menu` to discover projects and available setup actions.",
  "Use `project-read` even for an ordinary README question. Read from the exact checkout returned by `project-route`. A failed route is a Director prerequisite to report before continuing the request.",
  "In Codex, the Setup entry is normally `.skill-tree/.director/.agents/skills/skill-tree-director-setup/scripts/director-entry.py`. For example, run `python3 -B .skill-tree/.director/.agents/skills/skill-tree-director-setup/scripts/director-entry.py project-menu .skill-tree/.director`.",
  "For example, run `printf '%s\\n' '{\"operation\":\"status\"}' | python3 -B .skill-tree/.director/.agents/skills/skill-tree-director-setup/scripts/director-entry.py project-route .skill-tree/.director --input /dev/stdin`. Use `project-read` for a general question, `discovery` for capabilities, and the exact operation or skill identifier otherwise.",
  "Omit `project_id` when the request names no project so the route can select the co-located project. If the route asks for a selection, use the exact intended project from the menu.",
  "Execute the returned `entry`, `command`, and `input` for status and audit. Use `status` for one project, `workspace-status` for all projects, and `audit` for workspace audit. Use an exact project ID to focus an audit. A run-specific audit or diagnosis takes an exact selector. Report actual child audit results.",
  "Treat an unlabeled request to add, process, or implement tasks as a Director request. Follow the authorized objective and exact assignment route. For grouped work report the exact selection and any blocked assignment.",
  "Use direct Core only when the owner explicitly requests it. Pass `route: \"direct\"` to preview that choice and use `--direct-project` for direct queue writes. The route preview grants no effect permissions.",
  END
].join("\n");
const block = previousBlock.slice(0, -END.length) + workflowGuidance.join("\n") + "\n" + END;

function blockBounds(bytes) {
  const start = bytes.indexOf(BEGIN);
  const end = bytes.indexOf(END);
  if (start < 0 && end < 0) return null;
  const limit = end + Buffer.byteLength(END);
  const ownedBlock = bytes.subarray(start, limit).toString("utf8");
  if (start < 0 || end < start || bytes.indexOf(BEGIN, start + Buffer.byteLength(BEGIN)) >= 0 ||
      bytes.indexOf(END, limit) >= 0 || ![block, previousBlock].includes(ownedBlock)) {
    throw Error("Director routing instructions conflict with the installed block");
  }
  const head = bytes.subarray(Math.max(0, start - 2), start).equals(Buffer.from("\n\n")) ? start - 2 : start;
  const tail = bytes[limit] === 10 ? limit + 1 : limit;
  return {start, limit, head, tail, hadFile: head !== start, previous: ownedBlock === previousBlock};
}

function read(file) {
  const stat = fs.lstatSync(file, {throwIfNoEntry:false});
  if (!stat) return null;
  if (!stat.isFile() || stat.isSymbolicLink()) throw Error("Select a regular Director routing instruction file");
  return fs.readFileSync(file);
}

function destinations(hosts) {
  return new Set(hosts.map(host => host.bridgePath).filter(Boolean));
}

function plan(workspace, previous, selected, {verify = false} = {}) {
  const oldPaths = destinations(previous);
  const present = destinations(selected);
  const changes = [];
  for (const relative of new Set([...oldPaths, ...present])) {
    const file = fs.existsSync(workspace) ? composer.safe(workspace, relative) : path.join(workspace, relative);
    const before = read(file);
    const existing = before ? blockBounds(before) : null;
    if (existing && !oldPaths.has(relative)) throw Error("An existing Director routing block needs ownership inspection: " + relative);
    if (present.has(relative)) {
      if (!existing && verify) throw Error("Missing owned Director routing instructions: " + relative);
      if (!existing) {
        const separator = before === null ? "" : "\n\n";
        const content = Buffer.concat([before || Buffer.alloc(0), Buffer.from(separator + block + "\n")]);
        changes.push({file, before, content});
      } else if (existing.previous) {
        if (verify) throw Error("Director routing instructions need a workspace update: " + relative);
        const content = Buffer.concat([
          before.subarray(0, existing.start), Buffer.from(block), before.subarray(existing.limit)
        ]);
        changes.push({file, before, content});
      }
    } else if (existing) {
      const content = Buffer.concat([before.subarray(0, existing.head), before.subarray(existing.tail)]);
      changes.push({file, before, content: content.length || existing.hadFile ? content : null});
    }
  }
  return changes;
}

function apply(changes) {
  for (const {file, before, content} of changes) {
    const current = read(file);
    if (before === null ? current !== null : !current?.equals(before)) {
      throw Error("Director routing instructions changed during setup: " + file);
    }
    if (content === null) {
      fs.unlinkSync(file);
      continue;
    }
    fs.mkdirSync(path.dirname(file), {recursive:true});
    if (before === null) {
      fs.writeFileSync(file, content, {flag:"wx"});
      continue;
    }
    const stage = fs.mkdtempSync(path.join(path.dirname(file), ".director-routing-"));
    try {
      const staged = path.join(stage, "instructions");
      const mode = fs.statSync(file).mode & 0o7777;
      fs.writeFileSync(staged, content, {mode});
      fs.chmodSync(staged, mode);
      if (!read(file)?.equals(before)) throw Error("Director routing instructions changed during setup: " + file);
      fs.renameSync(staged, file);
    } finally {
      fs.rmSync(stage, {recursive:true, force:true});
    }
  }
}

module.exports = {plan, apply, workflowGuidance};
