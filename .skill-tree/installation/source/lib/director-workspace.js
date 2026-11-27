"use strict";

const fs = require("node:fs");
const path = require("node:path");
const {spawnSync} = require("node:child_process");
const composer = require("./composer.js");
const manager = require("./installation.js");
const routing = require("./director-routing-bridge.js");

const directorFolder = ".skill-tree/.director";
const legacyFolder = ".skill-tree-director";
const relocationJournal = ".director-relocation.json";
const launcher = "skill-tree-director";

function relativePackage(provider, name) {
  return path.posix.join(provider.id === "generic" ? "." : provider.projectPath, name);
}

function legacyLauncherText(location) {
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

function previousLauncherText(location, home) {
  return [
    "---", "name: skill-tree-director",
    "description: Route shared-workspace task intake, processing, implementation, status and audit through Director. Connect or manage projects.",
    "---", "", "# Skill Tree Director", "",
    "Open the current workspace menu before choosing an action.", "", "```sh",
    `python3 "${location}" project-menu ${home}`, "```", "",
    "For registered projects offer objective intake, status, audit or project setup. Use the corresponding installed Director skill under the service directory. For a new workspace offer existing project, new project or later.",
    "For ordinary task intake, processing or implementation use project-route with a JSON object containing operation (intake, process, implement-next or implement-all) and optional project_id and task_ids.",
    "Show the receiving project, queue and task scope from the preview. If the Core route requires an upgrade, use project-setup with the original registration choice and the authorized installation handoff.",
    "Use the existing objective, plan and assignment route. A Director dispatch takes one exact task per assignment. Surface any unsupported grouped launch before acting.",
    "When the owner explicitly selects direct Core work, preview with route set to direct, show the same scope and invoke the Core CLI with --direct-project.",
    "For project setup, use project-preview with kind (existing or new), name, optional path and flavor. On selection use project-setup with the same request.",
    ""
  ].join("\n");
}

function launcherText(location, {previous = false} = {}) {
  return [
    "---", "name: skill-tree-director",
    "description: Route project requests through the registered Skill Tree Director workspace.",
    "---", "", "# Skill Tree Director", "",
    "Use the workspace menu to discover registered projects, or route a known operation directly through Setup.", "", "```sh",
    `python3 -B "${location}" project-menu ${directorFolder}`, "```", "",
    "Run `project-route` with the requested operation or installed skill ID before inspecting project files or queues. Even a simple README lookup requires `project-read` and the checkout chosen by Director. Use `discovery` for capabilities. An unnamed request uses the co-located project when one is registered.",
    "Use the returned entry, command, input and project scope. Grouped task dispatch requires one exact task per authorized assignment. Use direct Core only on an explicit owner request.",
    ...(previous ? [] : routing.workflowGuidance),
    "To connect a project, use `project-preview` with `kind` (existing or new), `name`, and optional `path` and `flavor`. Use `project-setup` with the same approved request.",
    ""
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

function checkLauncher(workspace, provider, expected, legacy = [], removing = false) {
  const folder = ownedPath(workspace, relativePackage(provider, launcher));
  const file = path.join(folder, "SKILL.md");
  if (removing && fs.existsSync(folder) && !fs.readdirSync(folder).length) return file;
  if (fs.existsSync(folder) && (!fs.existsSync(file) || !fs.lstatSync(file).isFile() ||
      ![expected, ...legacy].includes(fs.readFileSync(file, "utf8")) || fs.readdirSync(folder).length !== 1)) {
    throw Error("Director launcher conflicts with an existing package: " + folder);
  }
  return file;
}

function workspaceLocations(workspace) {
  const canonical = workspacePath(workspace);
  const home = ownedPath(canonical, directorFolder);
  const legacy = ownedPath(canonical, legacyFolder);
  if (fs.existsSync(home) && fs.existsSync(legacy)) {
    throw Error("Resolve the conflicting Director storage locations before continuing");
  }
  return {canonical, home, legacy, current: fs.existsSync(legacy) ? legacy : home};
}

function servicePath(workspace) {
  return workspaceLocations(workspace).current;
}

function workspaceDescriptor(workspace) {
  return fs.existsSync(path.join(servicePath(workspace), "workspace.json"));
}

function legacyLaunchers(location) {
  return [previousLauncherText(location, legacyFolder), legacyLauncherText(location)];
}

function relocation(workspace, phase) {
  const result = spawnSync(process.env.PYTHON || "python3",
    ["-B", path.join(__dirname, "../common/scripts/director-workspace-migration.py"), phase, workspace],
    {encoding:"utf8", timeout:120000});
  if (result.error || result.status !== 0) throw Error(result.error?.message || result.stdout || result.stderr);
  return JSON.parse(result.stdout);
}

function installSourceSupportsLayout(source) {
  const setup = composer.read(source, "common/scripts/director-state.py");
  if (!setup?.includes("DIRECTOR_HOME = Path('.skill-tree/.director')")) {
    throw Error("Select a Skill Tree package source that supports .skill-tree/.director");
  }
}

function inspectOwnedWorkspace(canonical, home, previous, source) {
  const {co_located: coLocated} = relocation(canonical, "inspect");
  if (previous !== home) {
    const legacyProfile = manager.verify(previous, path.join(previous, ".skill-tree/installation/source"));
    if (legacyProfile.flavor !== "director") throw Error("Legacy Director ownership could not be verified");
    const maintenance = path.join(previous, "sources/skill-tree");
    if (fs.lstatSync(path.join(maintenance, manager.PROFILE), {throwIfNoEntry:false})) {
      manager.verify(maintenance, path.join(maintenance, ".skill-tree/installation/source"));
    }
  }
  if (!coLocated) return null;
  const profile = manager.verify(canonical, path.join(canonical, ".skill-tree/installation/source"));
  if (profile.flavor === "director") throw Error("The co-located project requires its own Core profile");
  const planned = manager.plan(canonical, source, profile.flavor, []);
  if (Object.hasOwn(planned.changes, ".skill-tree/documents/future.json")) {
    throw Error("Finish the retained co-located Core work before moving Director storage");
  }
  return profile.flavor;
}

function moveOwnedWorkspace(canonical, home, productFlavor, source) {
  if (productFlavor) {
    manager.install(canonical, source, productFlavor, [], {
      recoverPending: false,
      recoverPluginPending: false,
      guardPlan(plan) {
        if (Object.hasOwn(plan.changes, ".skill-tree/documents/future.json")) {
          throw Error("Finish the retained co-located Core work before moving Director storage");
        }
      }
    });
  }
  relocation(canonical, "move");
  for (const root of [home, path.join(home, "sources/skill-tree")]) {
    if (!fs.existsSync(path.join(root, manager.PROFILE))) continue;
    manager.rebind(root, path.join(root, ".skill-tree/installation/source"));
  }
}

function directFlavor(workspace) {
  const file = path.join(workspace, manager.PROFILE);
  if (!fs.existsSync(file)) return null;
  return composer.readJson(workspace, manager.PROFILE)?.flavor || null;
}

function readDescriptor(home) {
  const reference = path.join(home, "workspace.json");
  if (fs.existsSync(reference) && fs.lstatSync(reference).isSymbolicLink()) throw Error("Select an owned Director workspace descriptor");
  const previous = fs.existsSync(reference) ? composer.readJson(home, "workspace.json") : null;
  if (previous && (previous.schema !== 1 || previous.kind !== "director-workspace" || !Array.isArray(previous.providers))) {
    throw Error("Unrecognized Director workspace descriptor: " + reference);
  }
  if (!previous && fs.existsSync(home) && fs.readdirSync(home).some(name => name !== ".setup-lock")) throw Error("Existing Director directory needs inspection: " + home);
  return previous;
}

function writeDescriptor(home, descriptor) {
  const scratch = fs.mkdtempSync(path.join(home, ".descriptor-"));
  try {
    const file = path.join(scratch, "workspace.json");
    fs.writeFileSync(file, JSON.stringify(descriptor, null, 2) + "\n");
    fs.renameSync(file, path.join(home, "workspace.json"));
  } finally { fs.rmSync(scratch, {recursive:true, force:true}); }
}

function setupLock(home, previous, operation) {
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
    const current = readDescriptor(home);
    if (composer.json(current) !== composer.json(previous)) throw Error("Director host selection changed; retry the request");
    return operation();
  } finally {
    fs.closeSync(fd);
    fs.unlinkSync(lock);
  }
}

function installDirector(workspace, source, providers, {dryRun = false, verify = false} = {}) {
  const {canonical, home, current} = workspaceLocations(workspace);
  const previous = readDescriptor(current);
  const moving = current !== home || fs.existsSync(path.join(home, relocationJournal));
  if (verify && moving) throw Error("Apply the owned Director storage migration before verification");
  if (!verify) installSourceSupportsLayout(source);
  if (verify && !previous) throw Error("Dedicated Director installation is missing: " + home);
  if (verify && !previous.providers.length) throw Error("No Director hosts are installed in this workspace");
  if (verify && providers.some(host => !previous.providers.includes(host.id))) throw Error("Selected host is missing from the Director workspace");
  const matrix = composer.readJson(source, "config/providers.json").providers;
  const selected = [...new Set([...(previous?.providers || []), ...providers.map(provider => provider.id)])].map(id => {
    const item = matrix.find(provider => provider.id === id);
    if (!item) throw Error("Recorded Director host is unavailable: " + id);
    return item;
  });
  const previousHosts = (previous?.providers || []).map(id => selected.find(host => host.id === id));
  const previousLaunchers = new Set(previousHosts.map(host => relativePackage(host, launcher)));
  routing.plan(canonical, previousHosts, selected, {verify});
  const names = composer.operationNames(source, "director");
  const selections = selected.flatMap(host => names.map(name => ({name, provider: host.id, rel: relativePackage(host, name)})));
  const setup = relativePackage(selected[0], "skill-tree-director-setup") + "/scripts/director-entry.py";
  const descriptor = {schema: 1, kind: "director-workspace", providers: selected.map(host => host.id), setup_entry: setup};
  const entries = selected.map(host => {
    const entry = relativePackage(host, "skill-tree-director-setup") + "/scripts/director-entry.py";
    const location = path.posix.join(directorFolder, entry);
    const content = launcherText(location);
    const legacy = previousLaunchers.has(relativePackage(host, launcher)) ? [
      launcherText(location, {previous: true}),
      ...(moving ? legacyLaunchers(path.posix.join(legacyFolder, entry)) : [])
    ] : [];
    return {file: checkLauncher(canonical, host, content, legacy), content, legacy, host};
  });
  const message = `Director ${dryRun ? "preview" : "ready"} at ${home}\nOpen ${canonical} in ${selected.map(item => item.label).join(", ")} and invoke skill-tree-director.\nConnect an existing project, create a new project, or continue later.`;
  function storage(mode) {
    const result = spawnSync(process.env.PYTHON || "python3",
      ["-B", path.join(__dirname, "../common/scripts/director-state.py"), mode, canonical],
      {encoding:"utf8", timeout:120000});
    if (result.error || result.status !== 0) throw Error(result.error?.message || result.stdout || result.stderr);
  }
  if (verify) {
    const receipt = manager.verify(home, path.join(home, ".skill-tree/installation/source"));
    if (receipt.flavor !== "director" || previous.setup_entry !== setup ||
        !selections.every(({name, provider, rel}) => {
          const item = receipt.destinations[rel];
          return item?.name === name && (item.providers || [item.provider]).includes(provider);
        })) throw Error("Dedicated Director receipt does not match its workspace descriptor");
    if (entries.some(({file, content}) => !fs.existsSync(file) || fs.readFileSync(file, "utf8") !== content)) {
      throw Error("An installed Director launcher is missing or needs a workspace update");
    }
    storage("project-storage-verify");
    return "Director verified at " + home;
  }
  if (dryRun) {
    if (moving) {
      inspectOwnedWorkspace(canonical, home, current, source);
      return message + "\nPreview: move the retained Director workspace to the new storage path.";
    }
    if (fs.existsSync(home)) manager.install(home, source, "director", selections, {dryRun: true});
    return message;
  }
  fs.mkdirSync(canonical, {recursive:true});
  if (fs.realpathSync(canonical) !== canonical) throw Error("Director workspace changed during creation");
  const productFlavor = moving ? inspectOwnedWorkspace(canonical, home, current, source) : null;
  storage("project-storage-prepare");
  if (moving) {
    fs.mkdirSync(path.dirname(home), {recursive: true});
    moveOwnedWorkspace(canonical, home, productFlavor, source);
  }
  fs.mkdirSync(home, {recursive: true});
  if (fs.realpathSync(home) !== home) throw Error("Director workspace changed during creation");
  setupLock(home, previous, () => {
    // Retain the approved selection for a safe retry of a partial first setup.
    if (!previous) writeDescriptor(home, descriptor);
    manager.install(home, source, "director", selections);
    manager.verify(home, source);
    if (previous) writeDescriptor(home, descriptor);
    const init = spawnSync(process.env.PYTHON || "python3", ["-B", path.join(home, setup), "project-init", home],
      {encoding:"utf8", timeout:120000});
    if (init.error || init.status !== 0) throw Error(init.error?.message || init.stdout || init.stderr);
    for (const {file, content, legacy, host} of entries) {
      checkLauncher(canonical, host, content, legacy);
      const folder = path.dirname(file);
      if (!fs.existsSync(file)) {
        fs.mkdirSync(folder, {recursive:true});
        fs.writeFileSync(file, content, {flag:"wx"});
        continue;
      }
      if (fs.readFileSync(file, "utf8") === content) continue;
      const scratch = fs.mkdtempSync(path.join(path.dirname(folder), ".skill-tree-launcher-"));
      try {
        const staged = path.join(scratch, "SKILL.md");
        fs.writeFileSync(staged, content, {flag:"wx"});
        checkLauncher(canonical, host, content, legacy);
        fs.renameSync(staged, file);
      } finally {
        fs.rmSync(scratch, {recursive:true, force:true});
      }
    }
    // The Core refresh during relocation may update another owned block in the same file.
    routing.apply(routing.plan(canonical, previousHosts, selected));
  });
  if (moving) relocation(canonical, "finish");
  return message;
}

function removeDirector(workspace, source, providers, {dryRun = false} = {}) {
  const canonical = workspacePath(workspace);
  const home = servicePath(canonical);
  if (fs.existsSync(path.join(home, relocationJournal))) throw Error("Finish the retained Director storage migration first");
  const previous = readDescriptor(home);
  if (!previous) throw Error("Dedicated Director installation is missing: " + home);
  const requested = new Set(providers.map(provider => provider.id));
  const matrix = composer.readJson(source, "config/providers.json").providers;
  const installed = previous.providers.map(id => {
    const host = matrix.find(item => item.id === id);
    if (!host) throw Error("Recorded Director host is unavailable: " + id);
    return host;
  });
  const removed = installed.filter(host => requested.has(host.id));
  if (!removed.length) return "Selected Director hosts are already absent at " + home;
  const remaining = installed.filter(host => !requested.has(host.id));
  const shared = new Set(remaining.map(host => relativePackage(host, launcher)));
  const bridgeChanges = routing.plan(canonical, installed, remaining);
  const setupEntry = host => relativePackage(host, "skill-tree-director-setup") + "/scripts/director-entry.py";
  const descriptor = {...previous, providers:remaining.map(host => host.id), setup_entry:remaining.length ? setupEntry(remaining[0]) : null};
  const execute = () => {
    const receipt = manager.receipt(home, true);
    if (receipt.flavor !== "director") throw Error("Director workspace has a different profile");
    const selections = [];
    for (const [rel, record] of Object.entries(receipt.destinations)) {
      for (const provider of record.providers || [record.provider]) {
        if (requested.has(provider)) selections.push({rel, name:record.name, provider});
      }
    }
    const launchers = new Set(removed.filter(host => !shared.has(relativePackage(host, launcher))).map(host => {
      const layout = home === ownedPath(canonical, legacyFolder) ? legacyFolder : directorFolder;
      const location = path.posix.join(layout, setupEntry(host));
      const expected = layout === legacyFolder ? previousLauncherText(location, layout) : launcherText(location);
      const legacy = layout === legacyFolder ? legacyLaunchers(location) : [launcherText(location, {previous: true})];
      return checkLauncher(canonical, host, expected, legacy, true);
    }));
    if (selections.length) manager.uninstall(home, selections, {dryRun, recoverPluginPending:false});
    if (!dryRun) {
      for (const file of launchers) {
        if (fs.existsSync(file)) fs.unlinkSync(file);
        const directory = path.dirname(file);
        if (fs.existsSync(directory) && !fs.readdirSync(directory).length) fs.rmdirSync(directory);
      }
      routing.apply(bridgeChanges);
      writeDescriptor(home,descriptor);
    }
  };
  if (dryRun) execute();
  else setupLock(home, previous, execute);
  const hosts = remaining.length ? remaining.map(host => host.id).join(", ") : "none";
  return `Director host removal${dryRun ? " preview" : " complete"} at ${home}. Remaining hosts: ${hosts}.`;
}

module.exports = {installDirector, removeDirector, servicePath, workspaceDescriptor, directFlavor};
