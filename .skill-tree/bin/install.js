#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const REPO_ROOT = path.resolve(__dirname, "..");
const PROVIDERS_FILE = path.join(REPO_ROOT, "config", "providers.json");

function usage() {
  return `Usage: node .skill-tree/bin/install.js [options]

Options:
  --all                         Select all non-soft matrix providers
  --only <provider-id>          Select provider id from .skill-tree/config/providers.json (repeatable)
  --agent <upstream-profile>    Explicit upstream skills CLI profile passthrough (repeatable)
  --skills <names...>           Select one or more skills
  --flavor general|web|unity    Select the project workflow flavor\n  --global                      Unsupported for project specialization
  --project                     Install to project path (default)
  --target <path>               Project root or explicit generic destination
  --source <path>               Explicit local Skill Tree source repository
  --copy                        Copy skill folders
  --symlink                     Unsupported for project specialization
  --with-init                   Add marker-fenced instruction bridge
  --dry-run                     Print plan without writes or network
  --list                        List providers and skills
  --list-plugins                Inspect installed plugins without setup or dispatch
  --configure-plugins           Enter optional plugin setup in a terminal
  --plugins <proposal.json>     Apply a resolved Skill Tree manager proposal
  --confirm-plugins <digest>    Confirm the exact supplied proposal
  --json                        Emit the plugin inventory as JSON
  --group-by plugin|point       Group the human plugin inventory (default: plugin)
  --force                       Retain ownership checks; never discard local modifications
  --uninstall                   Remove selected skills and optional bridge blocks
  --verify                      Verify installed files without writing
  --non-interactive             Do not prompt
  --no-color                    Disable color output
  --help                        Show command help
`;
}

function loadProviders(file = PROVIDERS_FILE) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function listSkills(sourceRoot = REPO_ROOT) {
  const dir = path.join(sourceRoot, "skills", "general");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((name) => fs.existsSync(path.join(dir, name, "SKILL.md")))
    .sort();
}

function parseArgs(argv) {
  const args = {
    flavor: null,
    all: false,
    only: [],
    agent: [],
    skills: [],
    global: false,
    project: false,
    target: null,
    source: null,
    copy: false,
    symlink: false,
    withInit: false,
    dryRun: false,
    list: false,
    listPlugins: false,
    configurePlugins: false,
    plugins: null,
    confirmPlugins: null,
    json: false,
    groupBy: null,
    force: false,
    uninstall: false,
    verify: false,
    nonInteractive: false,
    noColor: false,
    help: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) throw new Error(`${token} requires a value`);
      i += 1;
      return argv[i];
    };
    if (token === "--flavor") args.flavor = next();
    else if (token === "--all") args.all = true;
    else if (token === "--only") args.only.push(next());
    else if (token === "--agent") args.agent.push(next());
    else if (token === "--skills" || token === "--skill") {
      while (i + 1 < argv.length && !argv[i + 1].startsWith("--")) {
        i += 1;
        args.skills.push(argv[i]);
      }
      if (!args.skills.length) throw new Error(`${token} requires at least one value`);
    } else if (token === "--global" || token === "-g") args.global = true;
    else if (token === "--project" || token === "-p") args.project = true;
    else if (token === "--target") args.target = next();
    else if (token === "--source") args.source = next();
    else if (token === "--copy") args.copy = true;
    else if (token === "--symlink") args.symlink = true;
    else if (token === "--with-init") args.withInit = true;
    else if (token === "--dry-run") args.dryRun = true;
    else if (token === "--list") args.list = true;
    else if (token === "--list-plugins") {
      if (args.listPlugins) throw new Error("--list-plugins cannot repeat");
      args.listPlugins = true;
    }
    else if (token === "--configure-plugins") {
      if (args.configurePlugins) throw new Error("--configure-plugins cannot repeat");
      args.configurePlugins = true;
    }
    else if (token === "--plugins") {
      if (args.plugins !== null) throw new Error("--plugins cannot repeat");
      args.plugins = next();
    }
    else if (token === "--confirm-plugins") {
      if (args.confirmPlugins !== null) throw new Error("--confirm-plugins cannot repeat");
      args.confirmPlugins = next();
    }
    else if (token === "--json") {
      if (args.json) throw new Error("--json cannot repeat");
      args.json = true;
    }
    else if (token === "--group-by") {
      if (args.groupBy !== null) throw new Error("--group-by cannot repeat");
      args.groupBy = next();
      if (!["plugin", "point"].includes(args.groupBy)) throw new Error("--group-by requires plugin or point");
    }
    else if (token === "--force") args.force = true;
    else if (token === "--uninstall") args.uninstall = true;
    else if (token === "--verify") args.verify = true;
    else if (token === "--non-interactive" || token === "-y" || token === "--yes") args.nonInteractive = true;
    else if (token === "--no-color") args.noColor = true;
    else if (token === "--help" || token === "-h") args.help = true;
    else throw new Error(`unknown option: ${token}`);
  }
  if (args.global && args.project) throw new Error("--global and --project are mutually exclusive");
  if (args.copy && args.symlink) throw new Error("--copy and --symlink are mutually exclusive");
  if (args.uninstall && args.verify) throw new Error("--uninstall and --verify are mutually exclusive");
  if (args.configurePlugins && args.plugins !== null) throw new Error("--configure-plugins and --plugins are mutually exclusive");
  if (args.confirmPlugins !== null && args.plugins === null) throw new Error("--confirm-plugins requires --plugins");
  if ((args.configurePlugins || args.plugins !== null) && (args.list || args.listPlugins || args.verify || args.uninstall)) {
    throw new Error("Plugin setup cannot be mixed with listing, verification or uninstall");
  }
  if (!args.listPlugins && (args.json || args.groupBy !== null)) throw new Error("--json and --group-by require --list-plugins");
  if (args.listPlugins && (args.list || args.flavor || args.all || args.only.length || args.agent.length || args.skills.length || args.global || args.source || args.copy || args.symlink || args.withInit || args.dryRun || args.force || args.uninstall || args.verify)) {
    throw new Error("--list-plugins is a read-only operation and cannot be mixed with installation or provider options");
  }
  return args;
}

function expandHome(value) {
  if (!value) return value;
  if (value === "~") return os.homedir();
  if (value.startsWith("~/")) return path.join(os.homedir(), value.slice(2));
  return value;
}

function which(command, env = process.env) {
  const pathValue = env.PATH || "";
  const extensions = process.platform === "win32" ? ["", ".cmd", ".exe", ".bat"] : [""];
  for (const entry of pathValue.split(path.delimiter)) {
    if (!entry) continue;
    for (const ext of extensions) {
      const candidate = path.join(entry, command + ext);
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return null;
}

function vscodeExtensionDirs(home = os.homedir()) {
  return [
    path.join(home, ".vscode", "extensions"),
    path.join(home, ".vscode-insiders", "extensions"),
    path.join(home, ".cursor", "extensions"),
  ];
}

function jetbrainsPluginDirs(home = os.homedir()) {
  return [
    path.join(home, "Library", "Application Support", "JetBrains"),
    path.join(home, ".local", "share", "JetBrains"),
    path.join(home, "AppData", "Roaming", "JetBrains"),
  ];
}

function detectProbe(probe, env = process.env, home = os.homedir()) {
  if (probe.kind === "command") return Boolean(which(probe.value, env));
  if (probe.kind === "environment") return Boolean(env[probe.value]);
  if (probe.kind === "directory") return fs.existsSync(expandHome(probe.value));
  if (probe.kind === "file") return fs.existsSync(expandHome(probe.value));
  if (probe.kind === "mac-application") return process.platform === "darwin" && fs.existsSync(probe.value);
  if (probe.kind === "vscode-extension" || probe.kind === "cursor-extension") {
    return vscodeExtensionDirs(home).some((dir) => {
      if (!fs.existsSync(dir)) return false;
      return fs.readdirSync(dir).some((name) => name.toLowerCase().startsWith(probe.value.toLowerCase()));
    });
  }
  if (probe.kind === "jetbrains-plugin") {
    return jetbrainsPluginDirs(home).some((dir) => {
      if (!fs.existsSync(dir)) return false;
      const stack = [dir];
      while (stack.length) {
        const current = stack.pop();
        for (const name of fs.readdirSync(current, { withFileTypes: true })) {
          const full = path.join(current, name.name);
          if (name.isDirectory()) {
            if (name.name.toLowerCase().includes(probe.value.toLowerCase())) return true;
            stack.push(full);
          }
        }
      }
      return false;
    });
  }
  return false;
}

function detectProvider(provider, env = process.env) {
  const detected = (provider.detect || []).some((probe) => detectProbe(probe, env));
  return { id: provider.id, detected, soft: Boolean(provider.soft) };
}

function selectedProviders(args, matrix) {
  const providers = matrix.providers;
  const byId = new Map(providers.map((provider) => [provider.id, provider]));
  const selected = [];
  if (args.all) {
    selected.push(...providers.filter((provider) => !provider.soft && provider.tier !== 3));
  } else if (args.only.length) {
    for (const id of args.only) {
      if (!byId.has(id)) throw new Error(`unknown provider id: ${id}`);
      selected.push(byId.get(id));
    }
  } else {
    selected.push(...providers.filter((provider) => !provider.soft && detectProvider(provider).detected));
  }
  const seen = new Set();
  return selected.filter((provider) => {
    if (seen.has(provider.id)) return false;
    seen.add(provider.id);
    return true;
  });
}

function selectedSkills(args, sourceRoot) {
  const available = listSkills(sourceRoot);
  if (args.skills.length === 0 || args.skills.includes("*")) return available;
  for (const skill of args.skills) {
    if (!available.includes(skill)) throw new Error(`unknown skill: ${skill}`);
  }
  return [...new Set(args.skills)];
}

function isLocalSource(source) {
  if (!source) return true;
  if (/^(https?:|git@|ssh:)/.test(source)) return false;
  return fs.existsSync(path.resolve(source));
}

function sourceRoot(args) {
  if (!args.source) return REPO_ROOT;
  if (!isLocalSource(args.source)) return null;
  const resolved = path.resolve(args.source);
  for(const candidate of [path.join(resolved,".skill-tree"),resolved]){
    const marker=path.join(candidate,"config/repository.json");
    if(fs.existsSync(marker)&&JSON.parse(fs.readFileSync(marker,"utf8")).role==='source')return candidate;
  }
  throw Error('Local source requires explicit source-role metadata');
}

function installBase(provider, args) {
  if (provider.id === "generic") {
    if (!args.target) throw new Error("generic provider requires --target");
    return path.resolve(args.target);
  }
  if (args.global) return expandHome(provider.globalPath);
  const targetRoot = args.target ? path.resolve(args.target) : process.cwd();
  return path.join(targetRoot, provider.projectPath);
}

function printList(matrix) {
  console.log("Flavors: general, web, unity\nProviders:");
  for (const provider of matrix.providers) console.log(`${provider.id}\t${provider.label}\ttier=${provider.tier}\tsoft=${provider.soft}`);
  console.log("\nLogical operations:");
  for (const skill of listSkills()) console.log(skill);
}

const setupAdvice = "Documentation setup remains separate: invoke skill-tree-repo-documentation. After queue creation, capture the persisted foundation finding through scripts/workflow-state.py capture-foundation <project>. No product execution performed.";

function terminalPrompt() {
  const lines = require("node:readline").createInterface({input: process.stdin, output: process.stdout});
  const input = lines[Symbol.asyncIterator]();
  return {
    async ask(question) {
      process.stdout.write(question);
      return (await input.next()).value;
    },
    close() { lines.close(); },
  };
}

function verifiedCore(manager, target, source, flavor, selections) {
  const profile = manager.verify(target, source);
  if (profile.flavor !== flavor) throw new Error("Flavor differs from receipt");
  for (const {rel, provider, name} of selections) {
    const record = profile.destinations[rel];
    if (record?.name !== name || record.flavor !== flavor || !(record.providers || [record.provider]).includes(provider)) {
      throw new Error("Selected package is not receipt-owned: " + rel);
    }
  }
  return profile;
}

function pendingPluginRecovery(manager, target) {
  return fs.existsSync(path.join(target, manager.transactionPaths("plugins").journal));
}

function setupFailure(error, manager, target) {
  if (error.code === "plugin-recovery" || pendingPluginRecovery(manager, target)) {
    return {status: "recovery-required", reason: "Use the owned installation manager --recover before retrying."};
  }
  const blocked = ["plugin-active", "plugin-consent", "plugin-proposal", "plugin-replay", "plugin-stale",
    "source-acquisition-required"].includes(error.code);
  const reason = typeof error.code === "string" && /^[a-z][a-z0-9-]+$/.test(error.code) ?
    error.message : "Plugin setup could not read, verify or apply the requested configuration.";
  return {status: blocked ? "blocked" : "failed", reason, ...(blocked && {code: error.code})};
}

function suppliedProposal(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    throw Object.assign(new Error("Supply a readable, resolved manager proposal as JSON."), {code: "plugin-proposal"});
  }
}

function dryPluginStage(target, source, args, profile, selections) {
  if (args.plugins === null) {
    return {status: "blocked", dry_run: true, reason: "Prepare a resolved proposal to inspect optional plugin setup offline."};
  }
  const proposal = suppliedProposal(args.plugins);
  const backend = require(path.join(source, "lib/plugin-management.js"));
  const preview = backend.inspectManagerProposal(target, proposal, {proposal_digest: args.confirmPlugins}, {profile, selections, expectedFlavor: profile.flavor});
  return {status: "skipped", dry_run: true, proposal_digest: proposal.digest,
    packages: preview.packages?.map(row => row.id) ?? [], bindings: preview.bindings?.map(row => row.id) ?? []};
}

function requestInput(line) {
  try {
    return line.startsWith("@") ? JSON.parse(fs.readFileSync(line.slice(1), "utf8")) : JSON.parse(line);
  } catch {
    throw Object.assign(new Error("Enter a manager request as JSON or @file."), {code: "plugin-request"});
  }
}

async function interactiveRequest(target, source, flavor, host, backend, ask) {
  const view = backend.managementInventory(target, {source, flavor, host});
  console.log(backend.formatInventory(view, {groupBy: "point"}).trimEnd());
  const bundle = view.catalog?.recommendations?.[flavor] ?? [];
  const menu = bundle.length ? "recommended, known, custom, request" : "known, custom, request";
  const choice = await ask("Choose " + menu + ", or press Enter to cancel: ");
  if (!choice) return null;
  if (choice === "request") {
    const input = await ask("Manager request JSON or @file (Enter cancels): ");
    return input ? requestInput(input) : null;
  }

  const request = {action: "install", request_id: "installer-" + crypto.randomUUID()};
  const {readRegistry} = require(path.join(source, "lib/plugin-registry.js"));
  const current = readRegistry(target).bindings;
  if (choice === "recommended" && bundle.length) {
    request.sources = bundle.map(row => row.id);
    request.bindings = [...current, ...bundle.map(row => ({
      id: "recommended-" + crypto.randomUUID(), plugin_id: row.id, location: row.boundary_id,
    }))];
    return request;
  }
  if (choice === "known") {
    const ids = await ask("Exact known IDs, comma-separated (Enter cancels): ");
    if (!ids) return null;
    request.sources = ids.split(",").map(id => id.trim());
  } else if (choice === "custom") {
    const input = await ask("Source URL, local path, or source descriptor JSON (Enter cancels): ");
    if (!input) return null;
    const descriptor = input.startsWith("{") ? requestInput(input) : input;
    const {normalizeSource} = require(path.join(source, "lib/plugin-sources.js"));
    const {definition} = normalizeSource(descriptor, {baseDir: target});
    console.log("Plugin ID: " + definition.id);
    request.sources = [descriptor];
  } else {
    throw Object.assign(new Error("Select a displayed plugin configuration choice."), {code: "plugin-request"});
  }

  const operations = JSON.parse(fs.readFileSync(path.join(source, "templates/operations.json"), "utf8"));
  const {createCatalog} = require(path.join(source, "lib/plugin-composition.js"));
  console.log("Registered locations: " + Object.keys(createCatalog(operations).boundaries).sort().join(", "));
  console.log("Current ordered bindings: " + JSON.stringify(current));
  const input = await ask("Complete ordered bindings JSON or @file, 'keep' for existing bindings, or Enter to cancel: ");
  if (!input) return null;
  request.bindings = input === "keep" ? current : requestInput(input);
  return request;
}

async function prepareInteractive(target, source, flavor, providers, backend, selections, ask, explicit) {
  if (!explicit) {
    const choice = await ask("Continue without new plugins [default], or type configure: ");
    if (!["configure", "2"].includes(choice?.toLowerCase())) return {status: "skipped"};
  }
  const host = providers.some(provider => provider.id === "codex") ? "codex" : "other";
  const request = await interactiveRequest(target, source, flavor, host, backend, ask);
  if (request === null) return {status: "cancelled"};
  // Only the terminal choice authorizes online resolution in this session.
  const {resolve_remote: ignored, ...offlineRequest} = request;
  let prepared;
  try {
    prepared = await backend.prepareManagerRequest(target, offlineRequest, {source, selections, expectedFlavor: flavor});
  } catch (error) {
    if (error.code !== "source-acquisition-required") throw error;
    const allow = await ask("Resolve the selected remote source online? [y/N] ");
    if (!["y", "yes"].includes(allow?.toLowerCase())) return {status: "cancelled"};
    prepared = await backend.prepareManagerRequest(target, {...offlineRequest, resolve_remote: true}, {source, selections, expectedFlavor: flavor});
  }
  console.log(JSON.stringify({proposal_digest: prepared.proposal?.digest ?? null,
    target_identity: prepared.proposal?.target_identity ?? null, core_identity: prepared.proposal?.mutation?.proposal?.core_identity ?? null,
    preview: prepared.preview, prerequisites: prepared.prerequisites}, null, 2));
  if (prepared.status !== "ready") return {status: "blocked", reason: "Resolve the displayed prerequisites before plugin activation."};
  const consent = await ask("Apply the exact displayed plugin change? [y/N] ");
  if (!["y", "yes"].includes(consent?.toLowerCase())) return {status: "cancelled"};
  return {proposal: prepared.proposal, confirmation: prepared.proposal.digest};
}

async function activateSetup(target, source, manager, args, flavor, providers, selections, ask) {
  try {
    const installedSource = path.join(target, ".skill-tree/installation/source");
    const backend = require(path.join(source, "lib/plugin-management.js"));
    const setup = args.plugins === null ?
      await prepareInteractive(target, installedSource, flavor, providers, backend, selections, ask, args.configurePlugins) :
      {proposal: suppliedProposal(args.plugins), confirmation: args.confirmPlugins};
    if (setup.status) return setup;
    const receipt = backend.applyManagerProposal(target, setup.proposal, {proposal_digest: setup.confirmation}, {selections, expectedFlavor: flavor});
    const {REGISTRY} = require(path.join(source, "lib/plugin-registry.js"));
    const stage = {status: receipt.action === "verified-no-op" ? "verified-no-op" : "installed",
      proposal_digest: setup.proposal.digest, receipt, profile: "current",
      registry: fs.existsSync(path.join(target, REGISTRY)) ? REGISTRY : null, management: "skill-tree-plugins"};
    if (receipt.requires_profile_refresh || receipt.replayed) {
      try {
        verifiedCore(manager, target, source, flavor, selections);
      } catch {
        if (receipt.requires_profile_refresh) {
          try {
            manager.refresh(target, source);
            verifiedCore(manager, target, source, flavor, selections);
            return stage;
          } catch {
            // The plugin transaction already has an independently verified receipt.
          }
        }
        stage.profile = "refresh-required";
      }
    }
    return stage;
  } catch (error) {
    return setupFailure(error, manager, target);
  }
}

async function main(argv = process.argv.slice(2), {promptFactory} = {}) {
  let prompt;
  const ask = async question => {
    prompt ??= (promptFactory ?? terminalPrompt)();
    return (await prompt.ask(question))?.trim();
  };
  try {
    const args = parseArgs(argv);
    if (args.help) { console.log(usage()); return 0; }
    if (args.listPlugins) {
      if (!args.target) throw Error("Select the inspected project explicitly with --target <repository>");
      const target = fs.realpathSync(path.resolve(args.target));
      if (!fs.statSync(target).isDirectory()) throw Error("Target must be a project directory");
      const listArgs = ["--list-plugins"];
      if (args.json) listArgs.push("--json");
      if (args.groupBy !== null) listArgs.push("--group-by", args.groupBy);
      return await require(path.join(REPO_ROOT, "lib/plugins.js")).listMain(target, listArgs, {source: REPO_ROOT});
    }
    const matrix = loadProviders();
    if (args.list) { printList(matrix); return 0; }
    if (args.global || args.symlink || args.agent.length || !isLocalSource(args.source)) {
      throw Error("Project specialization supports local project-scoped copy installation; global, symlink and uncomposed upstream paths are unsupported. Use --target <project> --flavor general|web|unity --copy.");
    }
    if (!args.target) throw Error("Select the covered project explicitly with --target <repository>");
    const target = fs.realpathSync(path.resolve(args.target));
    args.target = target;
    if (!fs.statSync(target).isDirectory()) throw Error("Target must be a project directory");
    const source = sourceRoot(args);
    const manager = require(path.join(source, "lib/installation.js"));
    const prior = manager.receipt(target);
    const interactive = !args.nonInteractive && (Boolean(promptFactory) || Boolean(process.stdin.isTTY && process.stdout.isTTY));
    if (args.configurePlugins && !args.dryRun && !interactive) {
      throw Error("--configure-plugins requires an interactive terminal. Use --plugins with --confirm-plugins for noninteractive setup.");
    }
    const flavor = args.flavor || prior?.flavor ||
      (interactive && !args.dryRun ? await ask("Choose flavor (general, web, unity): ") : null);
    if (!["general", "web", "unity"].includes(flavor)) {
      throw Error("Fresh noninteractive installation requires --flavor general|web|unity; --yes never selects a flavor");
    }
    const providers = selectedProviders(args, matrix);
    if (!providers.length) throw Error("No providers selected; use --only or --all");
    const skills = selectedSkills(args, source);
    const composer = require(path.join(source, "lib/composer.js"));
    const selections = [], rows = [];
    for (const provider of providers) {
      try {
        const base = installBase(provider, args);
        const selected = skills.map(name => ({name, provider: provider.id,
          rel: path.relative(target, path.join(base, name)).split(path.sep).join("/")}));
        selections.push(...selected);
        for (const item of selected) composer.safe(target, item.rel);
        let result;
        if (args.verify) {
          result = {action: "verified", profile: verifiedCore(manager, target, source, flavor, selected), delta: []};
        } else if (args.uninstall) {
          result = manager.uninstall(target, selected, {dryRun: args.dryRun, withInit: args.withInit, recoverPluginPending: false});
        } else {
          result = manager.install(target, source, flavor, selected, {dryRun: args.dryRun, provider: provider.id,
            bridges: args.withInit && provider.bridgePath ? [provider.bridgePath] : [], recoverPluginPending: false});
        }
        rows.push({provider: provider.id, ok: true, action: result.action, flavor, changed: result.delta,
          profile_identity: result.profile.identity, environment_identity: result.profile.environment_id,
          input_fingerprints: result.profile.inputs,
          packages: Object.entries(result.profile.destinations).map(([destination, record]) => ({
            destination, name: record.name, flavor: record.flavor, identity: record.identity, providers: record.providers || [record.provider],
          })),
          policy: "Immediate focused feedback; scoped additional boundary checks; no implicit product execution.",
          facts: result.profile.facts, gaps: result.profile.gaps});
      } catch (error) {
        rows.push({provider: provider.id, ok: false, error: error.message});
      }
    }

    const coreOK = rows.every(row => row.ok);
    const explicit = args.configurePlugins || args.plugins !== null;
    const setup = explicit || (interactive && !args.dryRun && !args.verify && !args.uninstall && coreOK);
    if (!explicit || (!args.dryRun && args.plugins === null)) {
      console.log(JSON.stringify(rows, null, 2));
      if (rows.some(row => row.ok) && !args.verify && !args.uninstall) console.log(setupAdvice);
    }
    if (!setup) return coreOK ? 0 : 1;

    let stage;
    try {
      if (!coreOK) {
        stage = pendingPluginRecovery(manager, target) ? setupFailure({}, manager, target) :
          {status: "blocked", reason: "Every selected core provider and destination must verify before plugin setup."};
      } else if (args.dryRun) {
        const planned = manager.plan(target, source, flavor, [...selections]);
        stage = dryPluginStage(target, source, args, planned.profile, selections);
      } else {
        verifiedCore(manager, target, source, flavor, selections);
        stage = await activateSetup(target, source, manager, args, flavor, providers, selections, ask);
      }
    } catch (error) {
      stage = setupFailure(error, manager, target);
    }
    const envelope = args.plugins !== null || args.dryRun ? {core: rows, plugin_stage: stage} : {plugin_stage: stage};
    console.log(JSON.stringify(envelope, null, 2));
    return coreOK && ["skipped", "cancelled", "verified-no-op", "installed"].includes(stage.status) ? 0 : 1;
  } catch (error) {
    console.error("error: " + error.message);
    return 2;
  } finally {
    prompt?.close();
  }
}
if(require.main===module)main().then(code=>{process.exitCode=code;}).catch(error=>{console.error(error.message);process.exitCode=2;});
module.exports={parseArgs,loadProviders,listSkills,detectProbe,detectProvider,selectedProviders,selectedSkills,sourceRoot,installBase,main};
