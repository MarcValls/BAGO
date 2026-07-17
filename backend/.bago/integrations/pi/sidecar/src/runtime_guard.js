"use strict";

/**
 * runtime_guard.js -- verifies sidecar runtime envelope.
 *
 * Reports effective cwd, effective HOME, visible env keys, loaded
 * modules and implicit PI sources. Emitted as `runtime_attested`.
 * The bridge compares the report with the BAGO-supplied limits and
 * rejects any drift.
 */

const fs = require("node:fs");
const path = require("node:path");

const FORBIDDEN_PATH_NAMES = new Set([
  ".pi",
  ".agents",
  ".pi-skills",
  "skills",
  "extensions",
]);

const FORBIDDEN_MODULE_PREFIXES = [
  "@earendil-works/",
  "pi-coding-agent",
  "@mariozechner/",
];

function effectiveHome() {
  return process.env.HOME || process.env.USERPROFILE || "";
}

function visibleEnvKeys() {
  return Object.keys(process.env).sort();
}

function loadedModules() {
  try {
    const cache = require.cache || {};
    return Object.keys(cache).sort();
  } catch {
    return [];
  }
}

function findImplicitPiSources(scopeRoot) {
  const found = [];
  if (!scopeRoot || !fs.existsSync(scopeRoot)) return found;
  let entries;
  try {
    entries = fs.readdirSync(scopeRoot);
  } catch {
    return found;
  }
  for (const name of entries) {
    if (FORBIDDEN_PATH_NAMES.has(name)) {
      const candidate = path.join(scopeRoot, name);
      try {
        if (fs.statSync(candidate)) {
          found.push(candidate);
        }
      } catch {
        // ignore
      }
    }
  }
  return found;
}

function detectForbiddenModules(modules) {
  return modules.filter((m) =>
    FORBIDDEN_MODULE_PREFIXES.some((p) => m.startsWith(p)),
  );
}

function buildReport(scopeRoot, sidecarVersion, lockfileHash) {
  return {
    effective_cwd: process.cwd(),
    effective_home: effectiveHome(),
    visible_env_keys: visibleEnvKeys(),
    loaded_modules: loadedModules(),
    implicit_pi_sources: findImplicitPiSources(scopeRoot),
    node_version: process.version,
    platform: process.platform,
    sidecar_version: sidecarVersion,
    lockfile_hash: lockfileHash,
  };
}

module.exports = {
  effectiveHome,
  visibleEnvKeys,
  loadedModules,
  findImplicitPiSources,
  detectForbiddenModules,
  buildReport,
};
