"""
SAP Repository Graph Builder.
Reads a complete SAP object graph from /sap/bc/zdoc, stores it as
repository_graph in upload.parsed_metadata, and builds the flat
concatenated source string consumed by the existing extractor.
"""
import asyncio
import logging
from typing import Optional

from app.config import settings
from app.services.sap_doc_api import SapDocApiError, _call_with_creds, read_by_type

logger = logging.getLogger(__name__)
_MAX_PER_TYPE = 20


async def _fetch_with_creds(name: str, object_type: str, creds: dict) -> dict:
    action_map = {
        "CLAS": "read_class", "INTF": "read_class",
        "TABL": "read_table", "DTEL": "read_dtel",
        "DOMA": "read_domain", "DDLS": "read_cds", "FUNC": "read_fm",
    }
    action = action_map.get(object_type.upper(), "read")
    try:
        result = await _call_with_creds(
            {"action": action, "object": name},
            sap_url=creds["sap_url"], sap_user=creds["sap_user"],
            sap_password=creds["sap_password"], sap_client=creds["sap_client"],
            verify_ssl=settings.SAP_DOC_API_VERIFY_SSL,
            timeout=settings.SAP_DOC_API_TIMEOUT,
        )
        return result if isinstance(result, dict) else {}
    except SapDocApiError as exc:
        logger.warning("Repo fetch %s %s: %s", object_type, name, exc)
        return {"object": name, "objectType": object_type, "error": str(exc)}


async def build_repository_graph(
    name: str,
    object_type: str,
    creds: Optional[dict] = None,
) -> dict:
    """
    Build the complete repository graph for a SAP object.

    Flow:
        Object
          -> read root object from /sap/bc/zdoc
          -> collect sub-object names from response fields
          -> fetch all sub-objects in parallel (semaphore=6, dedup via visited set)
          -> return graph dict with all sections populated

    creds: per-request SAP credentials dict. None = use env settings.
    """
    visited: set[str] = set()
    sem = asyncio.Semaphore(6)

    async def fetch(n: str, t: str) -> dict:
        key = f"{t}:{n}"
        if key in visited:
            return {}
        visited.add(key)
        async with sem:
            if creds:
                return await _fetch_with_creds(n, t, creds)
            return await read_by_type(n, t)

    root = await fetch(name, object_type)
    if not root or root.get("error"):
        return _empty_graph(name, object_type, root.get("error", "root read failed"))

    def names(lst: list) -> list[str]:
        return [i.get("name", "") for i in lst if isinstance(i, dict) and i.get("name")][:_MAX_PER_TYPE]

    plan = [
        ("include",   names(root.get("includes", [])),        "PROG"),
        ("class",     names(root.get("classes", [])),         "CLAS"),
        ("fm",        names(root.get("functionModules", [])), "FUNC"),
        ("cds",       names(root.get("cdsViews", [])),        "DDLS"),
        ("table",     names(root.get("tables", [])),          "TABL"),
        ("dtel",      names(root.get("dataElements", [])),    "DTEL"),
        ("domain",    names(root.get("domains", [])),         "DOMA"),
        ("smartform", names(root.get("smartForms", [])),      "SSFO"),
    ]

    tasks: list = []
    labels: list[str] = []
    for bucket, obj_names, otype in plan:
        for n in obj_names:
            tasks.append(fetch(n, otype))
            labels.append(bucket)

    raw = await asyncio.gather(*tasks, return_exceptions=True)

    buckets: dict[str, list] = {k: [] for k in ("include","class","fm","cds","table","dtel","domain","smartform")}
    for label, res in zip(labels, raw):
        if isinstance(res, Exception):
            logger.warning("Repo gather [%s]: %s", label, res)
        elif isinstance(res, dict) and res:
            buckets[label].append(res)

    graph = {
        "object":          root.get("object", name),
        "objectType":      root.get("objectType", object_type),
        "sourceCode":      root.get("sourceCode", ""),
        "includes":        buckets["include"],
        "classes":         buckets["class"],
        "functionModules": buckets["fm"],
        "cdsViews":        buckets["cds"],
        "tables":          buckets["table"],
        "dataElements":    buckets["dtel"],
        "domains":         buckets["domain"],
        "smartForms":      buckets["smartform"],
        "transactions":    root.get("transactions", []),
        "dependencies":    root.get("dependencies", []),
        "methods":         root.get("methods", []),
        "parameters":      root.get("parameters", {}),
        "fields":          root.get("fields", []),
    }
    logger.info("Repository graph %s %s: %d objects", object_type, name, 1 + sum(len(v) for v in buckets.values()))
    return graph


def _empty_graph(name: str, object_type: str, error: str) -> dict:
    return {
        "object": name, "objectType": object_type, "error": error,
        "sourceCode": "", "includes": [], "classes": [], "functionModules": [],
        "cdsViews": [], "tables": [], "dataElements": [], "domains": [],
        "smartForms": [], "transactions": [], "dependencies": [],
        "methods": [], "parameters": {}, "fields": [],
    }


def build_source_from_graph(graph: dict) -> str:
    """Flat concatenated source string from a repository graph."""
    parts: list[str] = []

    def _app(label: str, src: str) -> None:
        if src:
            parts.append(f"*=== {label} ===")
            parts.append(src)

    _app(f"MAIN {graph.get('object','')}", graph.get("sourceCode", ""))
    for inc in graph.get("includes", []):
        _app(f"INCLUDE {inc.get('object','')}", inc.get("sourceCode", ""))
    for cls in graph.get("classes", []):
        _app(f"CLASS {cls.get('object','')}", cls.get("sourceCode", ""))
    for fm in graph.get("functionModules", []):
        _app(f"FUNCTION MODULE {fm.get('object','')}", fm.get("sourceCode", ""))
    for cds in graph.get("cdsViews", []):
        _app(f"CDS VIEW {cds.get('object','')}", cds.get("sourceCode", ""))
    for sf in graph.get("smartForms", []):
        _app(f"SMARTFORM {sf.get('object','')}", sf.get("sourceCode", ""))
    for tbl in graph.get("tables", []):
        fields = tbl.get("fields", [])
        if fields:
            parts.append(f"*=== TABLE {tbl.get('object','')} ===")
            for f in fields:
                key = "KEY " if f.get("keyflag") == "X" else ""
                parts.append(f"*  {key}{f.get('fieldname','')} {f.get('rollname','')} {f.get('datatype','')}({f.get('leng',0)},{f.get('decimals',0)})")
    return "\n".join(parts)
