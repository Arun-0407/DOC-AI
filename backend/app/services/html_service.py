"""
Enterprise SAP Technical Documentation — HTML Generator
Generates Gold-Standard self-contained HTML documents matching IBM Bob reference quality.
All extracted SAP objects documented — zero placeholders, zero AI summaries.
"""
import json as _json
import html as _html
from datetime import datetime


def _j(v):
    if v is None:
        return {}
    if isinstance(v, str):
        try:
            return _json.loads(v)
        except Exception:
            return {}
    return v if isinstance(v, dict) else {}


def _s(d, *keys, default=""):
    v = d
    for k in keys:
        if isinstance(v, dict):
            v = v.get(k)
        else:
            return default
        if v is None:
            return default
    return str(v) if v not in (None, "") else default


def _esc(text):
    """HTML-escape text safely."""
    if text is None:
        return ""
    return _html.escape(str(text))


# ═══════════════════════════════════════════════════════════════════════
# CSS DESIGN SYSTEM — matches Gold Standard reference exactly
# ═══════════════════════════════════════════════════════════════════════
CSS = """
/* ── Reset ─────────────────────────────────────────────── */
*{box-sizing:border-box;margin:0;padding:0}

/* ── Base ───────────────────────────────────────────────── */
html{scroll-behavior:smooth}
body{
  font-family:-apple-system,"Segoe UI",system-ui,Arial,sans-serif;
  font-size:13px;line-height:1.55;color:#1f2328;
  background:#edf0f4;
}

/* ── Page wrapper — full width, no artificial 960px cap ── */
.page{
  width:100%;max-width:1280px;
  margin:0 auto;background:#fff;
  box-shadow:0 0 24px rgba(0,0,0,.08);
}

/* ── COVER ─────────────────────────────────────────────── */
.cover{background:#1a3a6b;color:#fff;padding:32px 40px 28px;width:100%}
.cover h1{font-size:20px;font-weight:800;letter-spacing:.2px;margin-bottom:3px;word-break:break-word}
.cover .sub{font-size:12px;opacity:.8;margin-bottom:14px}
.brow{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.bx{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);
    color:#fff;font-size:10px;font-weight:600;padding:2px 9px;border-radius:20px;
    white-space:nowrap}
.mgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px}
.mcard{background:rgba(255,255,255,.1);border-radius:6px;padding:9px 12px;min-width:0}
.mcard .ml{font-size:10px;opacity:.65;text-transform:uppercase;letter-spacing:.5px}
.mcard .mv{font-size:12px;font-weight:700;margin-top:2px;word-break:break-word}

/* ── NAV ────────────────────────────────────────────────── */
.nav{display:flex;flex-wrap:wrap;background:#1e4080;width:100%}
.nav span{color:rgba(255,255,255,.65);padding:9px 16px;font-size:10px;
          font-weight:700;letter-spacing:.5px;text-transform:uppercase;
          border-bottom:3px solid transparent;white-space:nowrap}
.nav span.a{color:#fff;border-bottom-color:#60a5fa}

/* ── SECTION ────────────────────────────────────────────── */
.sec{padding:24px 40px 0;width:100%}
.vtitle{
  font-size:15px;font-weight:800;color:#1a3a6b;
  padding-bottom:5px;border-bottom:3px solid #1a3a6b;
  margin-bottom:4px;
}
.vdesc{font-size:12px;color:#6b7280;margin-bottom:14px}
.divider{height:1px;background:#e5e7eb;margin:20px 0}

/* ── CARDS ──────────────────────────────────────────────── */
.crow{display:grid;gap:12px;margin-bottom:14px;width:100%}
.c2{grid-template-columns:repeat(2,1fr)}
.c3{grid-template-columns:repeat(3,1fr)}
.c4{grid-template-columns:repeat(4,1fr)}
.c5{grid-template-columns:repeat(5,1fr)}
.card{
  background:#f8fafc;border:1px solid #e2e8f0;
  border-radius:6px;padding:12px 14px;min-width:0;
  word-break:break-word;overflow:hidden;
}
.card h4{
  font-size:10px;font-weight:700;color:#1a3a6b;
  text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px;
}
.card ul{padding-left:14px}
.card li{font-size:12px;color:#374151;margin-bottom:2px;word-break:break-word}
.card p{font-size:12px;color:#374151;word-break:break-word}
.kpi{text-align:center}
.kpi .num{font-size:26px;font-weight:800;color:#1a3a6b}
.kpi .lbl{font-size:10px;color:#6b7280;margin-top:2px}

/* ── TABLES ─────────────────────────────────────────────── */
.tbl-wrap{width:100%;overflow-x:auto;margin-bottom:14px;-webkit-overflow-scrolling:touch}
table{
  width:100%;border-collapse:collapse;font-size:12px;
  table-layout:fixed;word-break:break-word;
}
th{
  background:#1a3a6b;color:#fff;text-align:left;
  padding:7px 9px;font-size:11px;letter-spacing:.3px;font-weight:700;
  word-break:break-word;
}
td{
  padding:6px 9px;border-bottom:1px solid #e5e7eb;
  vertical-align:top;word-break:break-word;overflow-wrap:break-word;
}
tr:nth-child(even) td{background:#f8fafc}

/* ── INLINE CODE ────────────────────────────────────────── */
code{
  font-family:Consolas,"Courier New",monospace;
  font-size:11px;background:#eef2f8;
  padding:1px 5px;border-radius:3px;
  color:#1a3a6b;word-break:break-all;
}

/* ── CODE BLOCKS (ABAP source) ──────────────────────────── */
pre,pre code,.src-block{
  font-family:Consolas,"Courier New",monospace;
  font-size:11px;line-height:1.6;
  background:#f4f6fa;border:1px solid #dde3ed;
  border-radius:5px;padding:12px 14px;
  overflow-x:auto;white-space:pre;
  word-wrap:normal;width:100%;display:block;
  -webkit-overflow-scrolling:touch;margin:6px 0 14px;
}

.h4t{
  font-size:11px;font-weight:700;color:#1a3a6b;
  text-transform:uppercase;letter-spacing:.5px;margin:14px 0 6px;
}
.note{
  border-left:4px solid #3b82f6;background:#eff6ff;
  padding:9px 13px;border-radius:0 5px 5px 0;
  font-size:12px;margin:8px 0;color:#1e3a5f;word-break:break-word;
}
.warn{
  border-left:4px solid #f59e0b;background:#fffbeb;
  padding:9px 13px;border-radius:0 5px 5px 0;
  font-size:12px;margin:8px 0;color:#78350f;word-break:break-word;
}

/* ── FLOWCHART ───────────────────────────────────────────── */
.fc-wrap{
  background:#f8fafc;border:1px solid #e2e8f0;
  border-radius:6px;padding:20px 16px;margin-bottom:14px;
  overflow-x:auto;width:100%;
}
.fc{display:flex;flex-direction:column;align-items:center;gap:0;min-width:0}
.fc-node{
  text-align:center;padding:9px 18px;border-radius:6px;
  font-size:12px;width:100%;max-width:560px;
  word-break:break-word;
}
.fc-node.pill{
  background:#1a3a6b;color:#fff;border-radius:50px;
  font-weight:700;font-size:12px;width:auto;
  max-width:200px;padding:7px 18px;
}
.fc-node.proc{background:#eff6ff;border:2px solid #3b82f6;color:#1a3a6b}
.fc-node.proc strong{display:block;font-weight:700;margin-bottom:2px}
.fc-node.proc span{font-size:11px;color:#6b7280}
.fc-node.dec{background:#fffbeb;border:2px solid #f59e0b;color:#1a3a6b}
.fc-node.dec strong{display:block;font-weight:700;margin-bottom:2px;color:#92400e}
.fc-node.dec span{font-size:11px;color:#6b7280}
.fc-node.loop-bar{
  background:#1a3a6b;color:#fff;font-weight:700;
  font-size:11px;width:100%;max-width:560px;
  border-radius:4px;padding:9px 14px;
}
.fc-node.sfm{background:#ecfdf5;border:2px solid #059669;color:#1a3a6b}
.fc-node.sfm strong{display:block;font-weight:700;margin-bottom:2px}
.fc-node.sfm span{font-size:11px;color:#6b7280}
.fc-arrow{width:2px;height:20px;background:#3b82f6;margin:0 auto;flex-shrink:0}

/* ── DFD ─────────────────────────────────────────────────── */
.dfd-wrap{
  background:#f8fafc;border:1px solid #e2e8f0;
  border-radius:6px;padding:16px;margin-bottom:14px;
  overflow-x:auto;width:100%;
}
.dfd-row{
  display:flex;align-items:center;gap:0;
  justify-content:center;margin-bottom:8px;
  flex-wrap:wrap;
}
.dfd-ext{
  background:#1a3a6b;color:#fff;font-weight:700;
  font-size:11px;padding:9px 12px;border-radius:5px;
  text-align:center;min-width:70px;word-break:break-word;
}
.dfd-proc{
  background:#eff6ff;border:2px solid #3b82f6;color:#1a3a6b;
  font-size:11px;padding:9px 12px;border-radius:50%;
  text-align:center;min-width:80px;min-height:60px;
  display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  word-break:break-word;
}
.dfd-proc strong{font-size:11px;display:block}
.dfd-store{
  background:#fff7ed;border-top:2px solid #f59e0b;
  border-bottom:2px solid #f59e0b;font-size:11px;
  padding:5px 10px;text-align:center;min-width:110px;
  font-weight:600;color:#78350f;word-break:break-word;
}

/* ── CONNECTIVITY ────────────────────────────────────────── */
.conn-wrap{
  background:#f8fafc;border:1px solid #e2e8f0;
  border-radius:6px;padding:16px;margin-bottom:14px;
  overflow-x:auto;width:100%;
}
.conn-grid{
  display:grid;
  grid-template-columns:1fr minmax(120px,160px) 1fr;
  gap:14px;align-items:start;min-width:480px;
}
.conn-center{
  background:#1a3a6b;color:#fff;border-radius:8px;
  padding:14px 10px;text-align:center;
}
.conn-center .prog{font-size:12px;font-weight:800;margin-bottom:3px;word-break:break-word}
.conn-left,.conn-right{display:flex;flex-direction:column;gap:6px}
.conn-item{border-radius:5px;padding:7px 9px;font-size:11px;word-break:break-word}
.conn-item strong{display:block;font-weight:700;margin-bottom:1px}
.conn-item span{font-size:10px;color:#6b7280}
.ci-sf{background:#ecfdf5;border:1px solid #6ee7b7}
.ci-fm{background:#eff6ff;border:1px solid #93c5fd}
.ci-zt{background:#fffbeb;border:1px solid #fcd34d}
.ci-tr{background:#f5f3ff;border:1px solid #c4b5fd}
.conn-bot{
  margin-top:12px;
  display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
  gap:8px;
}

/* ── BADGE ───────────────────────────────────────────────── */
.sb{display:inline-block;font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px;white-space:nowrap}
.sb-r{background:#fee2e2;color:#991b1b}
.sb-g{background:#d1fae5;color:#065f46}
.sb-b{background:#dbeafe;color:#1e40af}
.sb-o{background:#fef3c7;color:#92400e}

/* ── DARK CODE BLOCK (inline source viewer) ──────────────── */
.code-block{
  background:#1e293b;color:#e2e8f0;
  padding:12px 14px;border-radius:5px;
  font-family:Consolas,"Courier New",monospace;
  font-size:11px;line-height:1.65;
  overflow-x:auto;margin:6px 0 14px;
  white-space:pre;word-wrap:normal;
  width:100%;display:block;
  -webkit-overflow-scrolling:touch;
}

/* ── FOOTER ──────────────────────────────────────────────── */
.footer{
  margin-top:32px;padding:12px 40px;
  border-top:1px solid #e5e7eb;
  text-align:center;font-size:11px;color:#9ca3af;
}

/* ── COVERAGE ────────────────────────────────────────────── */
.cov-pass{
  background:#d1fae5;border:1px solid #6ee7b7;
  padding:9px 13px;border-radius:5px;
  font-size:12px;color:#065f46;margin:8px 0;
}
.cov-warn{
  background:#fef3c7;border:1px solid #fcd34d;
  padding:9px 13px;border-radius:5px;
  font-size:12px;color:#92400e;margin:8px 0;
}

/* ── RESPONSIVE BREAKPOINTS ──────────────────────────────── */
@media (max-width:900px){
  .c4{grid-template-columns:repeat(2,1fr)}
  .c5{grid-template-columns:repeat(2,1fr)}
  .c3{grid-template-columns:repeat(2,1fr)}
  .mgrid{grid-template-columns:repeat(2,1fr)}
  .conn-grid{grid-template-columns:1fr}
  .sec{padding:16px 20px 0}
  .cover{padding:24px 20px}
}
@media (max-width:600px){
  .c2,.c3,.c4,.c5{grid-template-columns:1fr}
  .mgrid{grid-template-columns:1fr}
}

/* ── PRINT ───────────────────────────────────────────────── */
@media print{
  body{background:#fff;font-size:11px}
  .nav{display:none}
  .page{max-width:100%;box-shadow:none}
  .sec{padding:14px 24px 0}
  .cover{padding:24px;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .fc-wrap,.dfd-wrap,.conn-wrap{page-break-inside:avoid}
  table{page-break-inside:auto;table-layout:fixed}
  tr{page-break-inside:avoid}
  pre,.src-block,.code-block{
    white-space:pre-wrap;overflow-x:visible;
    word-break:break-all;font-size:9.5px;
  }
  .tbl-wrap{overflow-x:visible}
  .divider{margin:12px 0}
}
"""


# ═══════════════════════════════════════════════════════════════════════
# TABLE BUILDER
# ═══════════════════════════════════════════════════════════════════════
def _table(headers, rows):
    """Build a responsive data table wrapped in overflow-x:auto container."""
    if not rows:
        return '<p style="font-size:12px;color:#6b7280;margin:6px 0">No records extracted.</p>'
    h = "".join(f"<th>{_esc(str(hdr))}</th>" for hdr in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{str(c)}</td>" for c in row)
        body.append(f"<tr>{cells}</tr>")
    inner = f'<table><thead><tr>{h}</tr></thead><tbody>{"".join(body)}</tbody></table>'
    return f'<div class="tbl-wrap">{inner}</div>'


def _code(text):
    """Wrap text in code tag."""
    return f"<code>{_esc(str(text))}</code>"


# ═══════════════════════════════════════════════════════════════════════
# MAIN GENERATOR
# ═══════════════════════════════════════════════════════════════════════
def generate_html(document) -> str:
    """Generate Gold-Standard enterprise SAP technical documentation HTML."""

    # ── Extract all data sources ──
    cv = _j(document.cover_data) if hasattr(document, 'cover_data') else {}
    bv = _j(document.business_view) if hasattr(document, 'business_view') else {}
    tv = _j(document.technical_view) if hasattr(document, 'technical_view') else {}
    sa = _j(document.source_analysis) if hasattr(document, 'source_analysis') else {}
    da = _j(document.database_analysis) if hasattr(document, 'database_analysis') else {}
    ad = _j(document.api_dependency) if hasattr(document, 'api_dependency') else {}
    pf = _j(document.process_flow) if hasattr(document, 'process_flow') else {}
    sr = _j(document.security_review) if hasattr(document, 'security_review') else {}
    pr = _j(document.performance_review) if hasattr(document, 'performance_review') else {}
    ar = _j(document.ai_recommendations) if hasattr(document, 'ai_recommendations') else {}
    mh = _j(document.modification_history) if hasattr(document, 'modification_history') else {}
    dg = _j(document.diagrams) if hasattr(document, 'diagrams') else {}
    rd = _j(document.reference_data) if hasattr(document, 'reference_data') else {}

    # ── Get parsed metadata (direct extraction) ──
    pm = getattr(document, '_parsed_metadata', None) or {}
    if not pm and hasattr(document, 'upload') and document.upload:
        raw = document.upload.parsed_metadata
        pm = raw if isinstance(raw, dict) else {}

    st = pm.get("source_type", "")
    is_sf = st == "smartform_xml"
    hdr = pm.get("header", {})
    iface = pm.get("interface", {})

    title = document.title or pm.get("program_name", "") or _s(cv, "program_name") or "SAP Technical Documentation"

    parts = []

    # ══════════════════════════════════════════════════════════════════
    # COVER PAGE
    # ══════════════════════════════════════════════════════════════════
    prog_name = pm.get("program_name") or _s(cv, "program_name") or title
    description = pm.get("description") or _s(cv, "description") or "Complete Technical Documentation"
    module = _s(cv, "module") or ""
    obj_type = st.replace("_", " ").title() if st else _s(cv, "object_type") or ""
    tcode = _s(cv, "tcode") or ""
    package = hdr.get("devclass", "") or _s(cv, "package") or ""
    version = hdr.get("version", "") or _s(cv, "version") or ""
    author = hdr.get("firstuser", "") or _s(cv, "author") or ""
    creation_date = hdr.get("firstdate", "") or _s(cv, "creation_date") or ""
    last_mod = hdr.get("lastdate", "") or _s(cv, "last_modified_date") or ""
    last_user = hdr.get("lastuser", "") or ""
    master_lang = hdr.get("masterlang", "") or ""
    tech_consultant = _s(cv, "technical_consultant") or ""
    func_consultant = _s(cv, "functional_consultant") or ""
    project = _s(cv, "project_name") or ""
    msg_class = _s(cv, "message_class") or ""

    # Badges
    badges = []
    if module:
        badges.append(f"{_esc(module)} Module")
    if obj_type:
        badges.append(_esc(obj_type))
    if tcode:
        badges.append(f"T-Code: {_esc(tcode)}")
    if creation_date:
        badges.append(f"Created: {_esc(creation_date)}")
    if last_mod:
        badges.append(f"Last Modified: {_esc(last_mod)}")
    badge_html = "".join(f'<span class="bx">{b}</span>' for b in badges)

    # Metadata cards
    mcards = []
    card_data = [
        ("Functional Consultant", func_consultant),
        ("Technical Consultant", tech_consultant),
        ("Project", project),
        ("Transaction Code", tcode),
        ("Message Class", msg_class),
        ("Package / DevClass", package),
        ("Author / Created By", author),
        ("Last Modified By", last_user),
        ("Master Language", master_lang),
    ]
    for label, value in card_data:
        if value:
            mcards.append(f'<div class="mcard"><div class="ml">{_esc(label)}</div><div class="mv">{_esc(value)}</div></div>')

    parts.append(f'''<div class="cover">
  <h1>{_esc(prog_name)}</h1>
  <div class="sub">{_esc(description)}</div>
  <div class="brow">{badge_html}</div>
  <div class="mgrid">{"".join(mcards)}</div>
</div>''')

    # ══════════════════════════════════════════════════════════════════
    # NAVIGATION BAR
    # ══════════════════════════════════════════════════════════════════
    parts.append('''<div class="nav">
  <span class="a">● Business View</span>
  <span class="a">● Technical View</span>
  <span class="a">● Visual View</span>
  <span class="a">● Reference View</span>
</div>''')

    # ══════════════════════════════════════════════════════════════════
    # BUSINESS VIEW -> Object Inventory & Business Rules
    # ══════════════════════════════════════════════════════════════════
    kpis = bv.get("kpi_matrix", {}) or {}
    inventory = bv.get("object_inventory", []) or []
    rules_matrix = bv.get("business_rules_matrix", []) or []

    # KPI Cards
    kpi_items = []
    if kpis.get("total_tables"): kpi_items.append(("DB Tables", kpis.get("total_tables")))
    if kpis.get("total_apis"): kpi_items.append(("APIs", kpis.get("total_apis")))
    if kpis.get("total_classes"): kpi_items.append(("Classes", kpis.get("total_classes")))
    if kpis.get("total_smart_forms"): kpi_items.append(("SmartForms", kpis.get("total_smart_forms")))
    if kpis.get("total_windows"): kpi_items.append(("Windows", kpis.get("total_windows")))
    if kpis.get("total_conditions"): kpi_items.append(("Conditions", kpis.get("total_conditions")))

    display_kpis = kpi_items[:6] if kpi_items else [("Tables", len(pm.get("tables_used", []))), ("Variables", len(pm.get("variables_declared", [])))]
    kpi_grid_class = f"c{len(display_kpis)}" if len(display_kpis) <= 5 else "c4"
    kpi_html = "".join(f'<div class="card kpi"><div class="num">{v}</div><div class="lbl">{_esc(l)}</div></div>' for l, v in display_kpis)

    inv_html = ""
    if inventory:
        inv_html += '<div class="h4t">Object Inventory Matrix</div>'
        inv_rows = [[_esc(i.get("object_type", "")), _code(i.get("object_name", "")), str(i.get("count", "")), _esc(i.get("purpose", ""))] for i in inventory]
        inv_html += _table(["Object Type", "Object Name", "Count", "Purpose"], inv_rows)

    rules_html = ""
    if rules_matrix:
        rules_html += '<div class="h4t">Business Rules Matrix</div>'
        rule_rows = [[_code(r.get("rule_id", "")), _esc(r.get("condition", "")), _esc(r.get("business_logic", "")), _code(r.get("referenced_objects", ""))] for r in rules_matrix]
        rules_html += _table(["Rule ID", "Condition", "Business Logic", "Referenced Objects"], rule_rows)

    parts.append(f'''<div class="sec">
  <div style="margin-top:24px"></div>
  <div class="vtitle">Object Inventory & Business Rules</div>
  <div class="vdesc">Strict SAP KT matrix mapping of all objects and technical business rules.</div>
  <div class="crow {kpi_grid_class}">{kpi_html}</div>
  {inv_html}
  {rules_html}
</div>
<div class="divider"></div>''')

    # ══════════════════════════════════════════════════════════════════
    # TECHNICAL VIEW
    # ══════════════════════════════════════════════════════════════════
    parts.append('''<div class="sec">
  <div class="vtitle">Technical View</div>
  <div class="vdesc">Program specifications, all called objects, data objects, and component details</div>''')

    # ── Program Metadata ──
    pm_meta = tv.get("program_metadata", {}) or {}
    pm_rows = []
    meta_fields = [
        ("Report / Form Name", pm.get("program_name") or pm_meta.get("program_name", "")),
        ("Description", pm.get("description") or pm_meta.get("description", "")),
        ("Object Type", st.replace("_", " ").title() if st else pm_meta.get("type", "")),
        ("Transaction Code", pm_meta.get("transaction_code", "") or tcode),
        ("Package / DevClass", hdr.get("devclass", "") or pm_meta.get("package", "")),
        ("Default Smart Form", pm_meta.get("default_smart_form", "")),
        ("Message Class", pm_meta.get("message_class", "") or msg_class),
        ("Line Size", pm_meta.get("line_size", "")),
        ("Application Component", pm_meta.get("application_component", "")),
    ]
    for label, value in meta_fields:
        if value:
            pm_rows.append([label, f"{_code(value)}"])

    if pm_rows:
        parts.append('<div class="h4t">Program Metadata</div>')
        parts.append(_table(["Attribute", "Value"], pm_rows))

    # ── Function Module Matrix ──
    cfms = tv.get("call_function_statements", [])
    if not cfms:
        # Fallback to extracted + AI data
        all_fms = []
        for cat in ["function_modules", "bapis", "rfcs"]:
            its = ad.get(cat, [])
            if isinstance(its, list):
                all_fms.extend(its)
        fm_pm = pm.get("function_calls", [])
        cfms = all_fms or fm_pm

    if cfms and isinstance(cfms, list):
        parts.append('<div class="h4t">All CALL FUNCTION Statements in the Program</div>')
        fm_rows = []
        for i, f in enumerate(cfms):
            if not isinstance(f, dict):
                f = {"name": str(f)}
            fm_rows.append([
                str(i + 1),
                _code(f.get("name", "")),
                _esc(f.get("type", f.get("source", ""))),
                _esc(f.get("where_called", "")),
                _esc(str(f.get("parameters_passed", f.get("parameters", "")))[:80]),
                _esc(f.get("returns", "")),
                _esc(f.get("purpose", f.get("description", ""))[:100]),
            ])
        parts.append(_table(["#", "Function Module", "Type", "Where Called", "Parameters Passed", "Returns", "Purpose"], fm_rows))

    # ── Transaction Matrix ──
    ctxns = tv.get("call_transaction_statements", [])
    if not ctxns:
        ctxns = pm.get("call_transactions", []) or ad.get("call_transactions", []) or []
    if ctxns and isinstance(ctxns, list):
        parts.append('<div class="h4t">All CALL TRANSACTION Statements in the Program</div>')
        txn_rows = []
        for i, t in enumerate(ctxns):
            if not isinstance(t, dict):
                t = {"name": str(t)}
            txn_rows.append([
                str(i + 1),
                _code(t.get("transaction", t.get("name", ""))),
                _esc(t.get("when_called", "")),
                _esc(t.get("memory_used", "")),
                _esc(t.get("purpose", ""))[:100],
            ])
        parts.append(_table(["#", "Transaction", "When Called", "Memory Used", "Purpose"], txn_rows))

    # ── Smart Forms Used (from AI) ──
    sf_list = ad.get("smart_forms", []) or tv.get("components", {}).get("smart_forms", []) or []
    if sf_list and isinstance(sf_list, list):
        parts.append('<div class="h4t">All Smart Forms Used</div>')
        sf_rows = []
        for sf in sf_list:
            if isinstance(sf, dict):
                sf_rows.append([
                    _code(sf.get("name", "")),
                    _esc(sf.get("condition", sf.get("description", ""))),
                    _esc(sf.get("pages", "")),
                    _esc(sf.get("called_via_fm", sf.get("interface", ""))[:100] if sf.get("called_via_fm") or sf.get("interface") else ""),
                ])
        if sf_rows:
            parts.append(_table(["Smart Form Name", "Condition", "Pages", "Interface — Key Parameters"], sf_rows))

    # ── Database Read Analysis ──
    read_ops = da.get("read_operations", []) or []
    sel_stmts = tv.get("select_statements", []) or []
    db_reads = read_ops or sel_stmts
    db_tables = pm.get("tables_used", []) or da.get("tables", []) or []

    if db_reads and isinstance(db_reads, list):
        parts.append('<div class="h4t">All SELECT / Database Read Operations</div>')
        dr_rows = []
        for i, r in enumerate(db_reads):
            if not isinstance(r, dict):
                continue
            dr_rows.append([
                str(i + 1),
                _code(r.get("table", r.get("name", ""))),
                _esc(r.get("operation", "SELECT")),
                _esc(r.get("key_conditions", r.get("key_fields", r.get("where_conditions", "")))),
                _esc(r.get("into_variable", "")),
                _esc(r.get("purpose", r.get("event_or_form", "")))[:100],
            ])
        if dr_rows:
            parts.append(_table(["#", "Table", "Operation", "Key Conditions", "Into Variable", "Purpose"], dr_rows))
    elif db_tables:
        # Fallback: show extracted tables
        parts.append('<div class="h4t">Database Tables Accessed</div>')
        dt_rows = []
        for i, t in enumerate(db_tables):
            if isinstance(t, dict):
                dt_rows.append([str(i + 1), _code(t.get("name", "")), _esc(t.get("operation", t.get("source", ""))), _esc(t.get("description", ""))])
            else:
                dt_rows.append([str(i + 1), _code(str(t)), "", ""])
        parts.append(_table(["#", "Table", "Operation / Source", "Description"], dt_rows))

    # ── Database Write Analysis ──
    write_ops = da.get("write_operations", []) or []
    if write_ops and isinstance(write_ops, list):
        parts.append('<div class="h4t">All Database WRITE Operations</div>')
        dw_rows = []
        for i, w in enumerate(write_ops):
            if not isinstance(w, dict):
                continue
            dw_rows.append([
                str(i + 1),
                _code(w.get("table", "")),
                _esc(w.get("operation", "")),
                _esc(w.get("when", "")),
                _esc(w.get("data_written", w.get("purpose", "")))[:100],
            ])
        if dw_rows:
            parts.append(_table(["#", "Table", "Operation", "When", "Data Written"], dw_rows))

    # ── Billing Type Behaviour Matrix ──
    bm = tv.get("behavior_matrix", [])
    if bm and isinstance(bm, list) and len(bm) > 0 and isinstance(bm[0], dict):
        parts.append('<div class="h4t">Billing Type Behaviour Matrix</div>')
        keys = list(bm[0].keys())
        bm_rows = []
        for row in bm:
            cells = []
            for k in keys:
                val = row.get(k, "")
                # Apply badge styling for Yes/No/Suppressed
                val_str = str(val)
                if val_str.lower() in ("yes", "true", "x"):
                    cells.append(f'<span class="sb sb-g">Yes</span>')
                elif val_str.lower() in ("no", "false", "suppressed"):
                    cells.append(f'<span class="sb sb-r">Suppressed</span>')
                else:
                    cells.append(_esc(val_str) if not val_str.startswith("Z") else _code(val_str))
            bm_rows.append(cells)
        parts.append(_table([k.replace("_", " ").title() for k in keys], bm_rows))

    # ── PERFORM Subroutines ──
    performs = tv.get("perform_subroutines", []) or sa.get("routines", []) or []
    if performs and isinstance(performs, list):
        parts.append('<div class="h4t">PERFORM Subroutines (FORMs) — All Details</div>')
        perf_rows = []
        for p in performs:
            if not isinstance(p, dict):
                continue
            tabs_read = p.get("tables_read", p.get("tables_accessed", []))
            tabs_write = p.get("tables_written", [])
            perf_rows.append([
                _code(p.get("name", "")),
                _esc(p.get("called_from", "")),
                _esc(p.get("logic_summary", p.get("logic_description", p.get("purpose", ""))))[:200],
                _esc(", ".join(tabs_read) if isinstance(tabs_read, list) else str(tabs_read)),
                _esc(", ".join(tabs_write) if isinstance(tabs_write, list) else str(tabs_write)),
            ])
        if perf_rows:
            parts.append(_table(["FORM", "Called From", "Logic", "Tables Read", "Tables Written"], perf_rows))

    # ── Program Components ──
    components = tv.get("components", {}) or {}
    includes = components.get("includes", pm.get("includes", []))
    classes = components.get("classes", pm.get("classes", []))
    if includes and isinstance(includes, list):
        parts.append('<div class="h4t">Include Programs</div>')
        inc_rows = [[str(i + 1), _code(inc.get("name", inc) if isinstance(inc, dict) else str(inc))] for i, inc in enumerate(includes)]
        parts.append(_table(["#", "Include Name"], inc_rows))
    if classes and isinstance(classes, list):
        parts.append('<div class="h4t">Classes Used</div>')
        cls_rows = []
        for i, c in enumerate(classes):
            if isinstance(c, dict):
                cls_rows.append([str(i + 1), _code(c.get("name", "")), _esc(c.get("description", "")), str(c.get("methods_count", len(c.get("methods", []))))])
            else:
                cls_rows.append([str(i + 1), _code(str(c)), "", ""])
        parts.append(_table(["#", "Class", "Description", "Methods"], cls_rows))

    parts.append('</div><div class="divider"></div>')

    # ══════════════════════════════════════════════════════════════════
    # SMARTFORM & ABAP MATRIX DETAILS (from Source Analysis)
    # ══════════════════════════════════════════════════════════════════
    has_sa = any([sa.get("smartform_layout_matrix"), sa.get("window_matrix"), sa.get("abap_block_summary")])
    if is_sf or has_sa:
        parts.append('''<div class="sec">
  <div class="vtitle">SmartForm & ABAP Source Matrices</div>
  <div class="vdesc">Strict technical tracking of all SmartForm elements, windows, conditions, and embedded ABAP blocks.</div>''')

        sf_layout = sa.get("smartform_layout_matrix", [])
        if sf_layout:
            parts.append(f'<div class="h4t">SmartForm Layout Matrix ({len(sf_layout)} nodes)</div>')
            lo_rows = [[_code(l.get("node_name", "")), _esc(l.get("type", "")), _esc(l.get("description", "")), _esc(l.get("conditions", "")), _code(l.get("logic", ""))] for l in sf_layout]
            parts.append(_table(["Node Name", "Type", "Description", "Conditions", "Logic"], lo_rows))

        sf_wins = sa.get("window_matrix", [])
        if sf_wins:
            parts.append(f'<div class="h4t">Window Matrix ({len(sf_wins)} windows)</div>')
            win_rows = [[_code(w.get("window_name", "")), _esc(w.get("window_type", "")), _esc(w.get("purpose", "")), _esc(w.get("elements_contained", ""))] for w in sf_wins]
            parts.append(_table(["Window Name", "Window Type", "Purpose", "Elements Contained"], win_rows))

        sf_conds = sa.get("conditions_matrix", [])
        if sf_conds:
            parts.append(f'<div class="h4t">Conditions & Business Rules Matrix ({len(sf_conds)} conditions)</div>')
            cond_rows = [[_code(c.get("condition_id", "")), _esc(c.get("node", "")), _code(c.get("logic", "")), _esc(c.get("business_meaning", ""))] for c in sf_conds]
            parts.append(_table(["Condition ID", "Node", "Logic", "Business Meaning"], cond_rows))

        sf_vars = sa.get("variable_matrix", [])
        if sf_vars:
            parts.append(f'<div class="h4t">Variable Matrix ({len(sf_vars)} variables)</div>')
            var_rows = [[_code(v.get("variable_name", "")), _esc(v.get("type", "")), _esc(v.get("direction", "")), _esc(v.get("purpose", ""))] for v in sf_vars]
            parts.append(_table(["Variable", "Type", "Direction", "Purpose"], var_rows))

        sf_texts = sa.get("text_element_matrix", [])
        if sf_texts:
            parts.append(f'<div class="h4t">Text Element Matrix ({len(sf_texts)} texts)</div>')
            txt_rows = [[_code(t.get("text_name", "")), _esc(t.get("window", "")), _esc(t.get("content_summary", ""))] for t in sf_texts]
            parts.append(_table(["Text Name", "Window", "Content Summary"], txt_rows))

        abap_blocks = sa.get("abap_block_summary", [])
        if abap_blocks:
            parts.append(f'<div class="h4t">Embedded ABAP Matrix ({len(abap_blocks)} blocks)</div>')
            abap_rows = [[_code(a.get("block_id", "")), _esc(a.get("location", "")), _esc(a.get("logic_summary", "")), _code(a.get("variables_used", "")), _code(a.get("tables_accessed", ""))] for a in abap_blocks]
            parts.append(_table(["Block ID", "Location", "Logic Summary", "Variables Used", "Tables Accessed"], abap_rows))

        parts.append('</div><div class="divider"></div>')

    # ══════════════════════════════════════════════════════════════════
    # VISUAL VIEW
    # ══════════════════════════════════════════════════════════════════
    parts.append('''<div class="sec">
  <div class="vtitle">Visual View</div>
  <div class="vdesc">Program Flowchart · Data Flow Diagram · Connectivity Diagram</div>''')

    # Generate HTML-based diagrams from extracted data
    try:
        from app.services.diagram_service import (
            generate_html_flowchart, generate_html_dfd, generate_html_connectivity
        )
        parts.append('<div class="h4t">Program Execution Flowchart</div>')
        parts.append(generate_html_flowchart(pm))
        parts.append('<div class="h4t">Data Flow Diagram (DFD) — Level 1</div>')
        parts.append(generate_html_dfd(pm))
        parts.append('<div class="h4t">Connectivity / Integration Diagram</div>')
        parts.append(generate_html_connectivity(pm))
    except ImportError:
        # Fallback to Mermaid diagrams if HTML diagram functions not available
        for key, label in [
            ("high_level_flow_mermaid", "High-Level Process Flow"),
            ("detailed_flow_mermaid", "Detailed Process Flow"),
            ("execution_flow_mermaid", "Execution Flow"),
        ]:
            val = pf.get(key, "") or dg.get(key.replace("_mermaid", ""), "")
            if val and isinstance(val, str) and len(val) > 15:
                parts.append(f'<div class="h4t">{label}</div>')
                parts.append(f'<div class="mermaid">{val}</div>')

        # Other diagram types
        for key, label in [
            ("flowchart", "Flowchart"),
            ("data_flow", "Data Flow"),
            ("sequence_diagram", "Sequence Diagram"),
            ("er_diagram", "ER Diagram"),
            ("dependency_diagram", "Dependency Diagram"),
            ("connectivity_diagram", "Connectivity Diagram"),
        ]:
            val = dg.get(key, "")
            if val and isinstance(val, str) and len(val) > 15:
                parts.append(f'<div class="h4t">{label}</div>')
                parts.append(f'<div class="mermaid">{val}</div>')

    parts.append('</div><div class="divider"></div>')

    # ══════════════════════════════════════════════════════════════════
    # REFERENCE VIEW
    # ══════════════════════════════════════════════════════════════════
    parts.append('''<div class="sec">
  <div class="vtitle">Reference View</div>
  <div class="vdesc">All data dictionary objects, structures, tables, variables, and modification history</div>''')

    # Custom Structures
    custom_structs = rd.get("custom_structures", rd.get("structures", []))
    if custom_structs and isinstance(custom_structs, list):
        parts.append('<div class="h4t">All Custom Structures (DDIC)</div>')
        cs_rows = []
        for s in custom_structs:
            if isinstance(s, dict):
                cs_rows.append([
                    _code(s.get("name", "")),
                    _esc(s.get("used_as", s.get("description", ""))),
                    _esc(s.get("key_fields", "")),
                ])
        if cs_rows:
            parts.append(_table(["Structure", "Used As", "Key Fields"], cs_rows))

    # Custom Database Tables
    custom_tables = rd.get("custom_tables", [])
    if not custom_tables:
        # Build from extracted data
        custom_tables = [t for t in (da.get("tables", []) or [])
                          if isinstance(t, dict) and t.get("name", "").startswith("Z")]
    if custom_tables and isinstance(custom_tables, list):
        parts.append('<div class="h4t">All Custom Database Tables (DDIC)</div>')
        ct_rows = []
        for t in custom_tables:
            if isinstance(t, dict):
                ct_rows.append([
                    _code(t.get("name", "")),
                    _esc(t.get("key_fields", ", ".join(t.get("keys", [])))),
                    _esc(t.get("data_fields", "")),
                    _esc(t.get("role_in_program", t.get("purpose", t.get("description", "")))),
                ])
        if ct_rows:
            parts.append(_table(["Table", "Key Fields", "Data Fields", "Role in Program"], ct_rows))

    # SAP Standard Tables
    std_tables = [t for t in (da.get("tables", []) or [])
                   if isinstance(t, dict) and not t.get("name", "").startswith("Z")]
    if std_tables:
        parts.append('<div class="h4t">SAP Standard Tables Referenced</div>')
        st_rows = [[_code(t.get("name", "")), _esc(t.get("description", "")),
                      _esc(", ".join(t.get("crud", t.get("operations", []))) if isinstance(t.get("crud", t.get("operations", [])), list) else str(t.get("crud", "")))]
                     for t in std_tables]
        parts.append(_table(["Table", "Description", "CRUD Operations"], st_rows))

    # Key Program Variables (from AI reference tables)
    key_vars = rd.get("key_variables", [])
    if key_vars and isinstance(key_vars, list):
        parts.append('<div class="h4t">Key Program Variables</div>')
        kv_rows = [[_code(v.get("name", "")), _esc(v.get("type", "")), _esc(v.get("purpose", ""))]
                     for v in key_vars if isinstance(v, dict)]
        if kv_rows:
            parts.append(_table(["Variable", "Type", "Purpose"], kv_rows))

    # Data Elements
    data_elements = rd.get("data_elements", [])
    if data_elements and isinstance(data_elements, list):
        parts.append('<div class="h4t">Data Elements</div>')
        de_rows = [[_code(d.get("name", "")), _esc(d.get("description", ""))]
                     for d in data_elements if isinstance(d, dict)]
        if de_rows:
            parts.append(_table(["Data Element", "Description"], de_rows))

    # Domains
    domains = rd.get("domains", [])
    if domains and isinstance(domains, list):
        parts.append('<div class="h4t">Domains</div>')
        dom_rows = [[_code(d.get("name", "")), _esc(d.get("description", ""))]
                      for d in domains if isinstance(d, dict)]
        if dom_rows:
            parts.append(_table(["Domain", "Description"], dom_rows))

    # ── Modification History ──
    hist = mh.get("history", []) or []
    if hist and isinstance(hist, list):
        parts.append('<div class="h4t">Modification History</div>')
        mh_rows = []
        for h in hist:
            if isinstance(h, dict):
                mh_rows.append([
                    _esc(h.get("date", "")),
                    _esc(h.get("author", "")),
                    _esc(h.get("transport_ref", h.get("object", ""))),
                    _esc(h.get("modification", h.get("change_description", ""))),
                ])
        if mh_rows:
            parts.append(_table(["Date", "Author", "Reference", "Change Description"], mh_rows))

    parts.append('</div>')

    # ══════════════════════════════════════════════════════════════════
    # SECURITY & PERFORMANCE ANALYSIS
    # ══════════════════════════════════════════════════════════════════
    has_security = sr.get("auth_objects") or sr.get("sensitive_data_access") or sr.get("compliance_issues")
    has_perf = pr.get("select_in_loop") or pr.get("nested_loops") or pr.get("optimization_opportunities")

    if has_security or has_perf:
        parts.append('<div class="divider"></div><div class="sec">')
        parts.append('<div class="vtitle">Analysis</div>')
        parts.append('<div class="vdesc">Security review, performance analysis, and enhancement opportunities</div>')

        # Security
        if has_security:
            sec_score = sr.get("security_score", "N/A")
            parts.append(f'<div class="h4t">Security Review — Score: {sec_score}/100</div>')
            auth_objs = sr.get("auth_objects", [])
            if auth_objs and isinstance(auth_objs, list):
                ao_rows = [[_code(a.get("name", "")), _esc(a.get("field", "")),
                              _esc(a.get("description", "")), _esc(a.get("severity", ""))]
                             for a in auth_objs if isinstance(a, dict)]
                if ao_rows:
                    parts.append(_table(["Auth Object", "Field", "Description", "Severity"], ao_rows))

        # Performance
        if has_perf:
            perf_score = pr.get("performance_score", "N/A")
            parts.append(f'<div class="h4t">Performance Review — Score: {perf_score}/100</div>')
            for cat_key, cat_label in [("select_in_loop", "SELECT in LOOP"), ("nested_loops", "Nested Loops"), ("optimization_opportunities", "Optimization")]:
                items = pr.get(cat_key, [])
                if items and isinstance(items, list):
                    p_rows = [[_esc(p.get("location", "")), _esc(p.get("issue", "")), _esc(p.get("suggestion", ""))]
                               for p in items if isinstance(p, dict)]
                    if p_rows:
                        parts.append(f'<div style="font-size:11px;font-weight:600;color:#92400e;margin:8px 0 4px">{cat_label}</div>')
                        parts.append(_table(["Location", "Issue", "Suggestion"], p_rows))

        # AI Recommendations
        if ar:
            parts.append('<div class="h4t">S/4HANA Readiness & Modernization</div>')
            scores = [
                ("Code Quality", ar.get("code_quality_score")),
                ("Maintainability", ar.get("maintainability_score")),
                ("Performance", ar.get("performance_score")),
                ("Security", ar.get("security_score")),
                ("S/4HANA Readiness", ar.get("s4hana_readiness_score")),
                ("RAP Migration", ar.get("rap_migration_score")),
            ]
            score_rows = [[_esc(s[0]), f"{s[1]}/100" if s[1] is not None else "N/A"] for s in scores]
            parts.append(_table(["Metric", "Score"], score_rows))

            sug = ar.get("refactoring_suggestions", [])
            if sug and isinstance(sug, list):
                parts.append('<div style="font-size:11px;font-weight:600;color:#1a3a6b;margin:8px 0 4px">Refactoring Suggestions</div>')
                sg_rows = [[str(i + 1), _esc(s.get("title", "")), _esc(s.get("description", "")[:100]),
                              _esc(s.get("priority", "")), _esc(s.get("effort", ""))]
                             for i, s in enumerate(sug) if isinstance(s, dict)]
                if sg_rows:
                    parts.append(_table(["#", "Title", "Description", "Priority", "Effort"], sg_rows))

        parts.append('</div>')

    # ══════════════════════════════════════════════════════════════════
    # COVERAGE VALIDATION REPORT
    # ══════════════════════════════════════════════════════════════════
    coverage = cv.get("_coverage_report", {})
    if coverage:
        cov_status = coverage.get("status", "")
        cov_total = coverage.get("total_extracted", 0)
        cov_documented = coverage.get("total_documented", 0)
        gaps = coverage.get("gaps", [])
        if cov_status == "PASS":
            parts.append(f'<div class="cov-pass"><strong>✓ Object Coverage: 100%</strong> — All {cov_total} extracted objects documented.</div>')
        elif gaps:
            gap_detail = " · ".join(f"{g['object_type']}: {g['documented']}/{g['extracted']}" for g in gaps)
            parts.append(f'<div class="cov-warn"><strong>⚠ Object Coverage: {cov_documented}/{cov_total}</strong> — {gap_detail}</div>')

    # ══════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts.append(f'''<div class="footer">Generated by DOC AI — Enterprise SAP Documentation Platform · {_esc(prog_name)} · {now} · For team sharing — Open in browser → Ctrl+P → Save as PDF</div>''')

    # ══════════════════════════════════════════════════════════════════
    # ASSEMBLE FINAL HTML
    # ══════════════════════════════════════════════════════════════════
    mermaid_script = ""
    # Check if any Mermaid diagrams exist
    full_content = "\n".join(parts)
    if "mermaid" in full_content:
        mermaid_script = '<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script><script>mermaid.initialize({startOnLoad:true});</script>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>{_esc(prog_name)}</title>
{mermaid_script}
<style>{CSS}</style>
</head>
<body>
<div class="page">
{full_content}
</div>
</body>
</html>'''
