import asyncio
import logging
import time
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ERROR_MESSAGES = {
    401: "SAP rejected the technical user credentials",
    403: "SAP user is missing S_DEVELOP display authorization",
    404: "SAP service /sap/bc/zdoc is not active",
}

STATUS_MAP = {400: 400, 401: 502, 403: 403, 404: 503}

# Maximum objects fetched per type during repository graph construction.
# Prevents runaway fetches on very large dependency graphs.
_REPO_MAX_PER_TYPE = 20

# Object types that carry source code and are worth reading in full.
_SOURCE_TYPES = {"PROG", "CLAS", "INTF", "FUNC", "FUGR", "SSFO", "DDLS"}

# Object types that are read as dictionary/schema objects.
_DICT_TYPES = {"TABL", "DTEL", "DOMA"}


class SapDocApiError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


async def _call(params: dict, timeout: float) -> dict | list:
    if not settings.SAP_DOC_API_URL:
        raise SapDocApiError("SAP_DOC_API_URL is not configured", 503)
    # SAP_DOC_API_USER / PASSWORD are optional — used only when no per-request
    # credentials were supplied. _call_with_creds raises 401 if both are empty.
    return await _call_with_creds(
        params,
        sap_url=settings.SAP_DOC_API_URL,
        sap_user=settings.SAP_DOC_API_USER,
        sap_password=settings.SAP_DOC_API_PASSWORD,
        sap_client=settings.SAP_DOC_API_CLIENT,
        verify_ssl=settings.SAP_DOC_API_VERIFY_SSL,
        timeout=timeout,
    )


async def _call_with_creds(
    params: dict,
    sap_url: str,
    sap_user: str,
    sap_password: str,
    sap_client: str,
    verify_ssl: bool,
    timeout: float,
) -> dict | list:
    if not sap_url:
        raise SapDocApiError("SAP_DOC_API_URL is not configured", 503)
    if not sap_user or not sap_password:
        raise SapDocApiError(
            "SAP credentials are required — provide X-SAP-User and X-SAP-Password headers",
            401,
        )

    query = {**params, "sap-client": sap_client}
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=verify_ssl) as client:
            resp = await client.get(
                sap_url,
                params=query,
                auth=(sap_user, sap_password),
            )
    except httpx.TimeoutException as exc:
        raise SapDocApiError("SAP did not respond in time", 504) from exc
    except httpx.HTTPError as exc:
        raise SapDocApiError(f"SAP is not reachable: {exc}", 502) from exc

    elapsed = int((time.perf_counter() - started) * 1000)
    logger.info(
        "SAP %s %s -> HTTP %s in %d ms",
        params.get("action"), params.get("q") or params.get("object"), resp.status_code, elapsed,
    )

    try:
        data = resp.json()
    except ValueError:
        data = None

    if resp.status_code != 200:
        message = data.get("error") if isinstance(data, dict) else None
        raise SapDocApiError(
            message or ERROR_MESSAGES.get(resp.status_code, f"SAP returned HTTP {resp.status_code}"),
            STATUS_MAP.get(resp.status_code, 502),
        )
    if data is None:
        raise SapDocApiError("SAP returned an invalid response", 502)
    if isinstance(data, dict) and data.get("error"):
        raise SapDocApiError(data["error"], 400)
    return data


async def search_objects(query: str) -> list[dict]:
    return await _call({"action": "search", "q": query}, timeout=30)


# TADIR object types searched when no type filter is applied.
_ALL_SEARCH_TYPES = [
    "PROG", "CLAS", "INTF", "FUNC", "FUGR",
    "SSFO", "DDLS", "TABL", "DTEL", "DOMA", "TRAN",
]


def _normalize_pattern(pattern: str) -> str:
    """
    Normalise a user-supplied search pattern.
    - Uppercase
    - Trailing '*' is added when no wildcard is present (exact prefix match)
    - Leading/trailing whitespace stripped
    """
    p = pattern.strip().upper()
    if not p:
        return p
    # If the user typed only letters (no wildcard) treat it as prefix
    if "*" not in p:
        p = p + "*"
    return p


def _is_wildcard(pattern: str) -> bool:
    return "*" in pattern


async def search_objects_wildcard(
    pattern: str,
    types: list[str] | None,
    creds: dict | None,
    max_results: int = 100,
) -> list[dict]:
    """
    SAP-style wildcard search across multiple object types.

    Pattern supports SAP SE80 wildcards:
        Z*           prefix match
        *INVOICE*    contains match
        ZSD*GST*     multiple wildcards
        *PRINT       suffix match

    When creds is None the call uses env-configured credentials.
    Results are deduplicated (by objectName+objectType) and capped at max_results.
    """
    target_types = [t.upper() for t in (types or _ALL_SEARCH_TYPES)]
    sem = asyncio.Semaphore(5)

    async def _search_one(obj_type: str) -> list[dict]:
        async with sem:
            params = {"action": "search", "q": pattern, "type": obj_type}
            try:
                if creds:
                    result = await _call_with_creds(
                        params,
                        sap_url=creds["sap_url"],
                        sap_user=creds["sap_user"],
                        sap_password=creds["sap_password"],
                        sap_client=creds["sap_client"],
                        verify_ssl=settings.SAP_DOC_API_VERIFY_SSL,
                        timeout=30,
                    )
                else:
                    result = await _call(params, timeout=30)
                return result if isinstance(result, list) else []
            except SapDocApiError as exc:
                logger.debug("Wildcard search [%s] pattern=%s: %s", obj_type, pattern, exc)
                return []

    raw_results = await asyncio.gather(*[_search_one(t) for t in target_types])

    seen: set[str] = set()
    merged: list[dict] = []
    for hits in raw_results:
        for hit in hits:
            name = hit.get("objectName", "")
            otype = hit.get("objectType", "")
            key = f"{otype}:{name}"
            if name and key not in seen:
                seen.add(key)
                merged.append(hit)
            if len(merged) >= max_results:
                break
        if len(merged) >= max_results:
            break

    merged.sort(key=lambda h: h.get("objectName", ""))
    return merged[:max_results]


async def read_object(name: str) -> dict:
    data = await _call({"action": "read", "object": name}, timeout=settings.SAP_DOC_API_TIMEOUT)
    if data.get("objectType") == "UNKNOWN":
        raise SapDocApiError(f"Object {name} not found in SAP", 404)
    return data


async def read_class(name: str) -> dict:
    return await _call({"action": "read_class", "object": name}, timeout=settings.SAP_DOC_API_TIMEOUT)


async def read_table(name: str) -> dict:
    return await _call({"action": "read_table", "object": name}, timeout=60)


async def read_data_element(name: str) -> dict:
    return await _call({"action": "read_dtel", "object": name}, timeout=30)


async def read_domain(name: str) -> dict:
    return await _call({"action": "read_domain", "object": name}, timeout=30)


async def read_cds(name: str) -> dict:
    return await _call({"action": "read_cds", "object": name}, timeout=settings.SAP_DOC_API_TIMEOUT)


async def read_function_module(name: str) -> dict:
    return await _call({"action": "read_fm", "object": name}, timeout=settings.SAP_DOC_API_TIMEOUT)


async def build_dependency_tree(name: str, object_type: str, max_depth: int = 3) -> dict:
    return await _call(
        {"action": "tree", "object": name, "type": object_type, "depth": str(max_depth)},
        timeout=settings.SAP_DOC_API_TIMEOUT * 2,
    )


# Map TADIR object type to the correct targeted reader.
# Falls back to read_object for types not yet individually handled.
_TYPE_READERS = {
    "CLAS": read_class,
    "INTF": read_class,       # interfaces share the class reader
    "TABL": read_table,
    "DTEL": read_data_element,
    "DOMA": read_domain,
    "DDLS": read_cds,
    "FUNC": read_function_module,
}


async def read_by_type(name: str, object_type: str) -> dict:
    """Dispatch to the correct reader based on TADIR object type."""
    reader = _TYPE_READERS.get(object_type.upper(), read_object)
    return await reader(name)


async def _read_by_type_with_creds(name: str, object_type: str, creds: dict) -> dict:
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
        logger.warning("Could not read %s %s: %s", object_type, name, exc)
        return {"object": name, "objectType": object_type, "error": str(exc)}


def build_source(detail: dict) -> str:
    name = detail.get("mainProgram") or detail.get("object", "")
    parts = [f"*=== MAIN {name} ===", detail.get("sourceCode", "")]

    for include in detail.get("includes", []):
        parts.append(f"*=== INCLUDE {include.get('name', '')} ===")
        parts.append(include.get("source", ""))

    fields = detail.get("fields") or []
    if fields and not detail.get("sourceCode"):
        parts.append(f"*=== FIELDS {detail.get('object', '')} ===")
        for f in fields:
            key = "KEY " if f.get("keyflag") == "X" else ""
            parts.append(
                f"* {key}{f.get('fieldname')} {f.get('rollname')} "
                f"{f.get('datatype')}({f.get('leng')},{f.get('decimals')})"
            )

    return "\n".join(parts)