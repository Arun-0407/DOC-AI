"""
Analysis utilities — extract structural complexity and dependency metrics
from already-parsed SAP object data. No hardcoded logic.
"""


def calculate_complexity(parsed_data: dict) -> dict:
    """Calculate complexity from extracted parsed data."""
    ci = parsed_data.get("complexity_indicators", {})
    total_lines = ci.get("total_lines", 0)
    sel_in_loop = ci.get("select_in_loop", 0)
    sel_star = ci.get("select_star", 0)
    table_count = len(parsed_data.get("tables_used", []))
    fm_count = len(parsed_data.get("function_calls", []))
    form_count = len(parsed_data.get("forms", []))
    cond_count = len(parsed_data.get("conditions", []))
    code_blocks = len(parsed_data.get("code_blocks", parsed_data.get("embedded_abap_blocks", [])))

    score = 0
    if total_lines > 500: score += 1
    if total_lines > 2000: score += 2
    if sel_in_loop > 0: score += 2
    if sel_star > 5: score += 1
    if table_count > 10: score += 1
    if fm_count > 8: score += 1
    if code_blocks > 10: score += 1

    level = "high" if score >= 5 else "medium" if score >= 2 else "low"
    return {
        "complexity": level,
        "total_lines": total_lines,
        "select_in_loop": sel_in_loop,
        "select_star": sel_star,
        "table_count": table_count,
        "function_call_count": fm_count,
        "form_count": form_count,
        "condition_count": cond_count,
        "embedded_code_blocks": code_blocks,
        "complexity_score": score,
    }


def build_dependency_graph(parsed_data: dict) -> dict:
    """Build dependency graph from extracted objects."""
    prog = parsed_data.get("program_name", "PROGRAM")
    graph = {"root": prog, "edges": []}
    for fm in parsed_data.get("function_calls", []):
        graph["edges"].append({"from": prog, "to": fm.get("name", ""), "type": "CALL_FUNCTION"})
    for tx in parsed_data.get("call_transactions", []):
        graph["edges"].append({"from": prog, "to": tx.get("name", ""), "type": "CALL_TRANSACTION"})
    for t in parsed_data.get("tables_used", []):
        op = t.get("operation", t.get("source", "READ"))
        graph["edges"].append({"from": prog, "to": t.get("name", ""), "type": f"DB_{op}"})
    return graph


def detect_performance_issues(parsed_data: dict) -> list:
    """Detect performance issues from extracted metrics."""
    issues = []
    ci = parsed_data.get("complexity_indicators", {})
    if ci.get("select_in_loop", 0) > 0:
        issues.append({"type": "SELECT_IN_LOOP", "severity": "critical",
                        "count": ci["select_in_loop"], "recommendation": "Move SELECT outside loop, use FOR ALL ENTRIES"})
    if ci.get("select_star", 0) > 0:
        issues.append({"type": "SELECT_STAR", "severity": "medium",
                        "count": ci["select_star"], "recommendation": "Select only required fields"})
    if ci.get("nested_loops", 0) > 0:
        issues.append({"type": "NESTED_LOOPS", "severity": "high",
                        "count": ci["nested_loops"], "recommendation": "Refactor nested loops"})
    return issues


def detect_security_issues(parsed_data: dict) -> list:
    """Detect security gaps from extracted data."""
    issues = []
    auth_checks = parsed_data.get("auth_checks", parsed_data.get("auth_objects", []))
    tables = parsed_data.get("tables_used", [])
    sensitive = [t for t in tables if any(s in t.get("name","").upper() for s in
                 ["KNA1","LFA1","PA","CCARD","BSEG","VBRK","VBRP","KNB1"])]
    if sensitive and not auth_checks:
        issues.append({"type": "MISSING_AUTH_CHECK", "severity": "critical",
                        "detail": f"Accesses sensitive tables {[t['name'] for t in sensitive]} without AUTHORITY-CHECK"})
    return issues


def generate_call_hierarchy(parsed_data: dict) -> dict:
    """Build call hierarchy tree from extracted data."""
    root = parsed_data.get("program_name", "PROGRAM")
    forms = {f["name"]: f for f in parsed_data.get("forms", [])}
    fms = [f.get("name", "") for f in parsed_data.get("function_calls", [])]
    txns = [t.get("name", "") for t in parsed_data.get("call_transactions", [])]
    return {
        "name": root,
        "type": parsed_data.get("object_type", "program"),
        "children": (
            [{"name": f, "type": "FORM", "children": []} for f in list(forms.keys())[:20]] +
            [{"name": f, "type": "FUNCTION_MODULE", "children": []} for f in fms[:20]] +
            [{"name": t, "type": "TRANSACTION", "children": []} for t in txns[:10]]
        )
    }
