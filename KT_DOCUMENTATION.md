# DOC AI — Complete Knowledge Transfer (KT) Documentation
### Target Audience: New SAP ABAP Developer
### Classification: Internal Technical Reference

> **How to read this document:** Every section is written so that a new developer can understand the system without opening SAP, the codebase, or any other tool. Business purpose is explained first, technical implementation second.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Process](#2-business-process)
3. [Technical Architecture](#3-technical-architecture)
4. [Selection Screen Analysis](#4-selection-screen-analysis)
5. [Global Variables and Configuration](#5-global-variables-and-configuration)
6. [Forms and Methods Explanation](#6-forms-and-methods-explanation)
7. [Tables with Purpose](#7-tables-with-purpose)
8. [SmartForm Deep Analysis](#8-smartform-deep-analysis)
9. [Dependency Map](#9-dependency-map)
10. [Debugging Guide](#10-debugging-guide)
11. [New Developer KT Notes](#11-new-developer-kt-notes)
12. [Common Issues and Fixes](#12-common-issues-and-fixes)

---

## 1. Executive Summary

### What is DOC AI?

DOC AI is an **AI-powered SAP Technical Documentation Generator**. Its single purpose is to automatically create professional, human-quality technical design documents from SAP ABAP source code — without a developer having to write a single word manually.

### Why Does It Exist?

In every SAP project, developers spend days or weeks writing technical design documents (TDDs) for ABAP reports, SmartForms, function modules, classes, and other SAP objects. These documents are required for:
- Knowledge transfer to new team members
- Audit and compliance trails
- Client handover packages
- SAP system upgrades and S/4HANA migrations

DOC AI eliminates that manual effort. A developer uploads ABAP source code (or connects to a live SAP system), clicks Generate, and receives a complete 14-section technical document in minutes.

### Who Are the Users?

| Role | What They Do in DOC AI |
|------|------------------------|
| SAP ABAP Developer | Uploads code, generates docs, uses AI Chat |
| SAP Functional Consultant | Reviews the business view sections |
| Project Manager | Uses docs for sign-off, audits, handover |
| System Administrator | Manages accounts, configures SAP connectivity |

### Business Value

| Metric | Before DOC AI | After DOC AI |
|--------|--------------|--------------|
| Time to write a TDD | 2–5 days per object | 3–5 minutes per object |
| Quality consistency | Varies by developer | Consistent, AI-reviewed |
| SAP system knowledge | Expert-level | Minimal |
| Export formats | Manual Word/PDF | Auto PDF, DOCX, HTML |

### Technology Stack

```
Frontend  →  Next.js 15 + TypeScript + Tailwind CSS
Backend   →  Python FastAPI + SQLAlchemy (async)
Database  →  PostgreSQL 16
AI Engine →  SAP BTP AI Core (Claude) OR OpenAI GPT-4o (fallback)
SAP Link  →  HTTP ICF service /sap/bc/zdoc (primary) + RFC bridge (legacy)
Exports   →  ReportLab PDF | python-docx Word | self-contained HTML
```

---


## 2. Business Process

### 2.1 The Complete User Journey

```
STEP 1: Login
  User → http://localhost:3000 → email + password
  System issues JWT token (12 hours) → stored in browser localStorage

STEP 2: Create a Project
  A "project" is a folder grouping related SAP objects together
  Example: project "Invoice Printing" holds ZSD_INVOICE_PRINT + its SmartForm

STEP 3: Upload Code (two paths — see 2.2)
  PATH A — File Upload: .abap / .xml / .zip files from local computer
  PATH B — Live SAP Fetch: type object name, system fetches from SAP

STEP 4: Automatic Parsing
  SAPObjectExtractor reads uploaded content and extracts:
  tables, function calls, forms, classes, SmartForms, auth checks,
  SELECT statements, parameters, events, complexity metrics

STEP 5: AI Document Generation (background task)
  14 AI sections generated in parallel (max 4 concurrent):
  Cover → Business View → Technical View → Source Analysis →
  Database Analysis → API Dependencies → Process Flow → Diagrams →
  Integration View → Security → Performance → Reference Data →
  Modification History → AI Recommendations

STEP 6: View Document
  Browser displays all 14 sections in tabbed viewer
  AI Chat available to ask questions about the code

STEP 7: Export
  Download as PDF / Word DOCX / standalone HTML
```

### 2.2 The Two SAP Integration Paths

#### Path A — File Upload (Offline Mode)
No SAP system connection required. Developer exports from SAP manually and uploads the file.

| File Type | Source in SAP | Notes |
|-----------|--------------|-------|
| `.abap` | SE38 / SE80 source export | Plain text ABAP source |
| `.xml` | SMARTFORMS transaction XML export | SmartForm XML format |
| `.txt` | Any text editor | Works for ABAP and SmartForm source |
| `.zip` | Package of multiple files | Each file processed separately |
| `.pdf` `.docx` `.xlsx` | Any document | Text is extracted and analyzed |

#### Path B — Live SAP Connection (Online Mode)
System connects directly to a running SAP system via a custom HTTP ICF service.

**How it works:**
1. Developer enters SAP credentials + object name in browser
2. Frontend sends credentials as `X-SAP-User` and `X-SAP-Password` headers
3. Backend calls `GET /sap/bc/zdoc?action=search&q=ZSD_INV*` to find objects
4. Backend calls `GET /sap/bc/zdoc?action=read&object=ZSD_INVOICE_PRINT` to fetch source
5. System also fetches ALL related objects (includes, classes, SmartForms, tables)
6. Source code and dependency graph are stored, then AI generation proceeds

**Required SAP Setup (one-time, done by Basis team):**
- ABAP class `ZCL_DOC_HTTP` installed as ICF handler
- ICF service `/sap/bc/zdoc` activated in transaction `SICF`
- Technical user with `S_DEVELOP` ACTVT=03 (display) authorization

> **New developer note:** If you see "SAP service /sap/bc/zdoc is not active" (HTTP 404), the ICF service is not set up. If you see HTTP 403, the user is missing authorization. Contact SAP Basis.

### 2.3 The 14 Documentation Sections

| # | Section | Database Column | Business Purpose |
|---|---------|----------------|-----------------|
| 1 | Cover Page | `cover_data` | Program name, module, version, author, dates |
| 2 | Business View | `business_view` | Object inventory, business rules, KPI counts |
| 3 | Technical View | `technical_view` | Selection screen, all CALL FUNCTIONs, SELECTs, FORMs |
| 4 | Source Analysis | `source_analysis` | Complexity, pseudo-code, routine breakdown |
| 5 | Database Analysis | `database_analysis` | All tables with CRUD operations, ER diagram |
| 6 | API Dependencies | `api_dependency` | All FMs, BAPIs, RFCs, dependencies |
| 7 | Process Flow | `process_flow` | Step-by-step execution in plain English |
| 8 | Visual Diagrams | `diagrams` | Flowchart, ER, sequence, class, DFD diagrams |
| 9 | Integration View | `integration_view` | SAP module connections, external systems |
| 10 | Security Review | `security_review` | Auth objects, risks, compliance score |
| 11 | Performance Review | `performance_review` | SELECT-in-LOOP, SELECT *, optimization |
| 12 | Reference Data | `reference_data` | Complete index of all objects referenced |
| 13 | Modification History | `modification_history` | Change log from code comments |
| 14 | AI Recommendations | `ai_recommendations` | Quality scores, S/4HANA readiness |

### 2.4 Document Status Lifecycle

```
queued (5%)  →  fetching (15%)  →  generating (20-95%)  →  completed (100%)
                                                         ↘  failed (100%)
```

| Status | Meaning | `generation_step` example |
|--------|---------|--------------------------|
| `queued` | Background job waiting to start | "Queued" |
| `fetching` | Fetching source from live SAP (online mode only) | "Fetching from SAP" |
| `generating` | AI is generating the 14 sections | "Generating sections 7/14" |
| `completed` | All sections done, document ready | "Completed" |
| `failed` | Generation failed entirely | "Failed: all sections failed" |

---


## 3. Technical Architecture

### 3.1 System Component Map

```
BROWSER (Port 3000 — Next.js 15)
  Auth Pages | Dashboard | Document Viewer | SAP Search | AI Chat | Settings
  State: Zustand (authStore, projectStore, themeStore)
  API: Axios with Authorization: Bearer token interceptor
       ↕ HTTPS REST
BACKEND (Port 8000 — FastAPI Python)
  api/ layer → services/ layer → utils/ layer → models/ layer → database
       ↕
DATABASE (Port 5432 — PostgreSQL 16)
  users | projects | uploads | documents | document_versions | chat_messages

EXTERNAL:  SAP BTP AI Core (Claude)  |  OpenAI GPT-4o  |  SAP /sap/bc/zdoc
```

### 3.2 Backend File Structure

```
backend/app/
  main.py         FastAPI app entry. Registers all routers. Starts RFC bridge.
  config.py       All env settings (DATABASE_URL, JWT, SAP, BTP, OpenAI)
  database.py     SQLAlchemy async engine + session factory (asyncpg driver)

  api/
    auth.py       POST /login, /register, GET /me, POST /refresh, /logout
    projects.py   CRUD for projects
    uploads.py    POST /file, /zip; GET; DELETE
    documents.py  POST /generate, GET status/sections/versions; DELETE
    sap.py        SAP search, preview, build-graph, generate from live SAP
    export.py     GET /pdf, /docx, /html (streaming file downloads)
    chat.py       POST /chat, GET/DELETE history
    search.py     GET /search (full-text search over document titles)
    settings.py   GET/POST /ai-config, POST /ai-test (BTP credentials)
    deps.py       Shared: get_current_user(), assert_owner_or_admin()

  models/
    user.py       users table
    project.py    projects table
    upload.py     uploads table (stores raw source code text)
    document.py   documents table (stores all 14 AI sections as JSON columns)
    version.py    document_versions table (history snapshots)
    chat.py       chat_messages table

  services/
    ai_service.py       Core AI engine. BTP (Claude) or OpenAI. All 14 sections.
    doc_generator.py    Orchestrator. Runs 14 generators in parallel (max 4).
    sap_doc_api.py      HTTP client for /sap/bc/zdoc ICF service.
    sap_repo_builder.py Builds complete SAP object dependency graph.
    parser_service.py   Lightweight regex ABAP parser (backup path).
    analysis_service.py Complexity scoring, performance/security detection.
    diagram_service.py  Mermaid.js diagram string builders.
    pdf_service.py      ReportLab PDF renderer.
    docx_service.py     python-docx Word renderer.
    html_service.py     Self-contained HTML renderer with embedded CSS.
    auth_service.py     register_user(), authenticate_user() with rate limit.
    chat_service.py     process_chat() — load history, AI call, save response.

  utils/
    sap_extractor.py    Main extraction engine. ABAP source + SmartForm XML.
    abap_patterns.py    Pre-compiled regex patterns for ABAP keywords.
    file_utils.py       save_upload_file(), extract_zip(), detect_abap_type()

  core/
    security.py         hash_password, verify_password, JWT create/decode
    exceptions.py       NotFoundException, UnauthorizedException, etc.

  schemas/              Pydantic request/response validation models

sap_rfc_bridge.js       Node.js RFC bridge (optional legacy — off by default)
requirements.txt        All Python dependencies
Dockerfile              Container build
.env                    Environment variables (NEVER commit to Git)
```

### 3.3 Request Lifecycle — "Generate Document" Click to Completion

```
USER clicks Generate

→ POST /api/documents/generate  {upload_id, project_id, title}
  [documents.py] Validates JWT, checks ownership, creates Document(status=queued)
  Returns HTTP 200 IMMEDIATELY — does not wait for AI
  Queues background task: run_generation(document.id, user.id)

→ BACKGROUND [doc_generator.py]
  Loads Upload (source_code + parsed_metadata from DB)
  If live SAP mode: loads repository_graph, merges sub-objects into parsed_data
  Sets status = "generating"

→ EXTRACTION [sap_extractor.py]
  Auto-detects type: SmartForm XML / plain ABAP / generic XML
  Extracts: tables, FMs, forms, classes, params, auth checks, events, complexity
  Builds cross-reference matrix

→ AI GENERATION [ai_service.py]
  14 sections via asyncio.gather() with Semaphore(4)
  Each section: system prompt (role) + user prompt (data) → BTP/OpenAI → JSON
  Strips markdown fences from AI response if present

→ PERSISTENCE [doc_generator.py]
  Sets all 14 JSON results on Document model
  validate_coverage() flags missing objects
  Sets status = "completed" or "failed"
  Creates DocumentVersion snapshot
  Commits to PostgreSQL

→ FRONTEND polls GET /api/documents/{id}/status every 2 seconds
  When completed → fetches full document → renders 14-section viewer
```

### 3.4 AI Engine Selection Logic

```
if BTP_CLIENT_ID and BTP_DEPLOYMENT_ID are set:
    try BTP AI Core (Claude)
    if BTP fails → try OpenAI (if OPENAI_API_KEY set)
else:
    use OpenAI directly (if OPENAI_API_KEY set)
    else → return error ("AI service not configured")
```

BTP tokens are cached in-memory (`self._token`, `self._token_expiry`). Refreshed 60 seconds before expiry. Each generation job creates one `AIService` instance so the token is reused across all 14 section calls.

---


## 4. Selection Screen Analysis

### 4.1 What "Selection Screen" Means Here

DOC AI does not have its own ABAP selection screen. Instead, it **analyzes and documents** the selection screens of the ABAP programs you upload. This section explains what gets extracted and why it matters.

### 4.2 What Gets Extracted From ABAP Selection Screens

The `SAPObjectExtractor._abap()` method scans for these ABAP keywords:

**PARAMETERS** — Individual single-value inputs on the selection screen
```abap
PARAMETERS: p_bukrs TYPE bukrs OBLIGATORY,
            p_gjahr TYPE gjahr DEFAULT sy-datum(4).
```
DOC AI captures: parameter name, type reference, whether OBLIGATORY, default value.
This tells the business user: "The user must enter a Company Code. Year defaults to current year."

**SELECT-OPTIONS** — Range inputs (from/to filters) on the selection screen
```abap
SELECT-OPTIONS: s_vbeln FOR vbrk-vbeln,
                s_fkdat FOR vbrk-fkdat.
```
DOC AI captures: name, table it refers to (`VBRK`), field it refers to (`VBELN`).
This tells the business user: "User can filter by billing document number range."

**Events** — These tell the story of when the program's code runs:

| ABAP Event | When It Runs | Business Meaning |
|------------|-------------|-----------------|
| `INITIALIZATION` | Screen opens | Sets default values before user sees it |
| `AT SELECTION-SCREEN` | User presses Execute | Input validation logic |
| `START-OF-SELECTION` | Main execution begins | Where all data reading/processing happens |
| `END-OF-SELECTION` | After all data processed | Final calculations, output triggers |
| `TOP-OF-PAGE` | Before each printed page | Page header printing |
| `END-OF-PAGE` | After each printed page | Page footer, page totals |

### 4.3 Where This Data Appears in Generated Documents

**Section 3 (Technical View)** → `selection_screen` JSON key:
```json
{
  "parameters": [
    { "name": "P_BUKRS", "type": "BUKRS", "obligatory": true, "default": "" },
    { "name": "P_GJAHR", "type": "GJAHR", "obligatory": false, "default": "current year" }
  ],
  "select_options": [
    { "name": "S_VBELN", "for_table": "VBRK", "for_field": "VBELN", "description": "Billing Document Number" },
    { "name": "S_FKDAT", "for_table": "VBRK", "for_field": "FKDAT", "description": "Billing Date" }
  ],
  "radio_buttons": [],
  "checkboxes": [],
  "mandatory_fields": ["P_BUKRS"],
  "default_values": [{ "parameter": "P_GJAHR", "value": "current year" }]
}
```

### 4.4 The SAP Search Screen in the Frontend

When using the "SAP Search" page (`/sap-search`), the user fills in these fields:

| Field | Purpose | How Used Technically |
|-------|---------|---------------------|
| SAP Username | Authenticate with SAP | Sent as `X-SAP-User` HTTP header |
| SAP Password | Authenticate with SAP | Sent as `X-SAP-Password` HTTP header |
| Object Name | SAP program/class/form to fetch | Query param `q` to /sap/bc/zdoc |
| Object Type | PROG / CLAS / INTF / SSFO / TABL / DDLS | Query param `type` |
| Project | Which project receives this document | Stored with Upload + Document records |

**Security note:** Credentials are NEVER stored in the database. They pass through the backend directly to SAP for each request and are then discarded.

---


## 5. Global Variables and Configuration

### 5.1 The Settings Object (config.py)

All configuration lives in one place. The `settings` object is imported by every module that needs configuration:
```python
from app.config import settings
# Usage examples:
settings.DATABASE_URL
settings.OPENAI_API_KEY
settings.SAP_DOC_API_URL
```

**Database (REQUIRED — app refuses to start without this)**

| Variable | Purpose | Example |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost:5432/docai_db` |

> The `asyncpg` driver prefix is mandatory. The application uses async SQLAlchemy. Using `postgresql://` without asyncpg will crash the server.

**Security (REQUIRED — app refuses to start without this)**

| Variable | Purpose | Notes |
|----------|---------|-------|
| `JWT_SECRET` | Signs JWT tokens. MUST be 32+ chars. | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | JWT algorithm | Default: `HS256` |
| `JWT_EXPIRY_MINUTES` | Token lifetime | Default: `720` (12 hours) |

**Upload / CORS Settings**

| Variable | Purpose | Default |
|----------|---------|---------|
| `UPLOAD_DIR` | Where uploaded files are saved on disk | `./uploads` |
| `MAX_UPLOAD_SIZE` | Max file size in bytes | `52428800` (50 MB) |
| `CORS_ORIGINS` | Allowed frontend origins | `["http://localhost:3000"]` |

**SAP BTP AI Core (primary AI engine)**

| Variable | Purpose |
|----------|---------|
| `BTP_CLIENT_ID` | OAuth client ID |
| `BTP_CLIENT_SECRET` | OAuth client secret |
| `BTP_TOKEN_URL` | OAuth token endpoint |
| `BTP_AI_API_URL` | BTP AI Core base URL |
| `BTP_RESOURCE_GROUP` | AI resource group (default: `default`) |
| `BTP_DEPLOYMENT_ID` | Claude model deployment ID |

**OpenAI (fallback AI engine)**

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | OpenAI API key | (empty) |
| `OPENAI_MODEL` | Model name | `gpt-4o` |

**SAP HTTP Doc API (live SAP code fetch)**

| Variable | Purpose | Default |
|----------|---------|---------|
| `SAP_DOC_API_URL` | Full URL of SAP ICF service | (empty) |
| `SAP_DOC_API_USER` | Default SAP user (optional — can be per-request) | (empty) |
| `SAP_DOC_API_PASSWORD` | Default SAP password | (empty) |
| `SAP_DOC_API_CLIENT` | SAP client number | `120` |
| `SAP_DOC_API_VERIFY_SSL` | Verify SSL certs | `true` |
| `SAP_DOC_API_TIMEOUT` | HTTP timeout in seconds | `120` |

**RFC Bridge (optional, off by default)**

| Variable | Purpose | Default |
|----------|---------|---------|
| `SAP_RFC_ENABLED` | Enable Node.js RFC bridge | `false` |
| `SAP_HOST` | SAP app server hostname | (empty) |
| `SAP_SYSNR` | SAP system number | `00` |
| `SAP_CLIENT` | SAP client | `120` |
| `SAPNWRFC_HOME` | Path to NW RFC SDK | (empty, required if RFC enabled) |
| `SAP_BRIDGE_PORT` | RFC bridge HTTP port | `5001` |

### 5.2 Application-Level Constants

**doc_generator.py — Document Generation Engine**
```python
MAX_PARALLEL_SECTIONS = 4
# How many AI calls run simultaneously. Higher = faster but risks rate limits.

SECTIONS = [
    ("cover_data",          "generate_cover_page"),
    ("business_view",       "generate_business_view"),
    ("technical_view",      "generate_technical_view"),
    ("source_analysis",     "generate_source_analysis"),
    ("database_analysis",   "generate_database_analysis"),
    ("api_dependency",      "generate_api_dependency"),
    ("process_flow",        "generate_process_flow"),
    ("diagrams",            "generate_diagrams"),
    ("integration_view",    "generate_integration_view"),
    ("security_review",     "generate_security_review"),
    ("performance_review",  "generate_performance_review"),
    ("reference_data",      "generate_reference_tables"),
    ("modification_history","generate_modification_history"),
    ("ai_recommendations",  "generate_ai_recommendations"),
]
# col name on Document model = method name on AIService
```

**uploads.py — File Upload Security**
```python
BLOCKED_EXTENSIONS = {".exe", ".dll", ".bat", ".sh", ".cmd", ".msi", ".dmg", ".bin", ".iso"}
# These file types are always rejected. Cannot be changed at runtime.
```

**auth_service.py — Login Rate Limiting**
```python
_MAX_ATTEMPTS = 5       # Max failed logins before lockout
_WINDOW_SECONDS = 300   # Lockout window: 5 minutes
# Counter is in-memory. Resets on server restart.
```

**sap_doc_api.py — SAP Fetch Limits**
```python
_REPO_MAX_PER_TYPE = 20
# Maximum sub-objects fetched per type (includes, classes, FMs, etc.)
# Prevents runaway fetches on objects with hundreds of dependencies.
```

### 5.3 Frontend Global State (Zustand Stores)

| Store | File | What It Contains |
|-------|------|-----------------|
| `authStore` | `store/authStore.ts` | `user`, `token`, `isAuthenticated`, `isLoading`. Persists to localStorage. |
| `projectStore` | `store/projectStore.ts` | Currently selected project and project list |
| `themeStore` | `store/themeStore.ts` | `dark` or `light` theme preference |

The `authStore` saves `docai_token` and `docai_user` in localStorage. On page refresh, `loadUser()` reads the stored token and calls `GET /api/auth/me` to restore the session.

---


## 6. Forms and Methods Explanation

### 6.1 AIService — The 14 Section Generators (ai_service.py)

This class is the heart of the application. Every document section comes from one method here.

**`_get_token()`** — Gets OAuth token for BTP AI Core. Cached in memory, auto-refreshed 60s before expiry.

**`_call_ai(system_prompt, user_prompt, max_tokens)`** — Single entry point for ALL AI calls. Tries BTP first, falls back to OpenAI. Strips markdown fences. Returns dict or `{"error": "..."}`.

**`generate_cover_page()`** — Extracts program_name, module, package, tcode, version, author, dates, object_type. AI role: "SAP Metadata Analyst".

**`generate_business_view()`** — Creates `object_inventory` (all objects with counts), `business_rules_matrix` (exact rules from code conditions), `kpi_matrix` (counts). AI role: "SAP Architect creating KT Support Document".

**`generate_technical_view()`** — Most detailed section. Exhaustive extraction of:
- `selection_screen`: all parameters and select-options
- `call_function_statements`: EVERY CALL FUNCTION numbered sequentially
- `call_transaction_statements`: EVERY CALL TRANSACTION numbered
- `select_statements`: EVERY SELECT/INSERT/UPDATE/DELETE numbered
- `perform_subroutines`: EVERY FORM with logic summary and tables accessed
- `behavior_matrix`: conditional logic (e.g., per billing type)
AI instruction: "Be exhaustive. Extract EVERY function call, transaction, SELECT, and FORM."

**`generate_source_analysis()`** — Complexity level, pseudo-code, form-by-form breakdown.

**`generate_database_analysis()`** — All tables with CRUD operations, Mermaid ER diagram string.

**`generate_api_dependency()`** — All FMs categorized as: SAP Standard / Custom Z / SmartForm FM / BAPI / RFC.

**`generate_process_flow()`** — Step-by-step execution flow in plain English.

**`generate_diagrams()`** — Mermaid strings: flowchart, ER, sequence, class, component. Plus HTML: Data Flow Diagram, Connectivity Diagram.

**`generate_integration_view()`** — SAP module connections and external system integrations.

**`generate_security_review()`** — Auth objects, sensitive table access, RFC risks, hardcoded secrets, security_score (0–100).

**`generate_performance_review()`** — SELECT-in-LOOP, nested loops, optimization opportunities, performance_score (0–100).

**`generate_reference_tables()`** — Complete index: transactions, tables, structures, domains, data_elements, FMs, classes, message_classes, smart_forms, cds_views, custom_tables.

**`generate_modification_history()`** — Change log from comment blocks starting with `*`, transport references, version tags.

**`generate_ai_recommendations()`** — Quality scores (0–100): code_quality, maintainability, performance, security, s4hana_readiness, rap_migration. Plus refactoring_suggestions, clean_abap_recommendations, s4hana_migration_path.

**`chat_with_code(messages, source_code)`** — Conversational Q&A. Full source code passed as context. Returns plain text (not JSON).

### 6.2 SAPObjectExtractor (utils/sap_extractor.py)

**`extract(content, file_type, filename)`**
- If `<sf:SMARTFORM` in content → `_sf()` SmartForm parser
- If starts with `<?xml` → `_extract_generic_xml()`
- Otherwise → `_abap()` ABAP source parser
- Always adds: `cross_references`, `filename`, `file_size_chars`

**`_sf(content)`** — SmartForm XML parser. Extracts: header metadata, interface (imports/exports/tables), pages, windows, conditions, text_elements, code_blocks, graphics, field_references. Also runs `_abap_from_xml()` on embedded ABAP to find SELECT/CALL FUNCTION inside the form.

**`_abap(content)`** — ABAP source parser. Line-by-line + regex extraction of: program_name, tables, classes, FMs, CALL FUNCTION calls, CALL TRANSACTION calls, PERFORM calls, FORM subroutines, PARAMETERS, SELECT-OPTIONS, AUTHORITY-CHECK objects, SmartForm calls, MESSAGE statements, events, custom structures, complexity indicators (SELECT * count, SELECT-in-LOOP count).

**`build_cross_reference(d)`** — Maps which SAP table is used in which FORM or code block. Stored as `cross_references` in parsed_metadata.

### 6.3 DocGenerator Orchestrator (services/doc_generator.py)

**`generate_document(db, document_id, user_id)`**
1. Loads Document + Upload from DB
2. If live SAP fetch: calls `_enrich_parsed_data_from_graph()` to merge dependency objects
3. Creates AIService + Semaphore(MAX_PARALLEL_SECTIONS=4)
4. Fires all 14 generators with `asyncio.gather()` — true parallel execution
5. Sets each result on Document model
6. Runs `validate_coverage()` — compares extracted vs documented counts
7. Commits to DB, creates DocumentVersion snapshot

**`validate_coverage(parsed_data, document)`** — Returns `{"status": "PASS"|"PARTIAL", "gaps": [...]}`. Stored in `cover_data._coverage_report`.

### 6.4 Auth Functions (core/security.py + services/auth_service.py)

| Function | Purpose |
|----------|---------|
| `hash_password(password)` | bcrypt hash — never stores plain text |
| `verify_password(plain, hashed)` | bcrypt.checkpw comparison |
| `create_access_token(data)` | JWT with sub=user_uuid, exp=12h from now |
| `decode_access_token(token)` | Decode + validate JWT. Returns None if invalid. |
| `register_user(db, user_data)` | Check email unique, hash password, create User |
| `authenticate_user(db, email, password)` | Rate limit check → DB lookup → verify password |

---


## 7. Tables with Purpose

### 7.1 DOC AI PostgreSQL Tables

**`users`** — User account registry. Columns: id (UUID PK), email (UNIQUE), password_hash (bcrypt), full_name, role (`user` or `admin`), is_active, created_at, updated_at. One user owns many projects, uploads, documents.

**`projects`** — Project workspaces that group related SAP objects. Columns: id (UUID PK), name, description, module (SD/MM/FI/etc.), status (`active` or `deleted` — soft delete), owner_id (FK users). Business example: project "Invoice Printing" holds ZSD_INVOICE_PRINT + its SmartForm.

**`uploads`** — Source code storage. Columns: id (UUID PK), project_id, filename, file_type (abap_report / smart_form / class / function_group / etc.), file_size, content (TEXT — **the raw source code**), parsed_metadata (JSON — **the pre-computed extraction result**), uploaded_by.

> `parsed_metadata` is the MOST CRITICAL column. It is computed at upload time by `SAPObjectExtractor.extract()` and drives ALL AI generation. If it is empty, the generated document will be empty.

```json
Example parsed_metadata structure:
{
  "program_name": "ZSD_INVOICE_PRINT",
  "source_type": "abap_source",
  "tables_used": [{"name": "VBRK", "operation": "SELECT"}],
  "function_calls": [{"name": "SSF_FUNCTION_MODULE_NAME"}],
  "forms": [{"name": "GET_HEADER_DATA", "line_count": 45}],
  "parameters": [{"name": "P_VBELN", "obligatory": true}],
  "auth_checks": [{"object": "V_VBRK_VKO"}],
  "smart_forms": [{"name": "ZSD_INVOICE_JBMI_A4_GST"}],
  "complexity_indicators": {"select_in_loop": 2, "select_star": 0}
}
```

**`documents`** — Generated documentation storage. Each of the 14 AI sections is stored in its own JSON column: `cover_data`, `business_view`, `technical_view`, `source_analysis`, `database_analysis`, `api_dependency`, `process_flow`, `diagrams`, `integration_view`, `security_review`, `performance_review`, `reference_data`, `modification_history`, `ai_recommendations`. Also: status, generation_step, generated_by.

**`document_versions`** — History snapshots. Each time a document is regenerated, a version is saved. Columns: id, document_id, version_number (sequential integer), snapshot (JSON copy of all 14 sections), change_summary, created_by.

**`chat_messages`** — AI chat conversation. Columns: id, upload_id (which code is being discussed), user_id, role (`user` or `assistant`), content (message text). Full history sent to AI on each new message.

### 7.2 SAP Standard Tables Often Referenced in Generated Docs

| SAP Table | Module | Business Meaning |
|-----------|--------|-----------------|
| `VBRK` | SD | Billing Document Header (invoice header) |
| `VBRP` | SD | Billing Document Line Items |
| `KNA1` | SD/AR | Customer Master |
| `LFA1` | MM/AP | Vendor Master |
| `BSEG` | FI | Accounting Document Segment |
| `BKPF` | FI | Accounting Document Header |
| `EKKO` | MM | Purchase Order Header |
| `EKPO` | MM | Purchase Order Item |
| `MARA` | MM | Material Master General Data |
| `MARC` | MM | Material Master Plant Data |
| `T001` | FI | Company Codes |
| `NAST` | SD/MM | Output/Message conditions |
| `STXH` / `STXL` | ALL | SmartForm/SAPscript text storage |

---


## 8. SmartForm Deep Analysis

### 8.1 What is a SAP SmartForm?

A SmartForm is SAP's print output tool. When an invoice is printed, a delivery note generated, or a purchase order sent by email — a SmartForm is almost always involved. SmartForms are stored as XML in SAP and can be exported as `.xml` files from transaction `SMARTFORMS`.

### 8.2 SmartForm Node Tree Structure

A SmartForm is a tree of nodes. Each node type serves a specific purpose:

| Node Type | Business Purpose |
|-----------|-----------------|
| Form | Root container — the entire form definition |
| Global Definitions | Interface parameters, global types and variables |
| Page | One printed page layout (e.g., PAGE1, NEXTPAGE) |
| Window | A rectangle on a page (MAIN scrolling body, HEADER, FOOTER, etc.) |
| Text | Static or dynamic text block |
| Table | Repeating line-item table (loops over internal table data) |
| Folder | Logical grouping container |
| Command | Special commands: page break, set color, etc. |
| ABAP Code | **Embedded ABAP logic** — flagged for security/performance review |
| Alternative | If/Else branching |
| Condition | Boolean condition gating a child node |
| Graphics | Embedded image (logos, signatures, stamps) |
| Address | SAP address formatting block |

### 8.3 What DOC AI Extracts From SmartForm XML

**Header Metadata**
```
formname   → Form name (e.g., ZSD_INVOICE_JBMI_A4_GST)
caption    → Form description
devclass   → Development package
firstuser  → Who created the form (SAP user ID)
firstdate  → Creation date
lastuser   → Who last changed it
lastdate   → Last change date
masterlang → Master language (E = English)
```

**Interface (Parameters)**
```
imports[]   → Input parameters passed in by the calling program
exports[]   → Output parameters returned
tables[]    → Internal tables passed in/out (line items, etc.)
exceptions[]→ Exception conditions the form can raise
```

**Pages and Windows**
```
pages[]   → Each page: name, description, next_page logic, conditions
windows[] → Each window: name, type (MAIN or SECONDARY), description, position
```

**Code Blocks (ABAP Nodes) — Critical for Review**
```
code_blocks[] → Each embedded ABAP section:
               block_index → Sequential number
               lines[]     → The actual ABAP code lines
```
> **Warning:** ABAP inside SmartForms cannot be debugged the same way as regular ABAP. Any SELECT statements inside are a performance risk. DOC AI flags these in the Performance Review.

**Text Elements**
```
text_elements[] → Extracted text content (HTML tags stripped)
```

**Field References**
```
field_references[] → Data bindings like &KNA1-NAME1&
                    Shows exactly which data fields are printed
```

**Business Rules Discovered**
```
business_rules_discovered[] → Conditions extracted from condition nodes
                              Shows IF/ELSE business logic in plain text
```

### 8.4 SmartForm Generation Call Pattern

Every program that calls a SmartForm uses this two-step SAP standard pattern which DOC AI recognizes:

```abap
* Step 1: Get the generated function module name for this SmartForm
CALL FUNCTION 'SSF_FUNCTION_MODULE_NAME'
  EXPORTING  formname = 'ZSD_INVOICE_JBMI_A4_GST'
  IMPORTING  fm_name  = lv_fmname.

* Step 2: Call the dynamically-named function module
CALL FUNCTION lv_fmname
  EXPORTING  control_parameters = ls_ctrl
             output_options     = ls_opt
  TABLES     item_tab           = lt_items
  EXCEPTIONS OTHERS             = 1.
```

DOC AI recognizes `SSF_FUNCTION_MODULE_NAME` as a SmartForm call and documents the SmartForm name alongside it in the API Dependency section, categorized as "SmartForm FM" type.

### 8.5 SmartForm Sections in the Generated PDF

The PDF export has dedicated SmartForm-specific sections:
- Section 3: SmartForm Interface (imports, exports, table parameters)
- Section 4: Windows (all window names, types, positions)
- Section 5: Conditions (all business rules discovered)
- Section 6: Text Elements
- Section 7: Code Blocks (all embedded ABAP)
- Section 8: Graphics
- Section 9: Cross-References (which table used in which window/code block)
- Section 10: Field References (all &FIELD& bindings)

---


## 9. Dependency Map

### 9.1 Internal Component Call Graph

```
main.py
  imports all api/* routers
  imports database (Base, engine) for table auto-creation at startup

documents.py (API)
  → calls doc_generator.run_generation() as background task

doc_generator.py
  → uses database.AsyncSessionLocal (own session for background task)
  → reads models.Document, models.Upload
  → calls ai_service.AIService (14 section methods)
  → writes models.DocumentVersion

ai_service.py
  → calls SAP BTP AI Core via HTTPS (primary)
  → calls OpenAI API via HTTPS (fallback)

uploads.py (API)
  → calls file_utils.save_upload_file()
  → calls file_utils.detect_abap_type()
  → calls sap_extractor.SAPObjectExtractor.extract()

sap.py (API)
  → calls sap_doc_api.search_objects_wildcard()
  → calls sap_repo_builder.build_repository_graph()
  → calls sap_repo_builder.build_source_from_graph()
  → calls sap_extractor.SAPObjectExtractor.extract()
  → calls doc_generator.run_generation() as background task

sap_repo_builder.py
  → calls sap_doc_api._call_with_creds()

export.py (API)
  → calls pdf_service.generate_pdf()
  → calls docx_service.generate_docx()
  → calls html_service.generate_html()

chat.py (API)
  → calls chat_service.process_chat()

chat_service.py
  → calls ai_service.AIService.chat_with_code()

All API files
  → use deps.get_current_user() → security.decode_access_token()
  → use deps.assert_owner_or_admin() for resource access control
```

### 9.2 SAP Object Type Code Reference

| Friendly Name | TADIR Code | Description |
|--------------|-----------|-------------|
| `program` | `PROG` | ABAP Report or Program |
| `class` | `CLAS` | ABAP OO Class |
| `interface` | `INTF` | ABAP OO Interface |
| `function` | `FUNC` | Function Module |
| `function_group` | `FUGR` | Function Group (pool of FMs) |
| `smartform` | `SSFO` | SmartForm |
| `table` | `TABL` | Database Table or Structure |
| `cds` | `DDLS` | CDS View (Core Data Services) |
| `transaction` | `TRAN` | Transaction Code |

### 9.3 Repository Graph Structure

When DOC AI fetches from live SAP, it builds this JSON structure:

```json
{
  "object": "ZSD_INVOICE_PRINT",
  "objectType": "PROG",
  "sourceCode": "REPORT ZSD_INVOICE_PRINT. ...",
  "includes": [
    {"object": "ZSD_INVOICE_TOP", "sourceCode": "..."},
    {"object": "ZSD_INVOICE_SEL", "sourceCode": "..."}
  ],
  "classes": [{"object": "ZCL_INVOICE_HELPER", "sourceCode": "..."}],
  "functionModules": [{"object": "Z_GET_INVOICE_DATA", "sourceCode": "..."}],
  "tables": [{"object": "VBRK", "fields": [...]}, {"object": "VBRP", "fields": [...]}],
  "smartForms": [{"object": "ZSD_INVOICE_JBMI_A4_GST", "sourceCode": "..."}],
  "dataElements": [...],
  "domains": [...],
  "cdsViews": [...],
  "transactions": [...],
  "dependencies": [...]
}
```

This graph is stored in `uploads.parsed_metadata.repository_graph`.
`_enrich_parsed_data_from_graph()` merges it into `parsed_data` before AI generation, so the AI sees ALL related objects — not just the main program.

### 9.4 End-to-End Data Flow

```
Browser Upload / SAP Fetch
  ↓
uploads.py: save file + call SAPObjectExtractor
  ↓ parsed_metadata stored in uploads table
documents.py: create Document(status=queued)
  ↓ background task queued
doc_generator.py: load parsed_metadata + source_code
  ↓ 14 parallel AI calls
ai_service.py: BTP Claude or OpenAI GPT-4o
  ↓ 14 JSON responses
doc_generator.py: store results in Document (14 JSON columns)
  ↓ status=completed
pdf_service / docx_service / html_service: render on demand at export time
  ↓
Browser downloads file
```

### 9.5 ABAP Naming Conventions — What the System Understands

| Prefix | Meaning | Example |
|--------|---------|---------|
| `Z...` | Customer custom object | `ZSD_INVOICE_PRINT` |
| `Y...` | Also customer custom | `YSD_REPORT` |
| No prefix | SAP standard | `SD_INVOICE`, `BAPI_SALESORDER_GETLIST` |
| `/1BCDWB/SF...` | Auto-generated SmartForm FM | `/1BCDWB/SFZSD_INVOICE_PRINT` |
| `SSF_...` | SmartForm framework FM | `SSF_FUNCTION_MODULE_NAME` |
| `BAPI_...` | Business API | `BAPI_SALESORDER_GETLIST` |
| `RFC_...` | Remote Function Call | `RFC_READ_TABLE` |

The AI uses these conventions to categorize each CALL FUNCTION as: SAP Standard / Custom Z / SmartForm FM / BAPI / RFC.

---


## 10. Debugging Guide

### 10.1 Always Start Here — Health Endpoint

```
GET http://localhost:8000/api/health
```

Healthy response:
```json
{
  "status": "ok",
  "checks": {
    "database": { "ok": true, "message": "Connected" },
    "ai_engine": { "ok": true, "engine": "openai", "message": "gpt-4o" },
    "sap_doc_api": { "ok": true, "message": "Reachable (245 ms)" }
  }
}
```

### 10.2 Log Locations

| Component | Log Location |
|-----------|-------------|
| Backend | Console where `uvicorn` runs + `backend_log.txt` in project root |
| Frontend | Browser DevTools (F12) → Console tab |
| RFC Bridge | `backend/sap_rfc_bridge.log` (only if SAP_RFC_ENABLED=true) |

### 10.3 Debugging Document Generation Failures

**Step 1: Check document status**
```
GET /api/documents/{document_id}/status
```
Look at `generation_step` field. It will describe the failure.

**Step 2: Check which sections failed**
```
GET /api/documents/{document_id}
```
Look at `cover_data._failed_sections` — list of section names that failed.

**Step 3: Check individual section content**
```
GET /api/documents/{document_id}/section/database_analysis
```
If the content is `{"error": "..."}`, that section failed.

**Step 4: Check server logs** for lines like:
```
WARNING  Section database_analysis failed for <doc_id>: ...
ERROR    BTP AI Core error: HTTPStatusError ...
ERROR    OpenAI fallback error: AuthenticationError ...
```

### 10.4 Debugging SAP Connection Issues

| Error | Cause | Fix |
|-------|-------|-----|
| HTTP 404 "service not active" | ICF /sap/bc/zdoc not active | Basis team: activate in SICF |
| HTTP 401 "rejected credentials" | Wrong SAP user/password | Check user in SU01 (not locked?) |
| HTTP 403 "missing S_DEVELOP auth" | User missing display authorization | Basis: add S_DEVELOP ACTVT=03 to user role in PFCG |
| Timeout 504 | SAP system slow or unreachable | Increase SAP_DOC_API_TIMEOUT. Check SM21 for SAP errors. |
| "SAP returned invalid response" | ICF returned HTML error page | Test URL in browser. Check network. |

### 10.5 Debugging Empty Generated Documents

**Problem:** Document sections have empty tables or zero objects.

**Root cause:** `parsed_metadata` is empty — the extractor found nothing to extract.

**Debug query:**
```sql
SELECT filename, file_type,
       jsonb_array_length(parsed_metadata->'tables_used') as tables,
       jsonb_array_length(parsed_metadata->'function_calls') as fms,
       jsonb_array_length(parsed_metadata->'forms') as forms,
       parsed_metadata->>'source_type' as source_type
FROM uploads ORDER BY created_at DESC LIMIT 5;
```

If all counts are 0, check that the uploaded file is valid ABAP source (not encoded/binary).

For SmartForms: verify the XML contains `<sf:SMARTFORM` near the top.

### 10.6 Debugging JWT / Authentication Issues

| Error | Cause | Fix |
|-------|-------|-----|
| 401 "Invalid or expired token" | Token expired (12h) or JWT_SECRET changed | User logs in again |
| 403 "You do not have access" | User trying to access another user's resource | Expected security behavior. Set `role='admin'` for full access. |
| App won't start "JWT_SECRET must be..." | JWT_SECRET too short | Generate 32+ char secret (see Section 12 Issue 9) |

**Decode a JWT for debugging:**
```python
import jwt
payload = jwt.decode(token, options={"verify_signature": False})
print(payload)  # {"sub": "user-uuid", "exp": 1234567890}
```

### 10.7 Debugging AI Response Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| AI generates generic text | Extracted metadata is empty | Fix extraction first (see 10.5) |
| `{"error": "AI response was not valid JSON"}` | AI wrapped JSON in markdown | Usually self-corrects on retry. Check AI model version. |
| All sections in error state | No AI engine configured | Set OPENAI_API_KEY or all BTP vars in .env |
| BTP 401/403 | Wrong BTP credentials | Re-test via Settings page /api/settings/ai-test |

### 10.8 Useful SQL Queries

```sql
-- Recent documents and their status
SELECT id, title, status, generation_step, created_at
FROM documents ORDER BY created_at DESC LIMIT 10;

-- Check which sections failed for a document
SELECT id, title, status,
       cover_data->>'_failed_sections' as failed,
       cover_data->>'_coverage_report' as coverage
FROM documents WHERE id = '<uuid>';

-- Extraction quality check for recent uploads
SELECT filename,
       jsonb_array_length(parsed_metadata->'tables_used') as tables,
       jsonb_array_length(parsed_metadata->'function_calls') as fms,
       jsonb_array_length(parsed_metadata->'forms') as forms,
       parsed_metadata->>'source_type' as type
FROM uploads ORDER BY created_at DESC LIMIT 10;

-- All documents in a project
SELECT d.title, d.status, u.filename
FROM documents d
JOIN uploads u ON d.upload_id = u.id
WHERE d.project_id = '<project_uuid>'
ORDER BY d.created_at DESC;
```

---


## 11. New Developer KT Notes

### 11.1 The 10 Most Important Things to Understand

**1. Source code lives in `uploads.content` (TEXT column).** The AI reads directly from this. Wrong content = wrong document.

**2. `parsed_metadata` is computed at upload time, not generation time.** SAPObjectExtractor runs the moment a file is uploaded. This JSON dict drives all AI prompts. If extraction fails (empty JSON), the document will be mostly empty.

**3. Document generation is a background task.** `POST /documents/generate` returns HTTP 200 immediately. AI runs in background. Poll `GET /documents/{id}/status` to track progress.

**4. Two completely separate SAP connection paths exist.** File upload (offline) and Live SAP HTTP fetch (online). These are independent code paths. Live mode requires the `ZCL_DOC_HTTP` ABAP class installed in SAP.

**5. AI engine selection is automatic.** BTP tried first. Fails or unconfigured → OpenAI automatically. You cannot choose per-request.

**6. All 14 sections run in parallel (max 4 at once).** `asyncio.Semaphore(4)` in doc_generator.py. One section failing does NOT stop others. Document can be `completed` with some failed sections.

**7. PDF, DOCX, HTML are generated on demand.** NOT stored in database. Every download re-renders from JSON section data. If source JSON is empty, export will be empty.

**8. All resources are user-isolated.** A user only sees their own projects/uploads/documents. Admin role bypasses all ownership checks. Enforced by `assert_owner_or_admin()`.

**9. JWT tokens are stateless.** Logout just clears localStorage. Server does NOT blacklist tokens. Token is valid until expiry (12h) even after logout.

**10. RFC bridge is off by default.** `SAP_RFC_ENABLED=false`. Primary SAP method is HTTP Doc API. Do not touch RFC unless explicitly needed.

### 11.2 Development Environment Setup

```bash
# Prerequisites: Python 3.12+, Node.js 20+, PostgreSQL 16, Git

# 1. Backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. Create database
createdb docai_db

# 3. Configure environment
copy .env.example .env
# Edit .env — REQUIRED minimum:
# DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/docai_db
# JWT_SECRET=<run: python -c "import secrets; print(secrets.token_hex(32))">
# OPENAI_API_KEY=<your key>

# 4. Start backend
uvicorn app.main:app --reload --port 8000

# 5. Frontend
cd frontend
npm install
npm run dev
# Opens on http://localhost:3000

# 6. Verify
curl http://localhost:8000/api/health
# Open http://localhost:8000/docs  (Swagger UI)
```

### 11.3 How to Add a New Documentation Section (e.g., Section 15)

1. **Add column to Document model** (`app/models/document.py`):
   ```python
   new_section = Column(JSON)
   ```

2. **Add database column**:
   ```sql
   ALTER TABLE documents ADD COLUMN new_section JSONB;
   ```

3. **Add AI method to AIService** (`app/services/ai_service.py`):
   ```python
   async def generate_new_section(self, parsed_data: dict, source_code: str) -> dict:
       system = "You are an SAP expert. Return JSON with key: ..."
       prompt = f"Analyze: {json.dumps(parsed_data)[:3000]}"
       return await self._call_ai(system, prompt)
   ```

4. **Register in SECTIONS** (`app/services/doc_generator.py`):
   ```python
   SECTIONS = [...existing..., ("new_section", "generate_new_section")]
   ```

5. **Add renderer** in pdf_service.py, docx_service.py, html_service.py

6. **Add React component** in `frontend/src/components/documents/`

7. **Add tab** in DocumentNav.tsx

### 11.4 How to Improve an AI Prompt

All prompts are in `app/services/ai_service.py`. Each method has:
- `system` — Role instruction (who the AI acts as)
- `prompt` — Data + question

**Best practices:**
- Always specify the exact JSON structure you want returned
- Always add "Respond ONLY with valid JSON" in the prompt
- Include actual extracted data (not just the raw source) for accuracy
- Use `max_tokens=8192` for complex sections
- Temperature is always 0.3 (consistent, factual output)

### 11.5 Environment Variables Minimum Checklist

```
REQUIRED (app won't start without):
  DATABASE_URL    postgresql+asyncpg://user:pass@host:5432/dbname
  JWT_SECRET      32+ character random string

REQUIRED for AI generation:
  OPENAI_API_KEY  Your OpenAI key  (OR configure all BTP_* vars instead)

OPTIONAL for live SAP fetch:
  SAP_DOC_API_URL       https://<sap-host>:<port>/sap/bc/zdoc
  SAP_DOC_API_USER      SAP technical user
  SAP_DOC_API_PASSWORD  SAP technical user password
  SAP_DOC_API_CLIENT    SAP client number (e.g., 120)

OPTIONAL for BTP AI (overrides OpenAI):
  BTP_CLIENT_ID, BTP_CLIENT_SECRET, BTP_TOKEN_URL,
  BTP_AI_API_URL, BTP_DEPLOYMENT_ID
```

### 11.6 Understanding the Coverage Report

Every completed document contains `cover_data._coverage_report`:
```json
{
  "_coverage_report": {
    "status": "PARTIAL",
    "total_extracted": 15,
    "total_documented": 12,
    "gaps": [
      { "object_type": "function_calls", "extracted": 8, "documented": 5, "missing": 3 }
    ]
  }
}
```
- `PASS` = AI documented everything that was extracted
- `PARTIAL` = AI missed some objects. The `gaps` list shows what was missed.

This is stored in `cover_data` (not a separate column) so it is always visible.

---


## 12. Common Issues and Fixes

---

### Issue 1: "Missing required settings: DATABASE_URL, JWT_SECRET"
**Symptom:** Server crashes immediately on startup.
**Cause:** `.env` file missing or has empty required values.
**Fix:**
```bash
cd backend
copy .env.example .env
# Edit .env and set DATABASE_URL and JWT_SECRET
python -c "import secrets; print(secrets.token_hex(32))"
# Use the output as JWT_SECRET value
```

---

### Issue 2: Document stuck at "queued" forever
**Cause A:** No AI engine configured.
**Fix:** Set `OPENAI_API_KEY` in `.env`, restart server.

**Cause B:** Database connection failing inside background task.
**Fix:** Verify `DATABASE_URL` includes `asyncpg`. Ensure PostgreSQL is running.

**Cause C:** Server crashed after queueing.
**Fix:** Check server logs. Restart backend. The queued document will NOT auto-resume — delete and regenerate.

---

### Issue 3: AI generates generic/empty content
**Cause:** `parsed_metadata` is empty — extraction found nothing.
**Debug:**
```sql
SELECT filename, jsonb_array_length(parsed_metadata->'tables_used') as tables
FROM uploads ORDER BY created_at DESC LIMIT 5;
```
**Fix:** If counts are 0, the file is not valid ABAP. Check the content in `uploads.content` column. For SmartForms, verify XML contains `<sf:SMARTFORM` tag.

---

### Issue 4: PDF export shows "No records" throughout
**Cause:** The JSON section columns on the Document are empty `{}` or `{"error": "..."}`.
**Debug:**
```
GET /api/documents/{id}/section/technical_view
```
If it returns `{"error": "..."}`, that section failed during generation.
**Fix:** Delete the document. Fix the AI configuration. Regenerate.

---

### Issue 5: SAP search returns no results
**Cause A:** Wrong SAP credentials. **Fix:** Verify user/password. Check user not locked in SU01.
**Cause B:** `SAP_DOC_API_URL` not configured. **Fix:** Set it in `.env`.
**Cause C:** Wrong search pattern. **Fix:** Use uppercase + `*` wildcard. Example: `ZSD_INV*` not `zsd_inv%`.

---

### Issue 6: CORS error in browser console
**Cause:** Frontend URL not in `CORS_ORIGINS`.
**Fix:**
```
# In backend/.env:
CORS_ORIGINS=["http://localhost:3000","https://your-domain.com"]
# Restart backend after changing
```

---

### Issue 7: "File type '.exe' is not allowed"
**Cause:** Security feature blocking executable uploads.
**Fix:** This is intentional. Blocked types: `.exe`, `.dll`, `.bat`, `.sh`, `.cmd`, `.msi`, `.dmg`, `.bin`, `.iso`. Do not modify without security review.

---

### Issue 8: "Too many login attempts. Please wait X seconds"
**Cause:** Rate limiter: 5 failures per email in 5 minutes.
**Fix:** Wait 5 minutes. Counter is in-memory — **resets on server restart**. Do NOT disable in production — it prevents brute force attacks.

---

### Issue 9: "JWT_SECRET must be at least 32 characters"
**Fix:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
# Copy output to JWT_SECRET in .env
```

---

### Issue 10: SELECT-in-LOOP Performance Warning
**Cause:** Uploaded ABAP runs SELECT inside a LOOP. Critical anti-pattern.
**SAP Fix Pattern:**
```abap
" WRONG - SELECT inside loop (N database calls)
LOOP AT lt_vbrp INTO ls_vbrp.
  SELECT SINGLE * FROM vbrk INTO ls_vbrk WHERE vbeln = ls_vbrp-vbeln.
ENDLOOP.

" CORRECT - FOR ALL ENTRIES (1 database call)
SELECT * FROM vbrk INTO TABLE lt_vbrk
    FOR ALL ENTRIES IN lt_vbrp
    WHERE vbeln = lt_vbrp-vbeln.
```
This is flagged by `analysis_service.detect_performance_issues()` and appears in Section 11 (Performance Review) of the generated document.

---

### Issue 11: HTTP 403 from SAP — "Missing S_DEVELOP authorization"
**Cause:** SAP technical user lacks display authorization.
**Fix (by SAP Basis/Security team):**
1. Open transaction `PFCG`
2. Edit the role for the DOC AI technical user
3. Add authorization object `S_DEVELOP`:
   - `DEVCLASS = *`
   - `OBJTYPE = *`
   - `OBJNAME = *`
   - `P_GROUP = *`
   - `ACTVT = 03` (display — do NOT give 01/02 create/change)
4. Generate profile and assign to user

---

### Issue 12: SmartForm sections show no data
**Cause A:** File is not a SmartForm XML export.
**Fix:** Export from transaction `SMARTFORMS` as XML. Verify file starts with `<?xml` and contains `<sf:SMARTFORM`.

**Cause B:** Encoding issue.
**Fix:** Ensure XML file is UTF-8 encoded. SAP may export as ISO-8859-1. Convert using Notepad++ or VS Code (Save As → UTF-8).

---

### Issue 13: "asyncpg" driver error on startup
**Cause:** Wrong DATABASE_URL format.
**Fix:** Must use `postgresql+asyncpg://` prefix, not `postgresql://`:
```
# WRONG:
DATABASE_URL=postgresql://user:pass@localhost:5432/docai_db

# CORRECT:
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/docai_db
```

---

### Issue 14: Generated document shows "PARTIAL" coverage
**Cause:** AI generated the document but missed some extracted objects.
**Fix:**
- Check `cover_data._coverage_report.gaps` for what was missed
- Usually means the AI response was truncated due to token limits
- For complex objects: try increasing `max_tokens` in the relevant AIService method
- Or delete and regenerate — AI output varies per call

---

*Document prepared: September 30, 2026*
*System Version: DOC AI v1.0.0*
*Classification: Internal Knowledge Transfer — New Developer Onboarding*
*Scope: Complete system documentation — Backend, Frontend, AI Engine, SAP Integration*

