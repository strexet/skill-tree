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
  return `Usage: node .skill-tree/bin/install.js [options]

Options:
  --all                         Select all non-soft matrix providers
  --only <provider-id>          Select provider id from .skill-tree/config/providers.json (repeatable)
  --agent <upstream-profile>    Explicit upstream skills CLI profile passthrough (repeatable)
  --skills <names...>           Select one or more skills
  --flavor general|web|unity    Select the project workflow flavor\n  --global                      Unsupported for project specialization
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
  const resolved = path.resolve(args.source);
  return fs.existsSync(path.join(resolved, ".skill-tree", "skills")) ? path.join(resolved, ".skill-tree") : resolved;
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

async function main(argv = process.argv.slice(2)) {
  try {
    const args=parseArgs(argv);
    if(args.help){console.log(usage());return 0;}
    const matrix=loadProviders();
    if(args.list){printList(matrix);return 0;}
    if(args.global||args.symlink||args.agent.length||!isLocalSource(args.source)) throw Error("Project specialization supports local project-scoped copy installation; global, symlink and uncomposed upstream paths are unsupported. Use --target <project> --flavor general|web|unity --copy.");
    if(!args.target)throw Error("Select the covered project explicitly with --target <repository>");
    const target=fs.realpathSync(path.resolve(args.target));
    args.target=target;
    if(!fs.statSync(target).isDirectory())throw Error("Target must be a project directory");
    const source=sourceRoot(args),manager=require(path.join(source,'lib/installation.js'));
    const prior=manager.receipt(target);
    let flavor=args.flavor||prior?.flavor;
    if(!flavor&&process.stdin.isTTY&&!args.nonInteractive){
      const rl=require('node:readline/promises').createInterface({input:process.stdin,output:process.stdout});
      try {flavor=(await rl.question('Choose flavor (general, web, unity): ')).trim();}finally{rl.close();}
    }
    if(!['general','web','unity'].includes(flavor))throw Error("Fresh noninteractive installation requires --flavor general|web|unity; --yes never selects a flavor");
    const providers=selectedProviders(args,matrix);
    if(!providers.length)throw Error("No providers selected; use --only or --all");
    const skills=selectedSkills(args,source),rows=[];
    for(const provider of providers){
      try{
        const base=installBase(provider,args),selections=skills.map(name=>({name,provider:provider.id,rel:path.relative(target,path.join(base,name)).split(path.sep).join('/')}));
        for(const item of selections)require(path.join(source,'lib/composer.js')).safe(target,item.rel);
        let result;
        if(args.verify){const profile=manager.verify(target,source);if(profile.flavor!==flavor)throw Error('Flavor differs from receipt');for(const item of selections)if(!profile.destinations[item.rel])throw Error('Selected package is not receipt-owned: '+item.rel);result={action:'verified',profile,delta:[]};}
        else if(args.uninstall)result=manager.uninstall(target,selections,{dryRun:args.dryRun,withInit:args.withInit});
        else result=manager.install(target,source,flavor,selections,{dryRun:args.dryRun,bridges:args.withInit&&provider.bridgePath?[provider.bridgePath]:[]});
        rows.push({provider:provider.id,ok:true,action:result.action,flavor,changed:result.delta,facts:result.profile.facts,gaps:result.profile.gaps});
      }catch(error){rows.push({provider:provider.id,ok:false,error:error.message});}
    }
    console.log(JSON.stringify(rows,null,2));
    if(rows.some(r=>r.ok)&&!args.verify&&!args.uninstall){console.log('Documentation setup remains separate: invoke skill-tree-repo-documentation. After queue creation, capture the persisted foundation finding through scripts/workflow-state.py capture-foundation <project>. No product execution performed.');}
    return rows.every(r=>r.ok)?0:1;
  }catch(error){console.error('error: '+error.message);return 2;}
}
if(require.main===module)main().then(code=>{process.exitCode=code;}).catch(error=>{console.error(error.message);process.exitCode=2;});
module.exports={parseArgs,loadProviders,listSkills,detectProbe,detectProvider,selectedProviders,selectedSkills,sourceRoot,installBase,main};
