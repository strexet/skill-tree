#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const REPO_ROOT = path.resolve(__dirname, "..");
const PROVIDERS_FILE = path.join(REPO_ROOT, "config", "providers.json");
const SKILLS_DIR = path.join(REPO_ROOT, "skills");
const BRIDGE_FILE = path.join(REPO_ROOT, "src", "init-rules", "skill-tree-skills.md");
const MARKER_BEGIN = "<!-- BEGIN skill-tree-skills -->";
const MARKER_END = "<!-- END skill-tree-skills -->";

function usage() {
  return `Usage: node bin/install.js [options]

Options:
  --all                         Select all non-soft matrix providers
  --only <provider-id>          Select provider id from config/providers.json (repeatable)
  --agent <upstream-profile>    Explicit upstream skills CLI profile passthrough (repeatable)
  --skills <names...>           Select one or more skills
  --global                      Install to provider global path
  --project                     Install to project path (default)
  --target <path>               Project root or explicit generic destination
  --source <path-or-git>        Local source or Git source for upstream CLI
  --copy                        Copy skill folders
  --symlink                     Symlink skill folders
  --with-init                   Add marker-fenced instruction bridge
  --dry-run                     Print plan without writes or network
  --list                        List providers and skills
  --force                       Replace existing installer-owned skill dirs and bridge blocks
  --uninstall                   Remove selected skills and optional bridge blocks
  --verify                      Verify installed files without writing
  --non-interactive             Do not prompt
  --no-color                    Disable color output
  --help                        Show this help
`;
}

function loadProviders(file = PROVIDERS_FILE) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function listSkills(sourceRoot = REPO_ROOT) {
  const dir = path.join(sourceRoot, "skills");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((name) => fs.existsSync(path.join(dir, name, "SKILL.md")))
    .sort();
}

function parseArgs(argv) {
  const args = {
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
    if (token === "--all") args.all = true;
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
  return path.resolve(args.source);
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

function ensureSafeDestination(dest) {
  const resolved = path.resolve(dest);
  if (resolved === path.parse(resolved).root) {
    throw new Error(`refusing filesystem root destination: ${resolved}`);
  }
}

function copyDir(src, dest, force) {
  if (fs.existsSync(dest)) {
    if (!force) return { ok: false, skipped: true, message: "exists" };
    fs.rmSync(dest, { recursive: true, force: true });
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.cpSync(src, dest, { recursive: true, verbatimSymlinks: true });
  return { ok: true, message: "copied" };
}

function symlinkDir(src, dest, force) {
  if (fs.existsSync(dest)) {
    if (!force) return { ok: false, skipped: true, message: "exists" };
    fs.rmSync(dest, { recursive: true, force: true });
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.symlinkSync(src, dest, "dir");
  return { ok: true, message: "symlinked" };
}

function removeDir(dest) {
  if (!fs.existsSync(dest)) return { ok: true, message: "missing" };
  const stat = fs.lstatSync(dest);
  if (stat.isDirectory() || stat.isSymbolicLink()) {
    fs.rmSync(dest, { recursive: true, force: true });
    return { ok: true, message: "removed" };
  }
  return { ok: false, message: "not a directory or symlink" };
}

function bridgeText() {
  return `${MARKER_BEGIN}\n${fs.readFileSync(BRIDGE_FILE, "utf8").trim()}\n${MARKER_END}\n`;
}

function writeBridge(provider, args) {
  if (!provider.bridgePath) return { ok: true, message: "no bridge" };
  const rootDir = args.target ? path.resolve(args.target) : process.cwd();
  const dest = path.join(rootDir, provider.bridgePath);
  ensureSafeDestination(dest);
  const block = bridgeText();
  let current = "";
  if (fs.existsSync(dest)) current = fs.readFileSync(dest, "utf8");
  const markerRe = new RegExp(`${escapeRegExp(MARKER_BEGIN)}[\\s\\S]*?${escapeRegExp(MARKER_END)}\\n?`);
  let next;
  if (markerRe.test(current)) {
    next = current.replace(markerRe, block);
  } else {
    next = current ? `${current.replace(/\s*$/, "\n\n")}${block}` : block;
  }
  if (current === next) return { ok: true, message: "bridge current", path: dest };
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  if (fs.existsSync(dest)) {
    fs.copyFileSync(dest, `${dest}.bak`);
  }
  fs.writeFileSync(dest, next, "utf8");
  return { ok: true, message: "bridge written", path: dest };
}

function removeBridge(provider, args) {
  if (!provider.bridgePath) return { ok: true, message: "no bridge" };
  const rootDir = args.target ? path.resolve(args.target) : process.cwd();
  const dest = path.join(rootDir, provider.bridgePath);
  if (!fs.existsSync(dest)) return { ok: true, message: "bridge missing", path: dest };
  const current = fs.readFileSync(dest, "utf8");
  const markerRe = new RegExp(`\\n?${escapeRegExp(MARKER_BEGIN)}[\\s\\S]*?${escapeRegExp(MARKER_END)}\\n?`);
  if (!markerRe.test(current)) return { ok: true, message: "bridge absent", path: dest };
  fs.copyFileSync(dest, `${dest}.bak`);
  const next = current.replace(markerRe, "\n").replace(/\n{3,}/g, "\n\n").trimEnd() + "\n";
  fs.writeFileSync(dest, next, "utf8");
  return { ok: true, message: "bridge removed", path: dest };
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function verifyInstall(provider, args, skills) {
  const base = installBase(provider, args);
  const errors = [];
  for (const skill of skills) {
    const dest = path.join(base, skill);
    const skillFile = path.join(dest, "SKILL.md");
    if (!fs.existsSync(skillFile)) {
      errors.push(`${skill}: missing SKILL.md`);
      continue;
    }
    const text = fs.readFileSync(skillFile, "utf8");
    for (const rel of text.match(/(references|scripts)\/[A-Za-z0-9_.\-/]+/g) || []) {
      const clean = rel.replace(/[).,;]+$/, "");
      if (!fs.existsSync(path.join(dest, clean))) errors.push(`${skill}: missing ${clean}`);
    }
  }
  if (args.withInit && provider.bridgePath) {
    const bridge = path.join(args.target ? path.resolve(args.target) : process.cwd(), provider.bridgePath);
    if (!fs.existsSync(bridge) || !fs.readFileSync(bridge, "utf8").includes(MARKER_BEGIN)) {
      errors.push(`${provider.id}: bridge marker missing`);
    }
  }
  return { ok: errors.length === 0, errors };
}

function upstreamCommand(args, provider, skills) {
  const source = args.source || REPO_ROOT;
  const command = ["npx", "-y", "skills", args.uninstall ? "remove" : "add"];
  if (args.uninstall) {
    command.push(...skills, "--agent", provider.skillsProfile, "--yes");
    if (args.global) command.push("--global");
  } else {
    command.push(source, "--agent", provider.skillsProfile, "--yes");
    for (const skill of skills) command.push("--skill", skill);
    if (args.global) command.push("--global");
    if (args.copy) command.push("--copy");
  }
  return command;
}

function runUpstream(command) {
  const result = spawnSync(command[0], command.slice(1), { stdio: "inherit", shell: process.platform === "win32" });
  return { ok: result.status === 0, status: result.status };
}

function installLocalProvider(provider, args, skills, source) {
  const base = installBase(provider, args);
  ensureSafeDestination(base);
  const rows = [];
  for (const skill of skills) {
    const src = path.join(source, "skills", skill);
    const dest = path.join(base, skill);
    if (args.dryRun || args.verify) {
      rows.push({ provider: provider.id, skill, action: args.verify ? "verify" : "dry-run", path: dest, ok: true });
      continue;
    }
    const result = args.uninstall
      ? removeDir(dest)
      : args.symlink
        ? symlinkDir(src, dest, args.force)
        : copyDir(src, dest, args.force);
    rows.push({ provider: provider.id, skill, action: result.message, path: dest, ok: result.ok || result.skipped });
  }
  if (args.withInit && !args.dryRun && !args.verify) {
    const bridge = args.uninstall ? removeBridge(provider, args) : writeBridge(provider, args);
    rows.push({ provider: provider.id, skill: "(bridge)", action: bridge.message, path: bridge.path || "", ok: bridge.ok });
  } else if (args.withInit) {
    rows.push({ provider: provider.id, skill: "(bridge)", action: args.verify ? "verify" : "dry-run", path: provider.bridgePath || "", ok: true });
  }
  if (args.verify) {
    const verified = verifyInstall(provider, args, skills);
    if (!verified.ok) {
      rows.push({ provider: provider.id, skill: "(verify)", action: verified.errors.join("; "), path: base, ok: false });
    }
  }
  return rows;
}

function printList(matrix) {
  console.log("Providers:");
  for (const provider of matrix.providers) {
    console.log(`${provider.id}\t${provider.label}\ttier=${provider.tier}\tsoft=${provider.soft}\tprofile=${provider.skillsProfile}`);
  }
  console.log("\nSkills:");
  for (const skill of listSkills()) console.log(skill);
}

function printRows(rows) {
  console.log("provider\tskill\taction\tok\tpath");
  for (const row of rows) {
    console.log(`${row.provider}\t${row.skill}\t${row.action}\t${row.ok ? "yes" : "no"}\t${row.path || ""}`);
  }
}

function main(argv = process.argv.slice(2)) {
  let args;
  try {
    args = parseArgs(argv);
  } catch (error) {
    console.error(`error: ${error.message}`);
    console.error(usage());
    return 2;
  }
  if (args.help) {
    console.log(usage());
    return 0;
  }
  const matrix = loadProviders();
  if (args.list) {
    printList(matrix);
    return 0;
  }
  try {
    const source = sourceRoot(args);
    const providers = selectedProviders(args, matrix);
    const passthrough = args.agent.map((profile) => ({
      id: `agent:${profile}`,
      label: `Upstream ${profile}`,
      tier: 2,
      skillsProfile: profile,
      soft: false,
      projectPath: "",
      globalPath: "",
      detect: [],
      bridgePath: "",
    }));
    const allProviders = [...providers, ...passthrough];
    if (allProviders.length === 0) throw new Error("no providers selected; use --only, --all, or --agent");
    const skills = selectedSkills(args, source || REPO_ROOT);
    if (skills.length === 0) throw new Error("no skills selected");
    const rows = [];
    for (const provider of allProviders) {
      try {
        const useUpstream = provider.id.startsWith("agent:") || !source;
        if (useUpstream) {
          const command = upstreamCommand(args, provider, skills);
          if (args.dryRun || args.verify) {
            rows.push({ provider: provider.id, skill: skills.join(","), action: command.join(" "), path: "", ok: true });
          } else {
            const result = runUpstream(command);
            rows.push({ provider: provider.id, skill: skills.join(","), action: "upstream", path: "", ok: result.ok });
          }
        } else {
          rows.push(...installLocalProvider(provider, args, skills, source));
        }
      } catch (error) {
        rows.push({ provider: provider.id, skill: skills.join(","), action: `failed: ${error.message}`, path: "", ok: false });
      }
    }
    printRows(rows);
    return rows.every((row) => row.ok) ? 0 : 1;
  } catch (error) {
    console.error(`error: ${error.message}`);
    return 2;
  }
}

if (require.main === module) {
  process.exitCode = main();
}

module.exports = {
  MARKER_BEGIN,
  MARKER_END,
  parseArgs,
  loadProviders,
  listSkills,
  detectProbe,
  detectProvider,
  selectedProviders,
  selectedSkills,
  installLocalProvider,
  verifyInstall,
  bridgeText,
  writeBridge,
  removeBridge,
  main,
};
