"""
SAP S/4HANA Live Connection Service — RFC Bridge Architecture.

PRIMARY connection method:
  sap_rfc_bridge.js — a local Node.js HTTP server (port 5001) that wraps
  node-rfc (the same library used by the working dashboard). Python calls
  it via httpx. This avoids the pyrfc wheel limitation on Python 3.14.

FALLBACK: direct pyrfc if available (Python ≤ 3.11 with pyrfc installed).

Bridge endpoints (all on http://127.0.0.1:5001):
  GET /health              → RFC PING
  GET /search?q=ZSD        → TADIR search
  GET /source?name=ZPROG   → RPY_PROGRAM_READ
  GET /smartform?name=ZSF  → SSF_FUNCTION_MODULE_NAME

Start the bridge:
  cd backend && node sap_rfc_bridge.js
"""

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Bridge base URL — can be overridden via SAP_BRIDGE_URL env var
_BRIDGE_DEFAULT = "http://127.0.0.1:5001"


@dataclass
class SAPObject:
    """Represents a single SAP object fetched from S/4HANA."""
    name: str
    object_type: str
    source_code: str = ""
    xml_source: str = ""
    description: str = ""
    package: str = ""
    created_by: str = ""
    created_date: str = ""
    changed_by: str = ""
    changed_date: str = ""
    includes: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class FetchResult:
    """Aggregated result from fetching a Z-Object and all its dependencies."""
    main_object: Optional[SAPObject] = None
    all_objects: list = field(default_factory=list)
    combined_source: str = ""
    combined_xml: str = ""
    object_count: int = 0
    errors: list = field(default_factory=list)
    success: bool = False


class SAPS4Service:
    """
    Live S/4HANA connection service.

    Uses sap_rfc_bridge.js (Node.js, port 5001) as an RFC bridge so
    Python 3.14 can call SAP without needing a pyrfc wheel.

    Falls back to direct pyrfc if installed (Python ≤ 3.11).
    """

    OBJECT_TYPE_MAP = {
        "program":         "PROG",
        "report":          "PROG",
        "function_module": "FUGR",
        "class":           "CLAS",
        "interface":       "INTF",
        "smartform":       "SFOM",
        "cds_view":        "DDLS",
        "rap":             "BDEF",
        "enhancement":     "ENHO",
        "table":           "TABL",
        "include":         "PROG",
    }

    def __init__(self):
        # Always load from the pydantic settings object (which reads .env) so
        # that there is a single source of truth and no raw os.environ calls
        # for credentials.
        try:
            from app.config import settings as cfg
            self.rfc_enabled  = cfg.SAP_RFC_ENABLED
            self.adt_enabled  = cfg.SAP_ADT_ENABLED
            self.bridge_url   = cfg.SAP_BRIDGE_URL.rstrip("/")
            self.rfc_host     = cfg.SAP_HOST
            self.rfc_sysnr    = cfg.SAP_SYSNR
            self.rfc_client   = cfg.SAP_CLIENT
            self.rfc_user     = cfg.SAP_USER
            self.rfc_pass     = cfg.SAP_PASSWORD
            self.rfc_lang     = cfg.SAP_LANG
            self.timeout      = cfg.SAP_S4_TIMEOUT
            self.max_depth    = cfg.SAP_S4_MAX_DEPTH
            # ADT / HTTP params
            self.adt_host     = cfg.SAP_S4_HOST
            self.adt_user     = cfg.SAP_S4_BASIC_USER
            self.adt_pass     = cfg.SAP_S4_BASIC_PASS
            self.adt_auth_mode = cfg.SAP_S4_AUTH_MODE
            self.adt_verify_ssl = cfg.SAP_S4_VERIFY_SSL
        except Exception:
            # Fallback to safe defaults if settings unavailable during import
            self.rfc_enabled  = False
            self.adt_enabled  = False
            self.bridge_url   = _BRIDGE_DEFAULT
            self.rfc_host = self.rfc_user = self.rfc_pass = ""
            self.rfc_sysnr = "00"
            self.rfc_client = "120"
            self.rfc_lang = "EN"
            self.timeout = 60
            self.max_depth = 3
            self.adt_host = self.adt_user = self.adt_pass = ""
            self.adt_auth_mode = "basic"
            self.adt_verify_ssl = True

    # ─────────────────────────────────────────
    # Configuration check
    # ─────────────────────────────────────────

    def is_configured(self) -> bool:
        """Return True if RFC params are set (bridge or direct pyrfc)."""
        return bool(self.rfc_host and self.rfc_user and self.rfc_pass)

    def _pyrfc_available(self) -> bool:
        try:
            import pyrfc  # noqa
            return True
        except ImportError:
            return False

    # ─────────────────────────────────────────
    # Bridge HTTP helpers
    # ─────────────────────────────────────────

    async def _bridge_get(self, path: str, params: dict | None = None) -> dict:
        """Call the local RFC bridge and return parsed JSON."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.bridge_url}{path}", params=params or {})
            resp.raise_for_status()
            return resp.json()

    async def _bridge_alive(self) -> bool:
        """Check if the bridge process is running (fast TCP check)."""
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                await client.get(f"{self.bridge_url}/health")
            return True
        except Exception:
            return False

    # ─────────────────────────────────────────
    # Direct pyrfc helpers (fallback)
    # ─────────────────────────────────────────

    def _rfc_params(self) -> dict:
        return {
            "ashost": self.rfc_host,
            "sysnr":  self.rfc_sysnr,
            "client": self.rfc_client,
            "user":   self.rfc_user,
            "passwd": self.rfc_pass,
            "lang":   self.rfc_lang,
        }

    def _rfc_read_source_sync(self, program_name: str) -> str:
        try:
            import pyrfc
            conn = pyrfc.Connection(**self._rfc_params())
            result = conn.call("RPY_PROGRAM_READ", PROGRAMM=program_name.upper())
            conn.close()
            return "\n".join(r.get("LINE", "") for r in result.get("SOURCE_EXTENDED", []))
        except Exception as e:
            logger.warning(f"pyrfc source read failed for {program_name}: {e}")
            return ""

    def _rfc_search_sync(self, query: str) -> list[dict]:
        try:
            import pyrfc
            conn = pyrfc.Connection(**self._rfc_params())
            result = conn.call(
                "RFC_READ_TABLE",
                QUERY_TABLE="TADIR",
                DELIMITER="|",
                FIELDS=[
                    {"FIELDNAME": "OBJECT"},
                    {"FIELDNAME": "OBJ_NAME"},
                    {"FIELDNAME": "DEVCLASS"},
                    {"FIELDNAME": "AUTHOR"},
                ],
                OPTIONS=[
                    {"TEXT": f"PGMID = 'R3TR'"},
                    {"TEXT": f"AND OBJ_NAME LIKE '{query.upper()}%'"},
                ],
                ROWCOUNT=100,
            )
            conn.close()
            objects = []
            for row in result.get("DATA", []):
                parts = (row.get("WA", "")).split("|")
                if len(parts) >= 2:
                    objects.append({
                        "name":        parts[1].strip(),
                        "object_type": parts[0].strip(),
                        "description": "",
                        "package":     parts[2].strip() if len(parts) > 2 else "",
                        "author":      parts[3].strip() if len(parts) > 3 else "",
                    })
            return objects
        except Exception as e:
            logger.warning(f"pyrfc search failed: {e}")
            return []

    # ─────────────────────────────────────────
    # Connectivity check
    # ─────────────────────────────────────────

    async def ping(self) -> dict:
        """
        Test connectivity to S/4HANA.
        Tries bridge first, then direct pyrfc, then reports not configured.
        """
        if not self.is_configured():
            return {
                "ok": False,
                "message": (
                    "SAP connection not configured. "
                    "Set SAP_HOST, SAP_USER, SAP_PASSWORD in backend/.env"
                ),
                "host": self.rfc_host or "(not set)",
                "method": "none",
            }

        # ── Try RFC bridge (primary) ────────────────────────────────────
        if await self._bridge_alive():
            try:
                data = await self._bridge_get("/health")
                return {
                    "ok":      data.get("ok", False),
                    "message": data.get("message", "Bridge responded"),
                    "host":    data.get("host", self.rfc_host),
                    "method":  "rfc-bridge",
                }
            except Exception as e:
                logger.warning(f"Bridge health call failed: {e}")

        # ── Try direct pyrfc (fallback) ─────────────────────────────────
        if self._pyrfc_available():
            try:
                def _ping():
                    import pyrfc
                    c = pyrfc.Connection(**self._rfc_params())
                    c.ping()
                    c.close()
                await asyncio.get_running_loop().run_in_executor(None, _ping)
                return {
                    "ok": True,
                    "message": f"Connected via pyrfc (ashost={self.rfc_host})",
                    "host": self.rfc_host,
                    "method": "pyrfc",
                }
            except Exception as e:
                return {
                    "ok": False,
                    "message": f"RFC failed: {str(e)}",
                    "host": self.rfc_host,
                    "method": "pyrfc",
                }

        # ── Bridge not running, pyrfc not installed ─────────────────────
        return {
            "ok": False,
            "message": (
                "SAP RFC bridge is not running. "
                "Start it with: node backend/sap_rfc_bridge.js"
            ),
            "host": self.rfc_host,
            "method": "none",
        }

    # ─────────────────────────────────────────
    # Object Search
    # ─────────────────────────────────────────

    async def search_objects(self, query: str, object_type: str = "") -> list[dict]:
        """Search TADIR for Z-objects matching query prefix."""
        if not self.is_configured():
            raise RuntimeError("SAP connection not configured")

        query = query.upper().strip()
        if not query:
            return []

        # ── Bridge path (primary) ───────────────────────────────────────
        if await self._bridge_alive():
            try:
                data = await self._bridge_get("/search", {"q": query})
                objects = data.get("objects", [])
                if object_type:
                    sap_type = self.OBJECT_TYPE_MAP.get(object_type.lower(), "")
                    if sap_type:
                        objects = [o for o in objects if o.get("object_type") == sap_type]
                return objects
            except Exception as e:
                logger.warning(f"Bridge search failed: {e}")

        # ── Direct pyrfc fallback ───────────────────────────────────────
        if self._pyrfc_available():
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(None, self._rfc_search_sync, query)
            if object_type:
                sap_type = self.OBJECT_TYPE_MAP.get(object_type.lower(), "")
                if sap_type:
                    results = [r for r in results if r.get("object_type") == sap_type]
            return results

        raise RuntimeError(
            "SAP RFC bridge is not running. Start it with: node backend/sap_rfc_bridge.js"
        )

    # ─────────────────────────────────────────
    # Source reading
    # ─────────────────────────────────────────

    async def _read_source(self, program_name: str) -> str:
        """Read ABAP source via bridge or direct pyrfc."""
        # Bridge
        if await self._bridge_alive():
            try:
                data = await self._bridge_get("/source", {"name": program_name})
                source = data.get("source", "")
                if data.get("error"):
                    logger.warning(f"Bridge /source error for {program_name}: {data['error']}")
                logger.info(f"Bridge /source {program_name}: {len(source)} chars, lineCount={data.get('lineCount',0)}")
                return source
            except Exception as e:
                logger.warning(f"Bridge source read failed for {program_name}: {e}")

        # Direct pyrfc
        if self._pyrfc_available():
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._rfc_read_source_sync, program_name)

        return ""

    async def _read_smartform(self, sf_name: str) -> str:
        """Read SmartForm source via bridge."""
        if await self._bridge_alive():
            try:
                data = await self._bridge_get("/smartform", {"name": sf_name})
                return data.get("source", "")
            except Exception as e:
                logger.warning(f"Bridge smartform read failed for {sf_name}: {e}")
        return ""

    # ─────────────────────────────────────────
    # Source extraction helpers
    # ─────────────────────────────────────────

    def _extract_includes(self, source: str) -> list[str]:
        return re.findall(r"^\s*INCLUDE\s+(\w+)", source, re.IGNORECASE | re.MULTILINE)

    def _extract_smartform_calls(self, source: str) -> list[str]:
        return re.findall(r"FORMNAME\s*=\s*['\"]?([A-Z_][A-Z0-9_]+)", source, re.IGNORECASE)

    def _extract_class_references(self, source: str) -> list[str]:
        classes     = re.findall(r"\bCLASS\s+(\w+)\s+(?:DEFINITION|IMPLEMENTATION)", source, re.IGNORECASE)
        create_refs = re.findall(r"CREATE OBJECT.*?TYPE\s+(\w+)", source, re.IGNORECASE)
        return list(set(classes + create_refs))

    # ─────────────────────────────────────────
    # Main fetch orchestrator
    # ─────────────────────────────────────────

    async def fetch_full_object(
        self,
        object_name: str,
        object_type: str = "PROG",
        depth: int = 0,
    ) -> FetchResult:
        """
        Fetch a Z-Object and ALL its dependencies from S/4HANA.
        Uses RFC bridge as primary, direct pyrfc as fallback.
        """
        result = FetchResult()

        if not self.is_configured():
            result.errors.append(
                "SAP not configured — set SAP_HOST, SAP_USER, SAP_PASSWORD in .env"
            )
            return result

        object_name = object_name.upper().strip()
        sap_type    = self.OBJECT_TYPE_MAP.get(object_type.lower(), object_type.upper())

        logger.info(f"Fetching {object_name} ({sap_type}), depth={depth}")

        try:
            source_parts: list[str] = []
            xml_parts:    list[str] = []
            all_objects:  list[SAPObject] = []

            # ── 1. Fetch main object source ─────────────────────────────
            main_source = ""
            main_xml    = ""

            if sap_type == "FUGR":
                # Function groups: source lives in includes named L<FUGR>TOP, L<FUGR>UXX, etc.
                fugr_candidates = [
                    f"L{object_name}TOP",   # global data / top include
                    f"L{object_name}UXX",   # function module source
                    f"L{object_name}F01",   # form routines
                    object_name,            # fallback: try direct name
                ]
                parts = []
                for candidate in fugr_candidates:
                    src = await self._read_source(candidate)
                    if src:
                        parts.append(f"*-- INCLUDE: {candidate} --*\n{src}")
                main_source = "\n\n".join(parts)
            elif sap_type in ("PROG", "INTF", "DDLS"):
                main_source = await self._read_source(object_name)
                # Auto-detect: if PROG returns nothing, try as function group includes
                if not main_source and sap_type == "PROG":
                    logger.info(f"PROG read empty for {object_name}, trying FUGR include convention")
                    fugr_parts = []
                    for candidate in [f"L{object_name}TOP", f"L{object_name}UXX", f"L{object_name}F01"]:
                        src = await self._read_source(candidate)
                        if src:
                            fugr_parts.append(f"*-- INCLUDE: {candidate} --*\n{src}")
                    if fugr_parts:
                        main_source = "\n\n".join(fugr_parts)
                        sap_type = "FUGR"
            elif sap_type == "CLAS":
                main_source = await self._read_source(f"CL_{object_name}")
                if not main_source:
                    main_source = await self._read_source(object_name)
            elif sap_type == "SFOM":
                main_xml = await self._read_smartform(object_name)

            # ── 2. Build main SAPObject ─────────────────────────────────
            main_obj = SAPObject(
                name=object_name,
                object_type=sap_type,
                source_code=main_source,
                xml_source=main_xml,
            )

            if main_source:
                source_parts.append(f"*-- MAIN OBJECT: {object_name} ({sap_type}) --*\n{main_source}")
            if main_xml:
                xml_parts.append(main_xml)
            all_objects.append(main_obj)

            # ── 3. Resolve dependencies ─────────────────────────────────
            if depth < self.max_depth and main_source:

                # Includes
                includes = self._extract_includes(main_source)
                main_obj.includes = includes
                for inc in includes:
                    if inc.upper() == object_name:
                        continue
                    inc_src = await self._read_source(inc)
                    if inc_src:
                        source_parts.append(f"*-- INCLUDE: {inc} --*\n{inc_src}")
                        all_objects.append(SAPObject(name=inc, object_type="PROG", source_code=inc_src))
                        main_obj.dependencies.append({"type": "INCLUDE", "name": inc})

                # SmartForms
                for sf in self._extract_smartform_calls(main_source):
                    if len(sf) < 3:
                        continue
                    sf_src = await self._read_smartform(sf)
                    if sf_src:
                        xml_parts.append(sf_src)
                        all_objects.append(SAPObject(name=sf, object_type="SFOM", xml_source=sf_src))
                        main_obj.dependencies.append({"type": "SMARTFORM", "name": sf})

                # Z-Classes (1 level only)
                if depth < 1:
                    for cls in self._extract_class_references(main_source)[:10]:
                        if not cls.upper().startswith("Z"):
                            continue
                        cls_src = await self._read_source(cls)
                        if cls_src:
                            source_parts.append(f"*-- CLASS: {cls} --*\n{cls_src}")
                            all_objects.append(SAPObject(name=cls, object_type="CLAS", source_code=cls_src))
                            main_obj.dependencies.append({"type": "CLASS", "name": cls})

            # ── 4. Build result ─────────────────────────────────────────
            result.main_object     = main_obj
            result.all_objects     = all_objects
            result.combined_source = "\n\n".join(source_parts)
            result.combined_xml    = "\n\n".join(xml_parts)
            result.object_count    = len(all_objects)
            result.success         = bool(result.combined_source or result.combined_xml)

            if not result.success:
                result.errors.append(
                    f"No source found for {object_name}. "
                    "Ensure the RFC bridge is running (node backend/sap_rfc_bridge.js) "
                    "and the object name exists in SAP."
                )

            logger.info(
                f"Fetched {object_name}: {len(all_objects)} objects, "
                f"{len(result.combined_source)} source chars"
            )
            return result

        except Exception as e:
            logger.error(f"fetch_full_object error for {object_name}: {e}")
            result.errors.append(str(e))
            return result

    def build_combined_content(self, fetch_result: FetchResult) -> tuple[str, str]:
        """Build (content, filename) tuple for SAPObjectExtractor — unchanged interface."""
        if fetch_result.combined_xml:
            xml = fetch_result.combined_xml
            if fetch_result.combined_source:
                xml = f"<!-- ABAP_SOURCE:\n{fetch_result.combined_source[:5000]}\n-->\n" + xml
            name = fetch_result.main_object.name if fetch_result.main_object else "UNKNOWN"
            return xml, f"{name}.xml"

        if fetch_result.combined_source:
            name = fetch_result.main_object.name if fetch_result.main_object else "UNKNOWN"
            return fetch_result.combined_source, f"{name}.abap"

        return "", "unknown.abap"


# ─────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────

_sap_s4_service: Optional[SAPS4Service] = None


def get_sap_s4_service() -> SAPS4Service:
    global _sap_s4_service
    if _sap_s4_service is None:
        _sap_s4_service = SAPS4Service()
    return _sap_s4_service
