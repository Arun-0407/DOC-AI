"""
SAP Object Extraction Engine - Production Grade.
Extracts ALL SAP objects from ABAP source and SmartForm XML.
Zero hardcoded business logic - purely structural extraction from actual source content.
"""
import re
from collections import Counter
import logging
logger = logging.getLogger(__name__)


class SAPObjectExtractor:
    """Production-grade extractor for ABAP source and SmartForm XML."""

    def extract(self, content, file_type="", filename=""):
        """Auto-detect type and extract all SAP objects."""
        is_sf = "<sf:SMARTFORM" in content or ("SMARTFORM" in content.upper() and content.strip().startswith("<?xml"))
        is_xml = content.strip().startswith("<?xml") or (content.strip().startswith("<") and len(content) > 100)
        if is_sf:
            d = self._sf(content)
            emb = self._abap_from_xml(content)
            for key in ["function_calls","call_transactions","tables_used","perform_calls","auth_checks","messages"]:
                seen = {str(x) for x in d.get(key,[])}
                for item in emb.get(key,[]):
                    if str(item) not in seen: d.setdefault(key,[]).append(item); seen.add(str(item))
            d["embedded_abap_blocks"] = emb.get("code_blocks",[])
            d["source_type"] = "smartform_xml"
        elif is_xml:
            d = self._extract_generic_xml(content, filename); d["source_type"] = "xml_object"
        else:
            d = self._abap(content); d["source_type"] = "abap_source"
        d["filename"] = filename; d["file_size_chars"] = len(content)
        d['cross_references'] = self.build_cross_reference(d)
        return d

    def _rx(self, pat, text, default="", flags=0):
        m = re.search(pat, text, re.DOTALL | flags)
        return m.group(1).strip() if m else default

    def _clean(self, s):
        return s.replace("&apos;","'").replace('&quot;','"').replace("&amp;","&").replace("&lt;","<").replace("&gt;",">").strip()

    def build_cross_reference(self, d: dict) -> list:
        """Build cross-reference matrix: which table is used in which code block/form."""
        xref = []
        for i, cb in enumerate(d.get('code_blocks', [])):
            txt = '\n'.join(cb.get('lines', []))
            for t in d.get('tables_used', []):
                tname = t.get('name', '') if isinstance(t, dict) else str(t)
                if tname and tname in txt.upper():
                    xref.append({'table': tname, 'used_in': f'Code Block {cb.get("block_index", i+1)}', 'context': 'embedded_abap'})
        for form in d.get('forms', []):
            fname = form.get('name', '')
            for t in form.get('tables_accessed', []):
                xref.append({'table': t, 'used_in': f'FORM {fname}', 'context': 'subroutine'})
        return xref

    def _sf(self, c):
        d = {
            "object_type":"smart_form","program_name":"","description":"","header":{},
            "interface":{"imports":[],"exports":[],"tables":[],"exceptions":[]},
            "pages":[],"windows":[],"conditions":[],"text_elements":[],
            "field_references":[],"code_blocks":[],"graphics":[],
            "node_summary":{},"tables_used":[],"function_calls":[],
            "call_transactions":[],"perform_calls":[],"auth_checks":[],
            "messages":[],"variables_declared":[],"einvoice_objects":[],
            "business_rules_discovered":[],
        }
        hkeys = ["formname","caption","devclass","version","firstuser","firstdate","lastuser","lastdate","masterlang"]
        d["header"] = {k:self._rx(f"<{k.upper()}>(.*?)</{k.upper()}>",c) for k in hkeys}
        d["program_name"] = d["header"].get("formname","")
        d["description"] = d["header"].get("caption","")
        ib = re.search(r"<INTERFACE>(.*?)</INTERFACE>",c,re.DOTALL)
        if ib:
            for item in re.findall(r"<item>(.*?)</item>",ib.group(1),re.DOTALL):
                io=self._rx(r"<IOTYPE>(.*?)</IOTYPE>",item)
                name=self._rx(r"<NAME>(.*?)</NAME>",item)
                typename=self._rx(r"<TYPENAME>(.*?)</TYPENAME>",item)
                optional="<OPTIONAL>X</OPTIONAL>" in item
                p={"name":name,"type":typename,"optional":optional}
                if io=="I": d["interface"]["imports"].append(p)
                elif io=="E": d["interface"]["exports"].append(p)
                elif io=="T": d["interface"]["tables"].append(p)
                elif io=="X": d["interface"]["exceptions"].append({"name":name})
        nt_map={"TI":"Text","WI":"Window","SE":"Section","RC":"Table_Row","CO":"Condition","EV":"Event","PA":"Page","CD":"Program_Lines","RP":"Template","GR":"Graphic","CM":"Complex"}
        d["node_summary"]={nt_map.get(k,k):v for k,v in Counter(re.findall(r"<NODETYPE>(.*?)</NODETYPE>",c)).items()}
        for pb in re.findall(r"<sf:PAGE>(.*?)</sf:PAGE>",c,re.DOTALL):
            d["pages"].append({"name":self._rx(r"<INAME>(.*?)</INAME>",pb),"caption":self._rx(r"<CAPTION>(.*?)</CAPTION>",pb),"next":self._rx(r"<NEXTPAGE>.*?<INAME>(.*?)</INAME>",pb,flags=re.DOTALL),"orientation":self._rx(r"<PAGEORTN>(.*?)</PAGEORTN>",pb)})
        for wb in re.findall(r"<sf:WINDOW[^>]*>(.*?)</sf:WINDOW>",c,re.DOTALL):
            wt=self._rx(r"<WTYPE>(.*?)</WTYPE>",wb,"T")
            d["windows"].append({"name":self._rx(r"<INAME>(.*?)</INAME>",wb),"caption":self._rx(r"<CAPTION>(.*?)</CAPTION>",wb),"window_type":"Main" if wt=="M" else "Secondary","text_nodes":wb.count("<NODETYPE>TI</NODETYPE>"),"conditions":wb.count("<NODETYPE>CO</NODETYPE>"),"table_rows":wb.count("<NODETYPE>RC</NODETYPE>")})
        for cb in re.findall(r"<sf:CONDITION>(.*?)</sf:CONDITION>",c,re.DOTALL):
            name=self._rx(r"<INAME>(.*?)</INAME>",cb); caption=self._rx(r"<CAPTION>(.*?)</CAPTION>",cb)
            cond_block=re.search(r"<COND>(.*?)</COND>",cb,re.DOTALL)
            parts=[]
            if cond_block:
                for cop,op1,op2 in re.findall(r"<COP>(.*?)</COP>.*?<OP1>(.*?)</OP1>.*?<OP2>(.*?)</OP2>",cond_block.group(1),re.DOTALL):
                    parts.append(f"{op1} {cop} {self._clean(op2)}")
            logic=" AND ".join(parts) if parts else "TRUE"
            d["conditions"].append({"id":name,"caption":caption,"logic":logic})
            if parts: d["business_rules_discovered"].append(f"IF {logic} THEN show/hide [{caption}]")
        field_refs=set()
        for tb in re.findall(r"<sf:TEXT>(.*?)</sf:TEXT>",c,re.DOTALL):
            name=self._rx(r"<INAME>(.*?)</INAME>",tb); caption=self._rx(r"<CAPTION>(.*?)</CAPTION>",tb)
            text=self._clean(" | ".join(re.findall(r"<TDLINE>(.*?)</TDLINE>",tb)))
            for raw in re.findall(r"&amp;([^&;]+)&amp;",tb): field_refs.add(raw.strip())
            for raw in re.findall(r"&([a-zA-Z][a-zA-Z0-9_.-]+)&",tb): field_refs.add(raw.strip())
            d["text_elements"].append({"id":name,"caption":caption,"content":text[:200]})
        d["field_references"]=sorted(list(field_refs))
        for idx,cb in enumerate(re.findall(r"<CODE>(.*?)</CODE>",c,re.DOTALL)):
            items=re.findall(r"<item>(.*?)</item>",cb,re.DOTALL)
            code_lines=[self._clean(i) for i in items if i.strip()]
            if code_lines:
                d["code_blocks"].append({"block_index":idx+1,"lines":code_lines,"line_count":len(code_lines)})
                txt2="\n".join(code_lines)
                for t in re.findall(r"(?:FROM|INSERT INTO|UPDATE|MODIFY)\s+(\w+)",txt2,re.IGNORECASE):
                    t=t.upper()
                    if len(t)>2 and t not in {"INITIAL","TABLE","LINE","LINES","SCREEN"}:
                        if not any(x.get("name")==t for x in d["tables_used"]):
                            d["tables_used"].append({"name":t,"source":"embedded_abap"})
                for sel_match in re.findall(r'SELECT\s+(SINGLE\s+)?(?:\*|\w[\w\s,]+?)\s+FROM\s+(\w+)(?:\s+(?:INTO|WHERE)\s+(.+?))?(?:\.)', txt2, re.IGNORECASE):
                    single = 'SINGLE' if sel_match[0].strip() else ''
                    table_name = sel_match[1].upper()
                    rest = sel_match[2].strip() if sel_match[2] else ''
                    d.setdefault('select_statements', []).append({
                        'table': table_name,
                        'operation': f'SELECT {single}'.strip(),
                        'details': rest[:100],
                        'source': 'embedded_abap'
                    })
                for fm in re.findall(r"CALL FUNCTION\\s+'([^']+)'",txt2,re.IGNORECASE):
                    if not any(x.get("name")==fm for x in d["function_calls"]):
                        d["function_calls"].append({"name":fm,"source":"embedded_abap"})
                for tx in re.findall(r"CALL TRANSACTION\\s+'?(\\w+)'?",txt2,re.IGNORECASE):
                    if not any(x.get("name")==tx.upper() for x in d["call_transactions"]):
                        d["call_transactions"].append({"name":tx.upper(),"source":"embedded_abap"})
        for gb in re.findall(r"<sf:GRAPHIC>(.*?)</sf:GRAPHIC>",c,re.DOTALL):
            d["graphics"].append({"id":self._rx(r"<INAME>(.*?)</INAME>",gb),"caption":self._rx(r"<CAPTION>(.*?)</CAPTION>",gb),"type":self._rx(r"<GTYPE>(.*?)</GTYPE>",gb)})
        for tb in re.findall(r'<sf:TEMPLATE>(.*?)</sf:TEMPLATE>', c, re.DOTALL):
            d.setdefault('templates', []).append({
                'name': self._rx(r'<INAME>(.*?)</INAME>', tb),
                'caption': self._rx(r'<CAPTION>(.*?)</CAPTION>', tb),
                'rows': len(re.findall(r'<ROW>', tb)),
                'columns': len(re.findall(r'<COLUMN>', tb))
            })
        var_seen=set()
        for plist in re.findall(r"<PLIST>(.*?)</PLIST>",c,re.DOTALL):
            for item in re.findall(r"<item>(.*?)</item>",plist,re.DOTALL):
                opd=self._rx(r"<OPD>(.*?)</OPD>",item); io=self._rx(r"<OUTIN>(.*?)</OUTIN>",item)
                if opd and opd not in var_seen: var_seen.add(opd); d["variables_declared"].append({"name":opd,"direction":io})
        ei_kw=["IRN","ACKNO","ACKDT","QRCODE","ZFTEI","SIGNEDQRCODE","IRN_NO","IRN_DT","EWAYNO","EWAYDT"]
        d["einvoice_objects"]=[{"keyword":kw,"occurrences":len(re.findall(kw,c,re.IGNORECASE))} for kw in ei_kw if kw.lower() in c.lower()]
        return d

    def _abap_from_xml(self, c):
        d={"function_calls":[],"call_transactions":[],"tables_used":[],"perform_calls":[],"auth_checks":[],"messages":[],"code_blocks":[]}
        all_lines=[]
        for cb in re.findall(r"<CODE>(.*?)</CODE>",c,re.DOTALL):
            lines=[self._clean(i) for i in re.findall(r"<item>(.*?)</item>",cb,re.DOTALL) if i.strip()]
            if lines: all_lines.extend(lines); d["code_blocks"].append({"lines":lines})
        text="\n".join(all_lines)
        seen_fm=set()
        for fm in re.findall(r"CALL FUNCTION\'([^\']+)\'",text,re.IGNORECASE):
            if fm not in seen_fm: seen_fm.add(fm); d["function_calls"].append({"name":fm,"source":"embedded_abap"})
        seen_tx=set()
        for tx in re.findall(r"CALL TRANSACTION\'?(\w+)\'?",text,re.IGNORECASE):
            if tx not in seen_tx: seen_tx.add(tx); d["call_transactions"].append({"name":tx.upper(),"source":"embedded_abap"})
        seen_t=set()
        for t in re.findall(r"(?:FROM|INSERT INTO|UPDATE|MODIFY)\s+(\w+)",text,re.IGNORECASE):
            t=t.upper()
            if t not in seen_t and len(t)>2 and t not in {"INITIAL","TABLE","LINE"}:
                seen_t.add(t); d["tables_used"].append({"name":t,"source":"embedded_abap"})
        for p in re.findall(r"PERFORM\s+(\w+)",text,re.IGNORECASE):
            d["perform_calls"].append({"name":p.upper()})
        for a in re.findall(r"AUTHORITY-CHECK OBJECT\'([^\']+)\'",text,re.IGNORECASE):
            d["auth_checks"].append({"object":a})
        return d

    def _extract_generic_xml(self, content, filename):
        obj=(self._rx(r"<(?:FORMNAME|PROGNAME|CLASSNAME|FUNCNAME|VIEWNAME)>(.*?)</",content) or filename.replace(".xml","").upper())
        return {"object_type":"xml_object","program_name":obj,"description":self._rx(r"<CAPTION>(.*?)</CAPTION>",content),"tables_used":[],"function_calls":[],"devclass":self._rx(r"<DEVCLASS>(.*?)</DEVCLASS>",content)}

    def _abap(self, content):
        d={
            "object_type":"abap_source","program_name":"","description":"",
            "includes":[],"tables_declared":[],"tables_used":[],
            "function_calls":[],"call_transactions":[],"perform_calls":[],
            "forms":[],"parameters":[],"select_options":[],
            "auth_checks":[],"smart_forms":[],"messages":[],
            "classes":[],"methods":[],"interfaces":[],
            "data_declarations":[],"constants":[],"types":[],
            "enhancements":[],"events":[],"header_comments":[],
            "complexity_indicators":{"total_lines":0,"select_star":0,"select_in_loop":0,"nested_loops":0}
        }
        lines=content.split("\n")
        d["complexity_indicators"]["total_lines"]=len(lines)
        d["header_comments"]=[l.strip().lstrip("*").lstrip(chr(34)).strip() for l in lines[:50] if l.strip().startswith("*") or l.strip().startswith(chr(34))]
        m=re.search(r"^\s*(?:REPORT|PROGRAM|FUNCTION-POOL|CLASS-POOL|TYPE-POOL)\s+(\w+)",content,re.IGNORECASE|re.MULTILINE)
        if m: d["program_name"]=m.group(1).upper()
        if d["header_comments"]: d["description"]=" ".join(d["header_comments"][:3])[:300]
        d["includes"]=re.findall(r"^\s*INCLUDE\s+(\w+)",content,re.IGNORECASE|re.MULTILINE)
        for td in re.findall(r"^\s*TABLES\s*:\s*([^.]+)\.",content,re.IGNORECASE|re.MULTILINE):
            d["tables_declared"].extend([t.strip().upper() for t in td.split(",") if t.strip()])
        seen_t=set(d["tables_declared"])
        for t in re.findall(r"\bFROM\s+(\w+)",content,re.IGNORECASE):
            t=t.upper()
            if t not in seen_t and len(t)>2 and not t.startswith("@") and t not in {"WHERE","INTO","AND","OR","SELECT","TABLE","SCREEN","INITIAL"}:
                seen_t.add(t); d["tables_used"].append({"name":t,"operation":"SELECT"})
        for op in ["INSERT","UPDATE","DELETE","MODIFY"]:
            for t in re.findall(rf"^\s*{op}\s+(\w+)",content,re.IGNORECASE|re.MULTILINE):
                t=t.upper()
                if t not in seen_t and len(t)>2: seen_t.add(t); d["tables_used"].append({"name":t,"operation":op})
        d["function_calls"]=[{"name":f} for f in re.findall(r"CALL\s+FUNCTION\s+\'([^\']+)\'",content,re.IGNORECASE)]
        d["call_transactions"]=[{"name":t.upper()} for t in re.findall(r"CALL\s+TRANSACTION\s+\'?(\w+)\'?",content,re.IGNORECASE)]
        d["perform_calls"]=[{"name":p.upper()} for p in re.findall(r"^\s*PERFORM\s+(\w+)",content,re.IGNORECASE|re.MULTILINE)]
        for fm in re.finditer(r"^\s*FORM\s+(\w+)(.*?)ENDFORM\.",content,re.IGNORECASE|re.MULTILINE|re.DOTALL):
            body=fm.group(0)
            d["forms"].append({"name":fm.group(1).upper(),"tables_accessed":sorted(set(t.upper() for t in re.findall(r"\bFROM\s+(\w+)",body,re.IGNORECASE) if len(t)>2)),"line_count":len(body.split("\n"))})
        for p_str in re.findall(r"^\s*PARAMETERS\s*:\s*([^.]+)\.",content,re.IGNORECASE|re.MULTILINE):
            for param in p_str.split(","):
                parts=param.strip().split()
                if parts: d["parameters"].append({"name":parts[0].upper(),"obligatory":"OBLIGATORY" in param.upper()})
        d["select_options"]=[{"name":s.strip().split()[0].upper()} for so in re.findall(r"^\s*SELECT-OPTIONS\s*:\s*([^.]+)\.",content,re.IGNORECASE|re.MULTILINE) for s in so.split(",") if s.strip()]
        d["auth_checks"]=[{"object":m.group(1)} for m in re.finditer(r"AUTHORITY-CHECK\s+OBJECT\s+\'([^\']+)\'",content,re.IGNORECASE)]
        d["smart_forms"]=[{"name":f.upper()} for f in re.findall(r"FORMNAME\s*=\s*[\'\"]?([A-Z_][A-Z0-9_]+)",content,re.IGNORECASE) if len(f)>3]
        d["messages"]=[{"class":m.group(1) or "","type":m.group(2),"number":m.group(3)} for m in re.finditer(r"MESSAGE\s+(?:(\w+))?([EWIAS])(\d+)",content,re.IGNORECASE)]
        for cd in re.finditer(r"^\s*CLASS\s+(\w+)\s+DEFINITION.*?ENDCLASS\.",content,re.IGNORECASE|re.MULTILINE|re.DOTALL):
            d["classes"].append({"name":cd.group(1).upper(),"methods":re.findall(r"METHODS\s+(\w+)",cd.group(0),re.IGNORECASE),"line_count":len(cd.group(0).split("\n"))})
        d["enhancements"]=[{"name":e} for e in re.findall(r"ENHANCEMENT\s+(\w+)",content,re.IGNORECASE)]
        d["events"]=[{"name":e.strip()} for e in re.findall(r"^\s*(INITIALIZATION|START-OF-SELECTION|END-OF-SELECTION|AT SELECTION-SCREEN[^.]*|TOP-OF-PAGE|END-OF-PAGE)",content,re.IGNORECASE|re.MULTILINE)]
        d['structures'] = []
        for struct in re.findall(r'TYPE\s+(Z\w+)', content, re.IGNORECASE):
            if struct.upper() not in [s.get('name','') for s in d['structures']]:
                d['structures'].append({'name': struct.upper(), 'source': 'type_reference'})
        for struct in re.findall(r'LIKE\s+(Z\w+)', content, re.IGNORECASE):
            if struct.upper() not in [s.get('name','') for s in d['structures']]:
                d['structures'].append({'name': struct.upper(), 'source': 'like_reference'})
        d["complexity_indicators"]["select_star"]=len(re.findall(r"SELECT\s+\*\s+FROM",content,re.IGNORECASE))
        in_loop=0
        for line in lines:
            s=line.strip().upper()
            if re.match(r"LOOP\s+",s): in_loop+=1
            if s.startswith("ENDLOOP"): in_loop=max(0,in_loop-1)
            if in_loop>0 and re.match(r"SELECT\b",s): d["complexity_indicators"]["select_in_loop"]+=1
        return d


_extractor = SAPObjectExtractor()

def extract_sap_objects(content, file_type="", filename=""):
    """Module-level convenience - extract all SAP objects from source content."""
    return _extractor.extract(content, file_type, filename)
