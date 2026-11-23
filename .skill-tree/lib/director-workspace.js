"use strict";

const fs = require("node:fs");
const path = require("node:path");
const {spawnSync} = require("node:child_process");
const composer = require("./composer.js");
const manager = require("./installation.js");

const directorFolder = ".skill-tree-director";
const launcher = "skill-tree-director";

function relativePackage(provider, name) {
  return path.posix.join(provider.id === "generic" ? "." : provider.projectPath, name);
}

function launcherText(location) {
  return [
    "---", "name: skill-tree-director",
    "description: Open Director Setup to connect an existing project, create a new project, or inspect the coordinator.",
    "---", "", "# Skill Tree Director", "",
    "Run commands from this workspace. Ask whether to connect an existing project, create a new one or continue later.",
    "For an existing project, ask for its folder. For a new project, ask for a name and offer the named folder in the workspace, or a custom location.",
    "Use a portable lowercase project name. Pass a JSON request containing kind (existing or new), name, optional path and optional flavor.",
    "Run the following read-only command with the request. Show the proposed path, profile and hosts. Once the user chooses the project, run project-setup with the same input.",
    "", "```sh", `python3 "${location}" project-preview .skill-tree-director --input <request.json>`, "```", "",
    "To check the available actions, run project-menu in place of project-preview and omit --input.", ""
  ].join("\n");
}

function workspacePath(location) {
  let anchor = path.resolve(location);
  const missing = [];
  while (!fs.lstatSync(anchor, {throwIfNoEntry:false})) {
    missing.unshift(path.basename(anchor));
    anchor = path.dirname(anchor);
  }
  if (!fs.statSync(anchor).isDirectory()) throw Error("Select a workspace directory");
  return path.join(fs.realpathSync(anchor), ...missing);
}

function ownedPath(workspace, relative) {
  if (fs.existsSync(workspace)) return composer.safe(workspace, relative);
  // With no directory to inspect, validate lexical containment without creating it.
  const target = path.resolve(workspace, relative);
  const child = path.relative(workspace, target);
  if (!child || child === ".." || child.startsWith(".." + path.sep) || path.isAbsolute(child)) {
    throw Error("Director destination must be inside the workspace");
  }
  return target;
}

function checkLauncher(workspace, provider, expected) {
  const folder = ownedPath(workspace, relativePackage(provider, launcher));
  const file = path.join(folder, "SKILL.md");
  if (fs.existsSync(folder) && (!fs.existsSync(file) || fs.lstatSync(file).isSymbolicLink() ||
      fs.readFileSync(file, "utf8") !== expected || fs.readdirSync(folder).length !== 1)) {
    throw Error("Director launcher conflicts with an existing package: " + folder);
  }
  return file;
}

function servicePath(workspace) {
  return ownedPath(workspacePath(workspace), directorFolder);
}

function directFlavor(workspace) {
  const file = path.join(workspace, manager.PROFILE);
  if (!fs.existsSync(file)) return null;
  return composer.readJson(workspace, manager.PROFILE)?.flavor || null;
}

function installDirector(workspace, source, providers, {dryRun = false, verify = false} = {}) {
  const canonical = workspacePath(workspace);
  const home = ownedPath(canonical, directorFolder);
  const reference = path.join(home, "workspace.json");
  if (fs.existsSync(reference) && fs.lstatSync(reference).isSymbolicLink()) throw Error("Select an owned Director workspace descriptor");
  const previous = fs.existsSync(reference) ? composer.readJson(home, "workspace.json") : null;
  if (previous && (previous.schema !== 1 || previous.kind !== "director-workspace" || !Array.isArray(previous.providers))) {
    throw Error("Unrecognized Director workspace descriptor: " + reference);
  }
  if (!previous && fs.existsSync(home) && fs.readdirSync(home).length) throw Error("Existing Director directory needs inspection: " + home);
  if (verify && !previous) throw Error("Dedicated Director installation is missing: " + home);
  if (verify && providers.some(host => !previous.providers.includes(host.id))) throw Error("Selected host is missing from the Director workspace");
  const matrix = composer.readJson(source, "config/providers.json").providers;
  const selected = [...new Set([...(previous?.providers || []), ...providers.map(provider => provider.id)])].map(id => {
    const item = matrix.find(provider => provider.id === id);
    if (!item) throw Error("Recorded Director host is unavailable: " + id);
    return item;
  });
  const names = composer.operationNames(source, "director");
  const selections = selected.flatMap(host => names.map(name => ({name, provider: host.id, rel: relativePackage(host, name)})));
  const setup = relativePackage(selected[0], "skill-tree-director-setup") + "/scripts/director-entry.py";
  const descriptor = {schema: 1, kind: "director-workspace", providers: selected.map(host => host.id), setup_entry: setup};
  const entries = selected.map(host => {
    const content = launcherText(path.posix.join(directorFolder, relativePackage(host, "skill-tree-director-setup"), "scripts/director-entry.py"));
    return {file: checkLauncher(canonical, host, content), content};
  });
  const message = `Director ${dryRun ? "preview" : "ready"} at ${home}\nOpen ${canonical} in ${selected.map(item => item.label).join(", ")} and invoke skill-tree-director.\nConnect an existing project, create a new project, or continue later.`;
  if (verify) {
    const receipt = manager.verify(home, path.join(home, ".skill-tree/installation/source"));
    if (receipt.flavor !== "director" || previous.setup_entry !== setup ||
        !selections.every(({name, provider, rel}) => {
          const item = receipt.destinations[rel];
          return item?.name === name && (item.providers || [item.provider]).includes(provider);
        })) throw Error("Dedicated Director receipt does not match its workspace descriptor");
    if (entries.some(({file}) => !fs.existsSync(file))) throw Error("An installed Director launcher is missing");
    return "Director verified at " + home;
  }
  if (dryRun) {
    if (fs.existsSync(home)) manager.install(home, source, "director", selections, {dryRun: true});
    return message;
  }
  fs.mkdirSync(home, {recursive: true});
  if (fs.realpathSync(home) !== home) throw Error("Director workspace changed during creation");
  const lock = path.join(home, ".setup-lock");
  let fd;
  try {
    fd = fs.openSync(lock, "wx");
  } catch (error) {
    if (error.code === "EEXIST") throw Error("Another Director installation owns " + lock + ". If it was interrupted, inspect the workspace and remove the abandoned lock before retrying.");
    throw error;
  }
  fs.writeFileSync(fd, String(process.pid) + "\n");
  try {
    // The descriptor identifies a partially prepared workspace on a safe retry.
    if (!previous) fs.writeFileSync(reference, JSON.stringify(descriptor, null, 2) + "\n", {flag: "wx"});
    manager.install(home, source, "director", selections);
    manager.verify(home, source);
    if (previous) {
      const scratch = fs.mkdtempSync(path.join(home, ".descriptor-"));
      try {
        fs.writeFileSync(path.join(scratch, "workspace.json"), JSON.stringify(descriptor, null, 2) + "\n");
        fs.renameSync(path.join(scratch, "workspace.json"), reference);
      } finally { fs.rmSync(scratch, {recursive:true, force:true}); }
    }
    const init = spawnSync(process.env.PYTHON || "python3", ["-B", path.join(home, setup), "project-init", home],
      {encoding:"utf8", timeout:120000});
    if (init.error || init.status !== 0) throw Error(init.error?.message || init.stdout || init.stderr);
    for (const {file, content} of entries) {
      if (fs.existsSync(file)) continue;
      fs.mkdirSync(path.dirname(file), {recursive:true});
      fs.writeFileSync(file, content, {flag:"wx"});
    }
  } finally {
    fs.closeSync(fd);
    fs.unlinkSync(lock);
  }
  return message;
}

module.exports = {installDirector, servicePath, directFlavor};
