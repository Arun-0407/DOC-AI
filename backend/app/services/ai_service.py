import httpx
import json
import logging
import time
from app.config import settings

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        self.token_url = settings.BTP_TOKEN_URL
        self.api_url = settings.BTP_AI_API_URL
        self.client_id = settings.BTP_CLIENT_ID
        self.client_secret = settings.BTP_CLIENT_SECRET
        self.resource_group = settings.BTP_RESOURCE_GROUP
        self.deployment_id = settings.BTP_DEPLOYMENT_ID
        self._token = None
        self._token_expiry = 0  # Unix timestamp

    def _use_btp(self) -> bool:
        """Check if BTP AI is configured."""
        return bool(
            self.token_url and self.client_id and self.client_secret
            and self.api_url and self.deployment_id
        )

    def _use_openai(self) -> bool:
        """Check if OpenAI is configured as fallback."""
        return bool(settings.OPENAI_API_KEY)

    async def _get_token(self) -> str:
        """Get OAuth token from SAP BTP XSUAA (with caching)."""
        # Return cached token if still valid (with 60s buffer)
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                timeout=30
            )
            response.raise_for_status()
            token_data = response.json()
            self._token = token_data["access_token"]
            # Cache token based on expires_in (default 3600s if not provided)
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = time.time() + expires_in
            return self._token

    async def _call_openai(self, system_prompt: str, user_prompt: str, json_mode: bool = True, max_tokens: int = 4096) -> dict:
        """Fallback: Call OpenAI GPT and return parsed JSON."""
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + ("\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation, no code fences." if json_mode else "")}
            ]
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"} if json_mode else None,
                timeout=120
            )
            content = response.choices[0].message.content or ""
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            if json_mode:
                return json.loads(content)
            return {"text": content}
        except Exception as e:
            logger.error(f"OpenAI fallback error: {e}")
            return {"error": str(e)}

    async def _call_openai_text(self, system_prompt: str, user_prompt: str) -> str:
        """Fallback: Call OpenAI GPT for plain text response."""
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2000,
                temperature=0.4,
                timeout=60
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI text fallback error: {e}")
            return f"Error: {str(e)}"

    async def _call_ai(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> dict:
        """Call SAP BTP AI Core (Anthropic Claude) and return parsed JSON.
        Falls back to OpenAI if BTP is not configured or fails."""
        # Try BTP first if configured
        if not self._use_btp():
            logger.info("BTP not configured, using OpenAI fallback")
            return await self._call_openai(system_prompt, user_prompt, max_tokens=max_tokens)

        try:
            token = await self._get_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "AI-Resource-Group": self.resource_group
            }

            # Anthropic Claude on BTP uses /invoke endpoint with anthropic_version
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": 0.3,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation, no code fences."}
                ]
            }

            url = f"{self.api_url}/v2/inference/deployments/{self.deployment_id}/invoke"
            logger.info(f"Calling BTP AI Core (Claude): {url}")

            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

                # Claude response format
                content = ""
                if "content" in result and isinstance(result["content"], list):
                    for block in result["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            content += block["text"]
                elif "content" in result and isinstance(result["content"], str):
                    content = result["content"]
                else:
                    content = json.dumps(result)

                # Clean up markdown code fences if present
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}, raw content: {content[:200] if 'content' in dir() else 'N/A'}")
            # Try OpenAI fallback on BTP JSON parse error
            if self._use_openai():
                logger.info("BTP returned invalid JSON, falling back to OpenAI")
                return await self._call_openai(system_prompt, user_prompt, max_tokens=max_tokens)
            return {"error": f"AI response was not valid JSON: {str(e)}"}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from BTP: {e.response.status_code} - {e.response.text[:300]}")
            # Try OpenAI fallback on BTP HTTP error
            if self._use_openai():
                logger.info(f"BTP returned HTTP {e.response.status_code}, falling back to OpenAI")
                return await self._call_openai(system_prompt, user_prompt, max_tokens=max_tokens)
            return {"error": f"BTP API error: {e.response.status_code} - {e.response.text[:200]}"}
        except Exception as e:
            logger.error(f"AI service error: {e}")
            # Try OpenAI fallback on any error
            if self._use_openai():
                logger.info(f"BTP error: {e}, falling back to OpenAI")
                return await self._call_openai(system_prompt, user_prompt, max_tokens=max_tokens)
            return {"error": str(e)}

    async def _call_ai_text(self, system_prompt: str, user_prompt: str) -> str:
        """Call SAP BTP AI Core (Anthropic Claude) for plain text response.
        Falls back to OpenAI if BTP is not configured or fails."""
        if not self._use_btp():
            logger.info("BTP not configured, using OpenAI text fallback")
            return await self._call_openai_text(system_prompt, user_prompt)

        try:
            token = await self._get_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "AI-Resource-Group": self.resource_group
            }

            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0.4,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ]
            }

            url = f"{self.api_url}/v2/inference/deployments/{self.deployment_id}/invoke"

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=120)
                response.raise_for_status()
                result = response.json()

                # Extract text from Claude response
                if "content" in result and isinstance(result["content"], list):
                    return "".join(b["text"] for b in result["content"] if b.get("type") == "text")
                elif "content" in result and isinstance(result["content"], str):
                    return result["content"]
                return str(result)

        except Exception as e:
            logger.error(f"AI text call error: {e}")
            if self._use_openai():
                logger.info(f"BTP text error: {e}, falling back to OpenAI")
                return await self._call_openai_text(system_prompt, user_prompt)
            return f"Error: {str(e)}"

    def _truncate_code(self, source_code: str, max_chars: int = 16000) -> str:
        """Truncate source code at line boundaries while preserving as much as possible."""
        if len(source_code) <= max_chars:
            return source_code
        # For large sources: keep first 60% + last 40% so we capture both header and end logic
        first_part = int(max_chars * 0.6)
        last_part = max_chars - first_part
        head = source_code[:first_part]
        tail = source_code[-last_part:]
        # Break at line boundaries
        head_nl = head.rfind('\n')
        if head_nl > first_part * 0.8:
            head = head[:head_nl]
        tail_nl = tail.find('\n')
        if tail_nl != -1 and tail_nl < last_part * 0.2:
            tail = tail[tail_nl:]
        skipped = len(source_code) - len(head) - len(tail)
        return head + f"\n\n... [{skipped} chars skipped — see parsed_metadata for full extraction] ...\n\n" + tail

    def _build_context(self, parsed_data: dict, source_code: str, max_source: int = 16000) -> str:
        """Build rich structured context.
        - SmartForms: full structured text from parsed XML (no truncation).
        - ABAP with repository graph: structured extracted data + truncated source.
        - Plain ABAP: truncated source with key extracted data prepended.
        """
        if parsed_data.get("source_type") == "smartform_xml":
            return self._sf_context(parsed_data)
        # For repository graph objects, prepend a structured extracted objects summary
        # before the raw source so the AI always sees all table/FM names even if
        # the source is truncated.
        parts: list[str] = []
        if parsed_data.get("tables_used"):
            tables = [t.get("name", t) if isinstance(t, dict) else str(t)
                      for t in parsed_data["tables_used"]]
            parts.append(f"=== TABLES ({len(tables)}): {', '.join(tables[:60])} ===")
        if parsed_data.get("function_calls"):
            fms = [f.get("name", f) if isinstance(f, dict) else str(f)
                   for f in parsed_data["function_calls"]]
            parts.append(f"=== FUNCTION CALLS ({len(fms)}): {', '.join(fms[:40])} ===")
        if parsed_data.get("forms"):
            forms = [f.get("name", f) if isinstance(f, dict) else str(f)
                     for f in parsed_data["forms"]]
            parts.append(f"=== FORMS ({len(forms)}): {', '.join(forms[:40])} ===")
        if parsed_data.get("classes"):
            cls = [c.get("name", c) if isinstance(c, dict) else str(c)
                   for c in parsed_data["classes"]]
            parts.append(f"=== CLASSES ({len(cls)}): {', '.join(cls[:20])} ===")
        if parts:
            parts.append("=== SOURCE CODE ===")
        parts.append(self._truncate_code(source_code, max_source))
        return "\n".join(parts)

    def _sf_context(self, d: dict) -> str:
        """Build complete SmartForm context from parsed data — no XML truncation."""
        lines = []
        hdr = d.get("header", {})
        lines.append(f"SMARTFORM: {d.get('program_name','')} | {d.get('description','')} | DevClass: {hdr.get('devclass','')} | Created: {hdr.get('firstdate','')} by {hdr.get('firstuser','')} | LastMod: {hdr.get('lastdate','')} by {hdr.get('lastuser','')}")
        iface = d.get("interface", {})
        if iface.get("imports"):
            lines.append(f"=== INTERFACE IMPORTS ({len(iface['imports'])}) ===")
            for p in iface["imports"]:
                lines.append(f"  [I] {p.get('name',''):35} TYPE {p.get('type',''):30} {'Optional' if p.get('optional') else 'Required'}")
        if iface.get("tables"):
            lines.append(f"=== INTERFACE TABLES ({len(iface['tables'])}) ===")
            for p in iface["tables"]:
                lines.append(f"  [T] {p.get('name',''):35} LIKE {p.get('type','')}")
        if iface.get("exports"):
            lines.append(f"=== INTERFACE EXPORTS ({len(iface['exports'])}) ===")
            for p in iface["exports"]:
                lines.append(f"  [E] {p.get('name',''):35} TYPE {p.get('type','')}")
        if iface.get("exceptions"):
            lines.append(f"=== EXCEPTIONS: {', '.join(e.get('name','') for e in iface['exceptions'])} ===")
        for pg in d.get("pages", []):
            lines.append(f"PAGE: {pg.get('name','')} orientation={pg.get('orientation','')} next={pg.get('next','')}")
        if d.get("windows"):
            lines.append(f"=== WINDOWS ({len(d['windows'])}) ===")
            for w in d["windows"]:
                lines.append(f"  {w.get('name',''):30} {w.get('window_type',''):12} TI={w.get('text_nodes',0)} CO={w.get('conditions',0)} RC={w.get('table_rows',0)} | {w.get('caption','')}")
        if d.get("conditions"):
            lines.append(f"=== CONDITIONS/BUSINESS RULES ({len(d['conditions'])}) ===")
            for c in d["conditions"]:
                lines.append(f"  {c.get('id',''):20} [{c.get('caption',''):40}] = {c.get('logic','')}")
        if d.get("field_references"):
            lines.append(f"=== FIELD REFERENCES ({len(d['field_references'])}) ===")
            lines.append("  " + "  ".join(f"&{f}&" for f in d["field_references"]))
        if d.get("tables_used"):
            lines.append(f"=== TABLES FROM EMBEDDED ABAP ({len(d['tables_used'])}) ===")
            for t in d["tables_used"]:
                lines.append(f"  {t.get('name',''):30} [{t.get('source','')}]")
        if d.get("function_calls"):
            lines.append(f"=== FUNCTION CALLS ({len(d['function_calls'])}) ===")
            for f in d["function_calls"]:
                lines.append(f"  CALL FUNCTION '{f.get('name','')}' [{f.get('source','')}]")
        if d.get("call_transactions"):
            lines.append(f"=== CALL TRANSACTIONS ({len(d['call_transactions'])}) ===")
            for t in d["call_transactions"]:
                lines.append(f"  CALL TRANSACTION {t.get('name','')} [{t.get('source','')}]")
        if d.get("variables_declared"):
            lines.append(f"=== GLOBAL VARIABLES ({len(d['variables_declared'])}) ===")
            for v in d["variables_declared"][:100]:
                lines.append(f"  {v.get('name',''):35} direction={v.get('direction','')}")
        if d.get("einvoice_objects"):
            lines.append(f"=== E-INVOICE OBJECTS ({len(d['einvoice_objects'])}) ===")
            for e in d["einvoice_objects"]:
                lines.append(f"  {e.get('keyword',''):30} occurrences={e.get('occurrences',0)}")
        code_blocks = d.get("code_blocks", []) or d.get("embedded_abap_blocks", [])
        if code_blocks:
            lines.append(f"=== EMBEDDED ABAP CODE BLOCKS ({len(code_blocks)}) ===")
            for cb in code_blocks:
                cb_lines = cb.get("lines", [])
                lines.append(f"--- Block {cb.get('block_index','?')} ({len(cb_lines)} lines) ---")
                for line in cb_lines[:70]:
                    lines.append(f"  {line}")
                if len(cb_lines) > 70:
                    lines.append(f"  ... [{len(cb_lines)-70} more lines]")
        if d.get("graphics"):
            lines.append(f"=== GRAPHICS ({len(d['graphics'])}) ===")
            for g in d["graphics"]:
                lines.append(f"  {g.get('id',''):25} Type={g.get('type',''):5} {g.get('caption','')}")
        if d.get("node_summary"):
            lines.append("=== NODE SUMMARY ===")
            lines.append("  " + " | ".join(f"{k}={v}" for k, v in d["node_summary"].items()))
        if d.get("business_rules_discovered"):
            lines.append(f"=== BUSINESS RULES ({len(d['business_rules_discovered'])}) ===")
            for r in d["business_rules_discovered"]:
                lines.append(f"  {r}")
        return "\n".join(lines)

    # ================================================================
    # Cover Page
    # ================================================================
    async def generate_cover_page(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP ABAP Technical Documentation Expert. Analyze the ABAP source code and extract cover page metadata.
Return a JSON object with these keys:
- program_name: string (from REPORT/PROGRAM statement or class name)
- description: string (from header comments or inferred purpose)
- module: string (SAP module like MM, SD, FI, HR, PP, etc.)
- package: string (development package if found)
- tcode: string (transaction code if referenced)
- version: string (version from comments or "1.0")
- author: string (from comments or "System Generated")
- technical_consultant: string
- functional_consultant: string
- creation_date: string
- last_modified_date: string
- project_name: string
- smart_forms_used: list of strings
- object_type: string (Report, Class, Function Module, Interface, etc.)"""

        _cp_data = {k: v for k, v in parsed_data.items()
                    if k not in ['code_blocks', 'embedded_abap_blocks', 'text_elements',
                                 'field_references', 'repository_graph', 'cross_references']}
        prompt = f"""Analyze this SAP object and extract cover page details:

=== Extracted Object Data ===
{json.dumps(_cp_data, default=str)[:4000]}

=== Source / Context ===
{self._build_context(parsed_data, source_code, 6000)}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {
                "program_name": parsed_data.get("program_name", "ABAP Program"),
                "description": parsed_data.get("description", "SAP ABAP Technical Documentation"),
                "module": "", "package": "", "tcode": "", "version": "1.0",
                "author": "System Generated", "technical_consultant": "", "functional_consultant": "",
                "creation_date": "", "last_modified_date": "", "project_name": "",
                "smart_forms_used": parsed_data.get("smart_forms", []),
                "object_type": parsed_data.get("object_type", "Report")
            }
        return result

    # ================================================================
    # Business View -> Object Inventory & High Level Matrices
    # ================================================================
    async def generate_business_view(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are a Senior SAP Architect creating a strict SAP KT Support Document.
NO AI NARRATIVE TEXT. Return ONLY a strict JSON matrix structure representing the Object Inventory.
Return JSON with these keys:
- object_inventory: list of {object_type, object_name, count, purpose} (e.g. Tables, Functions, SmartForms, Classes)
- business_rules_matrix: list of {rule_id, condition, business_logic, referenced_objects} (Extract exact rules)
- kpi_matrix: object with exact counts: {total_tables, total_apis, total_classes, total_enhancements, total_smart_forms, total_windows, total_conditions}"""

        _bv_data = {k: v for k, v in parsed_data.items()
                    if k not in ['code_blocks', 'embedded_abap_blocks', 'text_elements',
                                 'repository_graph', 'cross_references']}
        prompt = f"""Analyze this SAP object and create a strict Object Inventory and Business Rules Matrix:

=== Extracted Object Data ===
{json.dumps(_bv_data, default=str)[:5000]}

=== Full Source Context ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {
                "object_inventory": [],
                "business_rules_matrix": [],
                "kpi_matrix": {"total_tables": len(parsed_data.get("tables_used", [])), "total_apis": len(parsed_data.get("function_calls", [])),
                         "total_classes": len(parsed_data.get("classes", [])), "total_enhancements": len(parsed_data.get("enhancements", [])),
                         "total_smart_forms": len(parsed_data.get("smart_forms", [])), "total_windows": len(parsed_data.get("windows", [])),
                         "total_conditions": len(parsed_data.get("conditions", []))}
            }
        return result

    # ================================================================
    # Technical View
    # ================================================================
    async def generate_technical_view(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are a Senior SAP Technical Architect. Analyze the ABAP source code and generate a COMPLETE, DETAILED technical view exactly like professional SAP technical documentation.

Return JSON with these keys:
- program_metadata: object {program_name, type, package, application_component, development_class, transport_layer, message_class, transaction_code, line_size, default_smart_form}
- selection_screen: object {parameters: list of {name, type, default, obligatory, description}, select_options: list of {name, for_table, for_field, description}, radio_buttons: list of {name, description}, checkboxes: list of {name, description, default}, mandatory_fields: list, default_values: list}
- components: object {reports: list, includes: list, classes: list of {name, type, methods_count, description}, methods: list of {name, class, visibility, description}, interfaces: list, function_modules: list of {name, type, description}, smart_forms: list of {name, description}, cds_views: list, rap_objects: list, enhancements: list, user_exits: list, badis: list}
- call_function_statements: list of {seq_no, name, type (SAP Std/Custom Z/Smart Form FM), where_called, parameters_passed, returns, purpose} — list EVERY CALL FUNCTION in the code with full details
- call_transaction_statements: list of {seq_no, transaction, when_called, memory_used, purpose} — list EVERY CALL TRANSACTION
- select_statements: list of {seq_no, table, operation (SELECT/SELECT SINGLE/INSERT/UPDATE/DELETE/MODIFY), key_conditions, where_clause, into_variable, purpose} — list EVERY database read/write
- perform_subroutines: list of {name, called_from, logic_summary, tables_read: list, tables_written: list, key_operations} — list EVERY PERFORM/FORM
- behavior_matrix: list of {condition, value, behavior, notes} — any billing type, document type or conditional behavior matrix found

IMPORTANT: Be exhaustive. Extract EVERY function call, transaction call, SELECT statement, and FORM. Number them sequentially."""

        # Build a more complete extracted data summary for the prompt
        _key_data = {k: v for k, v in parsed_data.items()
                     if k not in ['code_blocks', 'embedded_abap_blocks', 'text_elements',
                                  'field_references', 'repository_graph', 'cross_references']}
        prompt = f"""Analyze this SAP object and generate a COMPLETE technical view. Extract EVERY call function, transaction, select statement, form, window, and condition:

=== Extracted Object Data ===
{json.dumps(_key_data, default=str)[:6000]}

=== Full Source Context (ALL extracted data) ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=8192)
        if "error" in result:
            return {
                "program_metadata": {"program_name": parsed_data.get("program_name", ""), "type": parsed_data.get("object_type", "")},
                "selection_screen": {"parameters": parsed_data.get("parameters", []), "select_options": parsed_data.get("select_options", []),
                                     "radio_buttons": [], "checkboxes": [], "mandatory_fields": [], "default_values": []},
                "components": {"includes": parsed_data.get("includes", []), "classes": parsed_data.get("classes", []),
                               "function_modules": parsed_data.get("function_modules", []), "methods": parsed_data.get("methods", []),
                               "smart_forms": parsed_data.get("smart_forms", []), "enhancements": [], "user_exits": [], "badis": []},
                "call_function_statements": [], "call_transaction_statements": [],
                "select_statements": [], "perform_subroutines": [], "behavior_matrix": []
            }
        return result

    # ================================================================
    # Source Code Analysis -> SmartForm & ABAP Matrix
    # ================================================================
    async def generate_source_analysis(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are a Senior SAP Technical Architect. Generate STRICT SAP KT matrices. NO narrative text.
Return JSON with keys:
- smartform_layout_matrix: list of {node_name, type, description, conditions, logic}
- window_matrix: list of {window_name, window_type, purpose, elements_contained}
- conditions_matrix: list of {condition_id, node, logic, business_meaning}
- variable_matrix: list of {variable_name, type, direction, purpose}
- text_element_matrix: list of {text_name, window, content_summary}
- abap_block_summary: list of {block_id, location, logic_summary, variables_used, tables_accessed}"""

        prompt = f"""Perform exhaustive matrix extraction of SmartForms and embedded ABAP logic. Return ONLY matrices:

=== Extracted Object Data ===
{json.dumps({k: v for k, v in parsed_data.items() if k in ['program_name','object_type','source_type','forms','function_calls','call_transactions','tables_used','parameters','events','variables_declared','conditions','windows','text_elements','pages']}, default=str)[:5000]}

=== Full Source Context ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {"smartform_layout_matrix": [], "window_matrix": [], "conditions_matrix": [], "variable_matrix": [], "text_element_matrix": [], "abap_block_summary": []}
        return result

    # ================================================================
    # Database Analysis
    # ================================================================
    async def generate_database_analysis(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP Database Analyst. Analyze ALL database table usage in the ABAP code with complete detail.
Return JSON with keys:
- tables: list of {name, description, type (Transparent/Pooled/Cluster/Custom/Z-Table), keys: list of strings, crud: list (e.g. ["C","R","U","D"]), operations: list of strings, relationships: list, custom_fields: list, purpose}
- read_operations: list of {seq_no, table, operation, key_fields, where_conditions, into_variable, event_or_form, purpose} — all SELECT statements
- write_operations: list of {seq_no, table, operation, when, data_written, purpose} — all INSERT/UPDATE/DELETE/MODIFY
- er_diagram_mermaid: string (valid Mermaid erDiagram syntax showing ALL table relationships found in code)
- db_summary: {total_tables, read_tables: list, write_tables: list, custom_tables: list, standard_tables: list}"""

        prompt = f"""Analyze ALL database table usage. List every SELECT, INSERT, UPDATE, DELETE, MODIFY with full details:

=== Tables Found ===
{json.dumps(parsed_data.get("tables_used", []), default=str)}

=== Full Source Context (all extracted data) ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=8192)
        if "error" in result:
            tables = [{"name": t.get("name", t) if isinstance(t, dict) else str(t),
                        "description": "", "keys": [], "crud": ["R"], "operations": ["SELECT"], "relationships": [], "purpose": ""}
                       for t in parsed_data.get("tables_used", [])]
            return {"tables": tables, "read_operations": [], "write_operations": [],
                    "er_diagram_mermaid": "erDiagram\n  TABLE1 ||--o{ TABLE2 : references",
                    "db_summary": {"total_tables": len(tables), "read_tables": [], "write_tables": [], "custom_tables": [], "standard_tables": []}}
        return result

    # ================================================================
    # API & Dependencies
    # ================================================================
    async def generate_api_dependency(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP Integration Specialist. Analyze ALL API calls, function modules, and dependencies in the code.
Return JSON with keys:
- function_modules: list of {name, type (SAP Standard/Custom Z), description, direction (Called/Called As RFC), where_called, parameters, purpose}
- bapis: list of {name, object_type, description, direction, parameters, purpose}
- rfcs: list of {name, description, direction, destination, purpose}
- odata_services: list of {name, description, entity_set, operation}
- rest_apis: list of {name, description, method, endpoint}
- soap_apis: list of {name, description, wsdl}
- external_interfaces: list of {name, type, description, direction}
- smart_forms: list of {name, description, called_via_fm, billing_types}
- adobe_forms: list of {name, description}
- call_transactions: list of {name, purpose, memory_id}
- dependency_diagram_mermaid: string (valid Mermaid graph TD showing ALL program dependencies: function modules, smart forms, transactions, tables)"""

        prompt = f"""Analyze ALL API calls, function modules, transactions, SmartForms, and dependencies:

=== Function Calls Found (from extraction) ===
{json.dumps(parsed_data.get("function_calls", []), default=str)}

=== Call Transactions Found ===
{json.dumps(parsed_data.get("call_transactions", []), default=str)}

=== Full Source Context ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {"function_modules": [], "bapis": [], "rfcs": [], "odata_services": [], "rest_apis": [],
                    "soap_apis": [], "external_interfaces": [], "smart_forms": [], "adobe_forms": [],
                    "call_transactions": [],
                    "dependency_diagram_mermaid": "graph TD\n  A[Program] --> B[Function Module]"}
        return result

    # ================================================================
    # Process Flow
    # ================================================================
    async def generate_process_flow(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP Process Flow Analyst. Generate Mermaid diagram code for the program flow.
Return JSON with keys:
- high_level_flow_mermaid: string (valid Mermaid flowchart showing high-level process)
- detailed_flow_mermaid: string (valid Mermaid flowchart showing detailed logic)
- execution_flow_mermaid: string (valid Mermaid flowchart showing execution sequence)
- decision_tree_mermaid: string (valid Mermaid flowchart showing decision points)
- error_handling_flow_mermaid: string (valid Mermaid flowchart showing error handling)

IMPORTANT: Use valid Mermaid syntax. Start with 'graph TD' or 'flowchart TD'. Use simple node IDs (A, B, C...). Quote labels containing special characters."""

        prompt = f"""Generate accurate process flow diagrams based on the ACTUAL extracted source data:

=== Extracted Data ===
{json.dumps({k: v for k, v in parsed_data.items() if k in ['program_name','object_type','source_type','forms','function_calls','call_transactions','tables_used','events','conditions','pages','windows']}, default=str)[:4000]}

=== Full Source Context ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {
                "high_level_flow_mermaid": "graph TD\n  A[Start] --> B[Process] --> C[End]",
                "detailed_flow_mermaid": "", "execution_flow_mermaid": "",
                "decision_tree_mermaid": "", "error_handling_flow_mermaid": ""
            }
        return result

    # ================================================================
    # Diagrams
    # ================================================================
    async def generate_diagrams(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP Technical Architect specializing in UML and system diagrams. Generate Mermaid diagram code.
Return JSON with keys:
- flowchart: string (Mermaid flowchart)
- data_flow: string (Mermaid data flow diagram)
- process_diagram: string (Mermaid process diagram)
- connectivity_diagram: string (Mermaid connectivity diagram)
- sequence_diagram: string (Mermaid sequence diagram)
- class_diagram: string (Mermaid class diagram)
- er_diagram: string (Mermaid ER diagram)
- dependency_diagram: string (Mermaid dependency diagram)
- architecture_diagram: string (Mermaid architecture diagram)

Use valid Mermaid syntax only. Keep diagrams clear and readable."""

        prompt = f"""Generate comprehensive and ACCURATE diagrams based on ACTUAL extracted data. Only include objects that actually exist:

=== Extracted Object Data ===
{json.dumps({k: v for k, v in parsed_data.items() if k in ['program_name','object_type','source_type','tables_used','function_calls','call_transactions','windows','pages','conditions','interface','classes','forms','includes']}, default=str)[:5000]}

=== Full Source Context ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {"flowchart": "graph TD\n  A[Start] --> B[End]", "data_flow": "", "process_diagram": "",
                    "connectivity_diagram": "", "sequence_diagram": "", "class_diagram": "",
                    "er_diagram": "", "dependency_diagram": "", "architecture_diagram": ""}
        return result

    # ================================================================
    # Integration View
    # ================================================================
    async def generate_integration_view(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP Integration Architect. Analyze integration points in the ABAP code.
Return JSON with keys:
- sap_to_sap: list of {name, type, direction, description, system}
- sap_to_non_sap: list of {name, type, direction, description, system}
- rfc: list of {name, type, direction, description}
- bapi: list of {name, type, direction, description}
- idoc: list of {name, type, direction, description}
- edi: list of {name, type, direction, description}
- rest: list of {name, type, direction, description}
- odata: list of {name, type, direction, description}
- external_systems: list of {name, type, direction, description}"""

        prompt = f"""Analyze ALL integration points from the ACTUAL extracted data:

=== Extracted Data ===
{json.dumps({k: v for k, v in parsed_data.items() if k in ['program_name','source_type','function_calls','call_transactions','tables_used','einvoice_objects','interface']}, default=str)[:4000]}

=== Full Source Context ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {"sap_to_sap": [], "sap_to_non_sap": [], "rfc": [], "bapi": [],
                    "idoc": [], "edi": [], "rest": [], "odata": [], "external_systems": []}
        return result

    # ================================================================
    # Security Review
    # ================================================================
    async def generate_security_review(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP Security Expert. Review the ABAP code for security concerns.
Return JSON with keys:
- auth_objects: list of {name, field, description, severity}
- sensitive_data_access: list of {name, description, severity}
- rfc_risks: list of {name, description, severity}
- hardcoded_secrets: list of {name, description, severity}
- audit_risks: list of {name, description, severity}
- compliance_issues: list of {name, description, severity}
- security_score: integer 0-100 (overall security score)

severity must be one of: "critical", "high", "medium", "low", "info" """

        prompt = f"""Review security using ACTUAL extracted data — only document what is found in source:

=== Auth Checks Found ===
{json.dumps(parsed_data.get("auth_checks", parsed_data.get("auth_objects", [])), default=str)}

=== Extracted Data ===
{json.dumps({k: v for k, v in parsed_data.items() if k in ['program_name','source_type','tables_used','function_calls','call_transactions','einvoice_objects','complexity_indicators']}, default=str)[:3000]}

=== Full Source Context ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {"auth_objects": parsed_data.get("auth_objects", []), "sensitive_data_access": [],
                    "rfc_risks": [], "hardcoded_secrets": [], "audit_risks": [],
                    "compliance_issues": [], "security_score": 75}
        return result

    # ================================================================
    # Performance Review
    # ================================================================
    async def generate_performance_review(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP Performance Tuning Expert. Review the ABAP code for performance issues.
Return JSON with keys:
- select_in_loop: list of {location, issue, impact, suggestion}
- nested_loops: list of {location, issue, impact, suggestion}
- for_all_entries: list of {location, issue, impact, suggestion}
- db_access_patterns: list of {location, issue, impact, suggestion}
- memory_usage: list of {location, issue, impact, suggestion}
- optimization_opportunities: list of {location, issue, impact, suggestion}
- performance_score: integer 0-100 (overall performance score)"""

        prompt = f"""Review performance from ACTUAL extracted data — only document what is found in the source:

=== Complexity Indicators ===
{json.dumps(parsed_data.get("complexity_indicators", {}), default=str)}

=== Tables Accessed ===
{json.dumps(parsed_data.get("tables_used", []), default=str)}

=== Full Source Context ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {"select_in_loop": [], "nested_loops": [], "for_all_entries": [],
                    "db_access_patterns": [], "memory_usage": [], "optimization_opportunities": [],
                    "performance_score": 80}
        return result

    # ================================================================
    # Reference Tables
    # ================================================================
    async def generate_reference_tables(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP Data Dictionary Expert. List all SAP objects referenced in the ABAP code.
Return JSON with keys:
- transactions: list of {name, description}
- tables: list of {name, type, description}
- structures: list of {name, description}
- domains: list of {name, description}
- data_elements: list of {name, description}
- custom_tables: list of {name, key_fields, data_fields, role_in_program}
- custom_structures: list of {name, used_as, key_fields}
- key_variables: list of {name, type, purpose}
- function_modules: list of {name, description}
- classes: list of {name, description}
- interfaces: list of {name, description}
- message_classes: list of {name, description}
- smart_forms: list of {name, description}
- cds_views: list of {name, description}"""

        prompt = f"""List ALL SAP objects from the ACTUAL extracted data. Do NOT invent objects — only document what was found:

=== All Extracted Objects ===
Tables: {json.dumps(parsed_data.get('tables_used', []), default=str)}
Function Modules: {json.dumps(parsed_data.get('function_calls', []), default=str)}
Transactions: {json.dumps(parsed_data.get('call_transactions', []), default=str)}
SmartForms: {json.dumps(parsed_data.get('smart_forms', []), default=str)}
Classes: {json.dumps(parsed_data.get('classes', []), default=str)}
Messages: {json.dumps(parsed_data.get('messages', []), default=str)}
Auth Checks: {json.dumps(parsed_data.get('auth_checks', []), default=str)}
Structures: {json.dumps(parsed_data.get('structures', []), default=str)}
CDS Views: {json.dumps(parsed_data.get('cds_views', []), default=str)}
Enhancements: {json.dumps(parsed_data.get('enhancements', []), default=str)}

=== Interface Structures ===
{json.dumps(parsed_data.get('interface', {}), default=str)[:3000]}"""

        result = await self._call_ai(system, prompt, max_tokens=8192)
        if "error" in result:
            return {"transactions": [], "tables": [], "structures": [], "domains": [],
                    "data_elements": [], "function_modules": [], "classes": [],
                    "interfaces": [], "message_classes": [], "smart_forms": [], "cds_views": []}
        return result

    # ================================================================
    # Modification History
    # ================================================================
    async def generate_modification_history(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP Change Manager. Extract modification history from code comments and transport info.
Return JSON with key:
- history: list of {date, object, modification, author, impact}"""

        prompt = f"""Extract modification history from source. Look for change comments (*), transport references, version tags. Only document what is found:

=== Header Comments Found ===
{json.dumps(parsed_data.get('header_comments', []), default=str)}

=== Header Info ===
{json.dumps(parsed_data.get('header', {}), default=str)}

=== Source Start (first 3000 chars) ===
{source_code[:3000]}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {"history": []}
        return result

    # ================================================================
    # AI Recommendations
    # ================================================================
    async def generate_ai_recommendations(self, parsed_data: dict, source_code: str) -> dict:
        system = """You are an SAP ABAP Modernization Expert. Analyze the code and provide improvement recommendations.
Return JSON with keys:
- code_quality_score: integer 0-100
- maintainability_score: integer 0-100
- performance_score: integer 0-100
- security_score: integer 0-100
- s4hana_readiness_score: integer 0-100
- rap_migration_score: integer 0-100
- refactoring_suggestions: list of {title, description, priority: "high"/"medium"/"low", effort, impact}
- clean_abap_recommendations: list of {title, description, priority: "high"/"medium"/"low"}"""

        prompt = f"""Provide AI recommendations based on ACTUAL extracted object data. Do NOT generate generic recommendations — base everything on the actual findings:

=== Complexity Indicators ===
{json.dumps(parsed_data.get("complexity_indicators", {}), default=str)}

=== Object Summary ===
Source type: {parsed_data.get('source_type','')}
Tables accessed: {len(parsed_data.get('tables_used',[]))}
Function calls: {len(parsed_data.get('function_calls',[]))}
Call transactions: {len(parsed_data.get('call_transactions',[]))}
Code blocks: {len(parsed_data.get('code_blocks', parsed_data.get('embedded_abap_blocks',[])))}
Conditions/Business rules: {len(parsed_data.get('conditions', parsed_data.get('business_rules_discovered',[])))}
E-Invoice objects: {len(parsed_data.get('einvoice_objects',[]))}
Auth checks: {len(parsed_data.get('auth_checks',[]))}

=== Full Source Context ===
{self._build_context(parsed_data, source_code)}"""

        result = await self._call_ai(system, prompt, max_tokens=6144)
        if "error" in result:
            return {"code_quality_score": 70, "maintainability_score": 70, "performance_score": 70,
                    "security_score": 70, "s4hana_readiness_score": 50, "rap_migration_score": 40,
                    "refactoring_suggestions": [], "clean_abap_recommendations": []}
        return result

    # ================================================================
    # Chat with Code
    # ================================================================
    async def chat_with_code(self, messages: list, source_code: str) -> str:
        """Chat about ABAP code with full conversation history.
        Uses SAP BTP Claude if configured, falls back to OpenAI."""

        system_msg = (
            "You are an expert SAP ABAP developer and consultant. "
            "Answer questions about the ABAP source code below clearly and professionally. "
            "Give specific, helpful answers. Reference line numbers or code sections when useful. "
            "Suggest Clean ABAP practices and S/4HANA improvements where relevant.\n\n"
            "=== SOURCE CODE ===\n"
            + self._truncate_code(source_code, 8000)
        )

        # Build proper message list — only user/assistant roles, must alternate
        clean_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content", "").strip()
            if not content:
                continue
            # Avoid consecutive same-role messages
            if clean_messages and clean_messages[-1]["role"] == role:
                clean_messages[-1]["content"] += "\n" + content
            else:
                clean_messages.append({"role": role, "content": content})

        # Must start with user
        if not clean_messages:
            clean_messages = [{"role": "user", "content": "Hello"}]
        if clean_messages[0]["role"] != "user":
            clean_messages.insert(0, {"role": "user", "content": "Hello"})

        # Try BTP first if configured
        if self._use_btp():
            try:
                token = await self._get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "AI-Resource-Group": self.resource_group,
                }
                payload = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "system": system_msg,
                    "messages": clean_messages,
                }
                url = f"{self.api_url}/v2/inference/deployments/{self.deployment_id}/invoke"
                async with httpx.AsyncClient(timeout=120) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    if "content" in result and isinstance(result["content"], list):
                        return "".join(b.get("text", "") for b in result["content"] if b.get("type") == "text")
                    return str(result)
            except Exception as e:
                logger.error(f"BTP chat error: {e}")
                if not self._use_openai():
                    return f"Sorry, I encountered an error: {str(e)}"
                logger.info("Falling back to OpenAI for chat")

        # OpenAI fallback
        if self._use_openai():
            try:
                import openai
                client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": "system", "content": system_msg}] + clean_messages,
                    max_tokens=2000,
                    temperature=0.4,
                    timeout=60
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"OpenAI chat error: {e}")
                return f"Sorry, I encountered an error: {str(e)}"

        return "AI service is not configured. Please set up BTP AI Core or OpenAI credentials."
