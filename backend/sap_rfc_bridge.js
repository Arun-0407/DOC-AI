/**
 * SAP RFC Bridge for DOC AI
 *
 * Reuses node-rfc from the working dashboard's node_modules — no npm install needed.
 * Exposes a local HTTP server on port 5001 so Python (3.14) can call SAP via RFC.
 *
 * Endpoints:
 *   GET /health              – RFC PING
 *   GET /search?q=ZSD        – search TADIR for Z/Y objects
 *   GET /source?name=ZPROG   – RPY_PROGRAM_READ
 *   GET /smartform?name=ZSF  – SSF_FUNCTION_MODULE_NAME
 *
 * Start: node sap_rfc_bridge.js
 */

"use strict";
const path = require("path");
const http = require("http");
const url  = require("url");
const fs   = require("fs");

// ── Resolve modules from dashboard node_modules (already installed & working) ─
const DASHBOARD_MODULES = "C:\\Users\\arun.kumar9\\Desktop\\dashboard\\backend\\node_modules";
const LOCAL_MODULES      = path.join(__dirname, "node_modules");

function requireFrom(moduleName) {
  // Try local first, then dashboard
  const candidates = [
    path.join(LOCAL_MODULES, moduleName),
    path.join(DASHBOARD_MODULES, moduleName),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) {
      return require(p);
    }
  }
  throw new Error(`Cannot find module '${moduleName}' in local or dashboard node_modules`);
}

// Load dotenv — read .env from DOC AI backend directory
try {
  const dotenv = requireFrom("dotenv");
  dotenv.config({ path: path.join(__dirname, ".env") });
} catch (e) {
  // dotenv optional — fall back to process.env already set
  console.warn("[bridge] dotenv not found, using existing env vars");
}

// ── Guard: exit immediately when SAP_RFC_ENABLED is false ────────────────────
// Set SAP_RFC_ENABLED=true in .env to allow this bridge to start.
// When false (the default) the Python startup code never launches this file,
// but if someone runs it manually it exits with a clear message.
const SAP_RFC_ENABLED = (process.env.SAP_RFC_ENABLED || "false").toLowerCase();
if (SAP_RFC_ENABLED !== "true" && SAP_RFC_ENABLED !== "1") {
  console.warn(
    "[bridge] SAP_RFC_ENABLED is not set to true in .env — bridge will not start.\n" +
    "[bridge] Set SAP_RFC_ENABLED=true and ensure SAPNWRFC_HOME points to the NW RFC SDK."
  );
  process.exit(0);
}

// ── Load SAP NW RFC SDK into PATH ────────────────────────────────────────────
// SAPNWRFC_HOME must be set in .env when SAP_RFC_ENABLED=true.
// No hardcoded fallback path — the bridge will not start without it.
const rfcHome = process.env.SAPNWRFC_HOME || "";
if (!rfcHome) {
  console.error(
    "[bridge] SAPNWRFC_HOME is not set in .env.\n" +
    "[bridge] Set SAPNWRFC_HOME=<path to nwrfcsdk> in backend/.env and restart."
  );
  process.exit(1);
}
{
  const libPath = path.join(rfcHome, "lib");
  const cur = process.env.PATH || "";
  if (!cur.includes(libPath)) {
    process.env.PATH = `${libPath};${cur}`;
    process.env.Path = process.env.PATH;
  }
  process.env.SAPNWRFC_HOME = rfcHome;
}

// ── Load node-rfc from dashboard node_modules ─────────────────────────────────
let rfc = null;
let rfcError = null;
try {
  rfc = requireFrom("node-rfc");
} catch (e) {
  rfcError = e.message;
  console.error("[bridge] node-rfc failed to load:", e.message);
}

// ── SAP connection params ─────────────────────────────────────────────────────
const SAP = {
  ashost: process.env.SAP_HOST,
  sysnr:  process.env.SAP_SYSNR  || "00",
  client: process.env.SAP_CLIENT || "120",
  user:   process.env.SAP_USER,
  passwd: process.env.SAP_PASSWORD,
  lang:   process.env.SAP_LANG   || "EN",
};

async function openClient() {
  if (!rfc)         throw new Error("node-rfc not available: " + rfcError);
  if (!SAP.ashost)  throw new Error("SAP_HOST not set in .env");
  if (!SAP.user)    throw new Error("SAP_USER not set in .env");
  if (!SAP.passwd)  throw new Error("SAP_PASSWORD not set in .env");
  const c = new rfc.Client(SAP);
  await c.open();
  return c;
}

async function closeClient(c) {
  try { if (c && c.alive) await c.close(); } catch (_) {}
}

// ── HTTP helpers ──────────────────────────────────────────────────────────────
function send(res, status, data) {
  const body = JSON.stringify(data);
  res.writeHead(status, {
    "Content-Type":  "application/json",
    "Content-Length": Buffer.byteLength(body),
    "Access-Control-Allow-Origin": "*",
  });
  res.end(body);
}

function validateName(v) {
  return typeof v === "string" && /^[A-Za-z0-9_/@$#.:\- ]{1,120}$/.test(v);
}

async function readTable(client, table, fields, options, rowLimit) {
  const MAX = rowLimit > 0 ? rowLimit : 500000;
  const all = [];
  let skip = 0;
  while (true) {
    const remaining = MAX - all.length;
    if (remaining <= 0) break;
    const fetch = Math.min(5000, remaining);
    const res = await client.call("RFC_READ_TABLE", {
      QUERY_TABLE: table,
      DELIMITER:   "|",
      GET_SORTED:  "X",
      FIELDS:  fields.map(f => ({ FIELDNAME: f })),
      OPTIONS: options.map(t => ({ TEXT: t })),
      ROWCOUNT: fetch,
      ROWSKIPS: skip,
    });
    const batch = res.DATA || [];
    if (!batch.length) break;
    const names = (res.FIELDS || []).map(f => (f.FIELDNAME || "").trim());
    all.push(...batch.map(row => {
      const vals = (row.WA || "").split("|");
      return Object.fromEntries(names.map((n, i) => [n, (vals[i] || "").trim()]));
    }));
    skip += batch.length;
    if (batch.length < fetch) break;
  }
  return all;
}

// ── Route handlers ────────────────────────────────────────────────────────────

async function handleHealth(res) {
  let client;
  try {
    client = await openClient();
    await client.ping();
    send(res, 200, {
      ok: true,
      message: `Connected via RFC (ashost=${SAP.ashost}, sysnr=${SAP.sysnr})`,
      host: SAP.ashost,
      method: "rfc",
    });
  } catch (e) {
    send(res, 200, { ok: false, message: e.message, host: SAP.ashost || "", method: "rfc" });
  } finally {
    await closeClient(client);
  }
}

async function handleSearch(q, res) {
  if (!q || q.length < 2) {
    return send(res, 400, { error: "q must be at least 2 characters" });
  }
  // Validate input to prevent RFC injection — only allow safe SAP object name chars
  if (!validateName(q)) {
    return send(res, 400, { error: "Invalid search query. Use only letters, digits, and underscores." });
  }
  let client;
  try {
    client = await openClient();
    const query = q.toUpperCase();

    const rows = await readTable(
      client, "TADIR",
      ["PGMID", "OBJECT", "OBJ_NAME", "DEVCLASS", "AUTHOR"],
      [`PGMID = 'R3TR'`, `AND OBJ_NAME LIKE '${query}%'`],
      100
    );

    // Get descriptions from TRDIRT
    const names = rows.map(r => r.OBJ_NAME).filter(Boolean);
    const descMap = {};
    if (names.length) {
      try {
        const chunk = names.slice(0, 30);
        const list  = chunk.map(n => `'${n}'`).join(",");
        const dRows = await readTable(
          client, "TRDIRT",
          ["NAME", "TEXT"],
          [`NAME IN (${list})`, "AND SPRSL = 'E'"],
          50
        );
        for (const r of dRows) {
          if (r.NAME) descMap[r.NAME.trim()] = (r.TEXT || "").trim();
        }
      } catch (_) {}
    }

    const objects = rows.map(r => ({
      name:        (r.OBJ_NAME  || "").trim(),
      object_type: (r.OBJECT    || "").trim(),
      description: descMap[(r.OBJ_NAME || "").trim()] || "",
      package:     (r.DEVCLASS  || "").trim(),
      author:      (r.AUTHOR    || "").trim(),
    }));

    send(res, 200, { objects, total: objects.length });
  } catch (e) {
    send(res, 200, { objects: [], total: 0, error: e.message });
  } finally {
    await closeClient(client);
  }
}

async function handleSource(name, res) {
  if (!validateName(name)) {
    return send(res, 400, { error: "Invalid object name" });
  }
  let client;
  try {
    client = await openClient();
    const result = await client.call("RPY_PROGRAM_READ", { PROGRAMM: name.toUpperCase() });
    const lines  = (result.SOURCE_EXTENDED || []).map(r => r.LINE || "");
    const source = lines.join("\n");

    let description = "";
    try {
      const dr = await readTable(
        client, "TRDIRT", ["NAME", "TEXT"],
        [`NAME = '${name.toUpperCase()}'`, "AND SPRSL = 'E'"], 1
      );
      if (dr.length) description = (dr[0].TEXT || "").trim();
    } catch (_) {}

    send(res, 200, { name, source, description, lineCount: lines.length, charCount: source.length });
  } catch (e) {
    send(res, 200, { name, source: "", description: "", lineCount: 0, charCount: 0, error: e.message });
  } finally {
    await closeClient(client);
  }
}

async function handleSmartForm(name, res) {
  if (!validateName(name)) {
    return send(res, 400, { error: "Invalid SmartForm name" });
  }
  let client;
  try {
    client = await openClient();
    const result = await client.call("SSF_FUNCTION_MODULE_NAME", { FORMNAME: name.toUpperCase() });
    const fmName = (result.FUNCNAME || "").trim();

    let source = "";
    try {
      const sr = await client.call("RPY_PROGRAM_READ", {
        PROGRAMM: `/1BCDWB/SF${name.substring(0, 25).toUpperCase()}`,
      });
      source = (sr.SOURCE_EXTENDED || []).map(r => r.LINE || "").join("\n");
    } catch (_) {}

    send(res, 200, { name, fmName, source, charCount: source.length });
  } catch (e) {
    send(res, 200, { name, fmName: "", source: "", charCount: 0, error: e.message });
  } finally {
    await closeClient(client);
  }
}

// ── HTTP server ───────────────────────────────────────────────────────────────
const PORT = Number(process.env.SAP_BRIDGE_PORT || 5001);

const server = http.createServer(async (req, res) => {
  const parsed = url.parse(req.url, true);
  const route  = parsed.pathname;
  const q      = parsed.query;

  if (req.method === "OPTIONS") {
    res.writeHead(204, { "Access-Control-Allow-Origin": "*" });
    return res.end();
  }

  if (req.method !== "GET") {
    return send(res, 405, { error: "Method not allowed" });
  }

  try {
    if      (route === "/health")    await handleHealth(res);
    else if (route === "/search")    await handleSearch((q.q || "").trim(), res);
    else if (route === "/source")    await handleSource((q.name || "").trim(), res);
    else if (route === "/smartform") await handleSmartForm((q.name || "").trim(), res);
    else send(res, 404, { error: "Not found" });
  } catch (e) {
    console.error("[bridge] unhandled:", e.message);
    send(res, 500, { error: e.message });
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[bridge] SAP RFC Bridge listening on http://127.0.0.1:${PORT}`);
  console.log(`[bridge] SAP: ${SAP.ashost || "(not set)"}  sysnr=${SAP.sysnr}  client=${SAP.client}`);
  if (!rfc) console.error("[bridge] ERROR: node-rfc not loaded — fix the path above");
});

server.on("error", e => {
  console.error("[bridge] Server error:", e.message);
  process.exit(1);
});
