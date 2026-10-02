"""
parser_service.py — Legacy thin wrapper kept for import compatibility.
The production extraction engine is SAPObjectExtractor in utils/sap_extractor.py.
This module delegates to it so any code that imported parse_abap_source still works.
"""
import re
from typing import Dict, Any
from app.utils.sap_extractor import SAPObjectExtractor

_extractor = SAPObjectExtractor()


def parse_abap_source(content: str, file_type: str) -> Dict[str, Any]:
    """Delegate to the production-grade extractor.
    Kept for backwards compatibility — prefer using SAPObjectExtractor.extract() directly.
    """
    return _extractor.extract(content, file_type)


def _parse_abap_source_legacy(content: str, file_type: str) -> Dict[str, Any]:
    # A complete functional parser using basic regex rules for ABAP
    parsed_data = {
        "program_name": "",
        "description": "",
        "object_type": file_type,
        "classes": [],
        "methods": [],
        "function_modules": [],
        "interfaces": [],
        "forms": [],
        "events": [],
        "includes": [],
        "tables_used": [],
        "auth_objects": [],
        "function_calls": [],
        "select_options": [],
        "parameters": [],
        "data_declarations": [],
        "constants": [],
        "types": [],
        "enhancements": [],
        "smart_forms": [],
        "cds_views": [],
        "rap_objects": [],
        "messages": [],
        "exceptions_used": [],
        "perform_calls": [],
        "macros": [],
        "complexity_indicators": {
            "nested_loops": 0,
            "select_in_loop": 0,
            "select_star": 0,
            "hardcoded_values": 0
        }
    }
    
    # Program name
    report_match = re.search(r'^\s*(?:REPORT|PROGRAM)\s+(\w+)', content, re.IGNORECASE | re.MULTILINE)
    if report_match:
        parsed_data["program_name"] = report_match.group(1)
        
    # Includes
    includes = re.findall(r'^\s*INCLUDE\s+(\w+)\s*\.', content, re.IGNORECASE | re.MULTILINE)
    parsed_data["includes"] = includes
    
    # Tables used (simple match for TABLES and SELECT/UPDATE/DELETE/INSERT)
    tables_decl = re.findall(r'^\s*TABLES\s*:\s*([^.]+)\.', content, re.IGNORECASE | re.MULTILINE)
    for td in tables_decl:
        for tbl in td.split(','):
            parsed_data["tables_used"].append({"name": tbl.strip(), "operations": ["DECLARATION"]})
            
    selects = re.findall(r'\bSELECT\b.*?\bFROM\s+(\w+)', content, re.IGNORECASE | re.DOTALL)
    for sel in selects:
        parsed_data["tables_used"].append({"name": sel.strip(), "operations": ["SELECT"]})
        
    # Classes
    class_defs = re.finditer(r'^\s*CLASS\s+(\w+)\s+DEFINITION.*?^\s*ENDCLASS\.', content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    for cd in class_defs:
        parsed_data["classes"].append({"name": cd.group(1), "definition": cd.group(0), "methods": [], "interfaces": [], "attributes": []})
        
    # Methods
    methods = re.finditer(r'^\s*METHOD\s+(\w+).*?^\s*ENDMETHOD\.', content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    for m in methods:
        parsed_data["methods"].append({"name": m.group(1), "class": "unknown", "visibility": "public", "parameters": [], "return_type": "", "body": m.group(0)})
        
    # Function modules
    fms = re.finditer(r'^\s*FUNCTION\s+(\w+).*?^\s*ENDFUNCTION\.', content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    for fm in fms:
        parsed_data["function_modules"].append({"name": fm.group(1), "group": "", "importing": [], "exporting": [], "changing": [], "tables": [], "exceptions": [], "body": fm.group(0)})

    # Call functions
    calls = re.findall(r'^\s*CALL\s+FUNCTION\s+\'([^\']+)\'', content, re.IGNORECASE | re.MULTILINE)
    for call in calls:
        parsed_data["function_calls"].append({"name": call, "type": "CALL FUNCTION"})
        
    # Forms
    forms = re.finditer(r'^\s*FORM\s+(\w+).*?^\s*ENDFORM\.', content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    for f in forms:
        parsed_data["forms"].append({"name": f.group(1), "parameters": [], "body": f.group(0)})

    # Parameters & Select-options
    params = re.findall(r'^\s*PARAMETERS\s*:\s*([^.]+)\.', content, re.IGNORECASE | re.MULTILINE)
    for p in params:
        for param in p.split(','):
            parsed_data["parameters"].append({"name": param.strip().split()[0], "type": "", "default": "", "obligatory": False})

    # Complexity indicators
    parsed_data["complexity_indicators"]["select_star"] = len(re.findall(r'\bSELECT\s+\*\s+FROM\b', content, re.IGNORECASE))
    
    return parsed_data
