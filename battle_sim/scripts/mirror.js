"use strict";
// Mirror the live deploy's battle assets to disk, same URL layout as the game host.
//   node battle_sim/scripts/mirror.js plan      # list what would be fetched (counts per group)
//   node battle_sim/scripts/mirror.js fetch     # download into .tmp/battle_sim/mirror/<ClientVer>/
// Public static files only (game host /, /assets, /ext-res), anonymous GETs, no login,
// nothing sent to game servers. Already-present files are skipped, so re-running resumes.
//
// Native file extensions are not in the bundle config; they are probed per asset type
// (engine rule: native/<xx>/<uuid>.<ver><ext>, fonts native/<xx>/<uuid>.<ver>/<name>.ttf).
// Natives that resolve to nothing go to missing.json; serve.js logs any 404 at runtime.
const fs = require("fs");
const path = require("path");
const http = require("../lib/http");
const cocos = require("../lib/cocos_bundle");
const { GAME, liveDeploy } = require("../lib/deploy");
const versions = require("../lib/versions");

const BUNDLES = ["internal", "main", "resources", "login", "battle", "battleConfig", "battleSkillRes", "towerDefense", "organ", "hangup", "summonCreature", "hero", "guildPVP", "climbTower", "worldBoss", "worldBossMatch"];
// ext-res: battle models + frames + data, plus the shuzhi/ image folders the battle UI loads
// (portraits, half-body portraits, item, skill, artifact, trap and building icons). Region variants other than base/_sea are skipped.
const EXT_RES_KEEP = /^(model\/|model_frame\/|userProto\/|data\/|shuzhi\/(head|icon|skillicon|TDBattle|shenbing|machine|half|build)\/)/;
const EXT_RES_REGION = /^(model\/([^/]*_(jp|kr|tw|us)|(kr|tw|jp|us)_[^/]*)\/|shuzhi\/.*(^|[/_])(jp|kr|tw|us)(_|\.))/;
const CONCURRENCY = 8;

const TEXTURE_EXTS = [".png", ".jpg", ".webp", ".jpeg"];
const NATIVE_EXTS_BY_TYPE = {
  "cc.Texture2D": TEXTURE_EXTS,
  "sp.SkeletonData": [".bin", ".skel", ".json"],
  "cc.AudioClip": [".mp3", ".ogg", ".wav", ".m4a"],
  "cc.JsonAsset": [".json"],
  "cc.TextAsset": [".txt", ".atlas", ".json"],
  "dragonBones.DragonBonesAsset": [".json", ".dbbin"],
  "cc.VideoClip": [".mp4"],
};
const FALLBACK_EXTS = [".png", ".jpg", ".bin", ".json", ".mp3", ".atlas", ".txt", ".webp", ".plist", ".fnt", ".skel"];

function mirrorRoot(clientVer) {
  return path.join(versions.CACHE, "mirror", clientVer);
}

// Static files for one bundle: config, script, imports (exact), natives (candidates).
async function bundleJobs(name, hash) {
  const cfg = await cocos.loadBundleConfig(name, hash);
  const base = `assets/${name}/`;
  const jobs = [
    { group: name, path: `${base}config.${hash}.json` },
    { group: name, path: `${base}index.${hash}.js` },
  ];
  for (const f of cocos.importUrls(name, cfg)) jobs.push({ group: name, path: f.url.slice(GAME.length) });

  const uuids = cfg.uuids.map(cocos.decodeUuid);
  const info = {}; // uuid index -> [path, type]
  for (const [idx, v] of Object.entries(cfg.paths)) info[idx] = [v[0], cfg.types[v[1]]];
  const nat = (cfg.versions && cfg.versions.native) || [];
  for (let i = 0; i < nat.length; i += 2) {
    const key = nat[i];
    const uuid = typeof key === "number" ? uuids[key] : cocos.decodeUuid(key);
    const ver = nat[i + 1];
    const [assetPath, type] = info[key] || [];
    const dir = `${base}native/${uuid.slice(0, 2)}/`;
    const cands = [];
    const pathExt = assetPath ? path.extname(assetPath) : "";
    if (type === "cc.TTFFont" || pathExt === ".ttf") {
      cands.push(`${dir}${uuid}.${ver}/${path.basename(assetPath || "font", ".ttf")}.ttf`);
    } else {
      const exts = [...new Set([pathExt, ...(NATIVE_EXTS_BY_TYPE[type] || []), ...FALLBACK_EXTS].filter(Boolean))];
      for (const e of exts) cands.push(`${dir}${uuid}.${ver}${e}`);
    }
    jobs.push({ group: name, native: true, uuid, type: type || "?", asset: assetPath || null, candidates: cands });
  }
  return jobs;
}

async function extResJobs(clientVer) {
  const manifestPath = `ext-res/version_${clientVer}.json`;
  const manifest = await http.getJson(GAME + manifestPath);
  const jobs = [{ group: "ext-res", path: manifestPath }];
  for (const [logical, hashed] of Object.entries(manifest)) {
    if (!EXT_RES_KEEP.test(logical) || EXT_RES_REGION.test(logical)) continue;
    jobs.push({ group: "ext-res/" + logical.split("/")[0], path: "ext-res/" + hashed });
  }
  return jobs;
}

// index.html and its local scripts/images (third-party SDK hosts are skipped).
function bootJobs(d) {
  const jobs = [{ group: "boot", path: "index.html", body: d.html }];
  jobs.push({ group: "boot", path: d.manifestFile });
  for (const f of [...d.manifest.initial, ...d.manifest.game]) jobs.push({ group: "boot", path: f });
  for (const f of d.jsList) jobs.push({ group: "boot", path: "src/" + f });
  const refs = [...d.html.matchAll(/(?:src|href)="(?:\.\/|\/)?([^":?#]+\.(?:js|png|jpg|json|css))"/g)].map((m) => m[1]);
  for (const r of new Set(refs)) jobs.push({ group: "boot", path: r });
  return jobs;
}

async function plan() {
  const d = await liveDeploy();
  const jobs = [...bootJobs(d)];
  for (const b of BUNDLES) {
    if (!d.bundleVers[b]) throw new Error(`bundle ${b} not in bundleVers`);
    jobs.push(...(await bundleJobs(b, d.bundleVers[b])));
  }
  jobs.push(...(await extResJobs(d.clientVer)));
  return { d, jobs };
}

async function pool(items, n, fn) {
  let i = 0;
  await Promise.all(Array.from({ length: n }, async () => {
    while (i < items.length) { const it = items[i++]; await fn(it); }
  }));
}

function isNotFound(e) { return /HTTP (403|404)/.test(e.message); }

async function fetchAll() {
  const { d, jobs } = await plan();
  const root = mirrorRoot(d.clientVer);
  fs.mkdirSync(root, { recursive: true });
  const indexFile = path.join(root, "files.json");
  const index = fs.existsSync(indexFile) ? JSON.parse(fs.readFileSync(indexFile, "utf8")) : {};
  const missing = [], failed = [];
  let done = 0, bytes = 0, last = Date.now();
  const t0 = Date.now();
  const tick = () => {
    done++;
    if (Date.now() - last > 5000) {
      last = Date.now();
      console.log(`  ${done}/${jobs.length} files, ${(bytes / 1e6).toFixed(1)} MB new, ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
  };
  const save = async (rel, body) => {
    const dest = path.join(root, rel);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest + ".part", body);
    fs.renameSync(dest + ".part", dest);
    index[rel] = body.length;
    bytes += body.length;
  };

  await pool(jobs, CONCURRENCY, async (job) => {
    try {
      if (job.native) {
        if (job.candidates.some((c) => index[c] != null)) return;
        for (const c of job.candidates) {
          try { await save(c, await http.get(GAME + c)); return; } catch (e) { if (!isNotFound(e)) throw e; }
        }
        missing.push({ group: job.group, uuid: job.uuid, type: job.type, asset: job.asset });
        return;
      }
      if (index[job.path] != null && fs.existsSync(path.join(root, job.path))) return;
      try { await save(job.path, job.body != null ? Buffer.from(job.body) : await http.get(GAME + job.path)); }
      catch (e) { if (isNotFound(e)) missing.push({ group: job.group, path: job.path }); else throw e; }
    } catch (e) {
      failed.push({ job: job.path || job.uuid, error: e.message });
    } finally {
      tick();
    }
  });

  fs.writeFileSync(indexFile, JSON.stringify(index));
  fs.writeFileSync(path.join(root, "missing.json"), JSON.stringify(missing, null, 1));
  fs.writeFileSync(path.join(root, "deploy.json"), JSON.stringify({
    clientVer: d.clientVer, settingsFile: d.settingsFile, bundleVers: d.bundleVers,
    bundles: BUNDLES, mirroredAt: new Date().toISOString(),
  }, null, 1));
  const total = Object.values(index).reduce((a, b) => a + b, 0);
  console.log(`done in ${((Date.now() - t0) / 1000).toFixed(0)}s: ${Object.keys(index).length} files, ${(total / 1e6).toFixed(1)} MB on disk (${(bytes / 1e6).toFixed(1)} MB new)`);
  console.log(`missing ${missing.length} (see missing.json), failed ${failed.length}`);
  failed.slice(0, 20).forEach((f) => console.log("  fail", f.job, f.error));
  console.log("mirror:", path.relative(process.cwd(), root));
  if (failed.length) process.exitCode = 1;
}

async function main() {
  const cmd = process.argv[2] || "plan";
  if (cmd === "plan") {
    const { d, jobs } = await plan();
    const groups = {};
    for (const j of jobs) {
      const g = (groups[j.group] = groups[j.group] || { files: 0, natives: 0 });
      j.native ? g.natives++ : g.files++;
    }
    console.log(`ClientVer ${d.clientVer}; ${jobs.length} entries -> ${path.relative(process.cwd(), mirrorRoot(d.clientVer))}`);
    for (const [g, c] of Object.entries(groups)) console.log(`  ${g.padEnd(24)} files ${String(c.files).padStart(5)}  natives ${String(c.natives).padStart(5)}`);
  } else if (cmd === "fetch") {
    await fetchAll();
  } else {
    throw new Error("usage: mirror.js plan|fetch");
  }
}

main().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
