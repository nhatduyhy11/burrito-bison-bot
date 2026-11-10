"use strict";
// Describe the live deploy over plain HTTP, no browser, no login:
// index.html (ClientVer) -> manifest.<ver>.js -> src/settings.<h>.js (bundleVers).
const { getText } = require("./http");

const GAME = "https://hauntedroomvnh5.joynetgame.com/";

async function liveDeploy() {
  const html = await getText(GAME);
  const clientVer = (/"ClientVer":\s*"(\d+)"/.exec(html) || [])[1];
  if (!clientVer) throw new Error("ClientVer not found in index.html");
  const manifestFile = `manifest.${clientVer}.js`;
  const manifest = await getText(GAME + manifestFile);
  // window.manifest = {"initial": [...], "game": [...], "debug": [...]}
  const manifestJson = JSON.parse(manifest.slice(manifest.indexOf("{"), manifest.lastIndexOf("}") + 1));
  const settingsFile = manifestJson.game.find((f) => /^src\/settings\.[0-9a-f]+\.js$/.test(f));
  if (!settingsFile) throw new Error("settings script not found in manifest");
  const settings = await getText(GAME + settingsFile);
  const vers = (/bundleVers:\{([^}]*)\}/.exec(settings) || [])[1];
  if (!vers) throw new Error("bundleVers not found in settings");
  const bundleVers = Object.fromEntries([...vers.matchAll(/(\w+):"([0-9a-f]+)"/g)].map((m) => [m[1], m[2]]));
  return { clientVer, html, manifestFile, manifest: manifestJson, settingsFile, bundleVers };
}

module.exports = { GAME, liveDeploy };
