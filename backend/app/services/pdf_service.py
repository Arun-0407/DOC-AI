"""Enterprise SAP KT PDF Generator - ALL extracted objects, no summaries."""
import io
from app.models.document import Document


def _s(d,*k,default=""):
    v=d
    for x in k:
        if isinstance(v,dict): v=v.get(x)
        else: return default
        if v is None: return default
    return str(v) if v not in (None,"") else default


def _pm(doc)->dict:
    pm=getattr(doc,"_parsed_metadata",None) or {}
    if not pm and hasattr(doc,"upload") and doc.upload:
        raw=doc.upload.parsed_metadata
        pm=raw if isinstance(raw,dict) else {}
    return pm


def generate_pdf(document:Document)->bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,HRFlowable
    from reportlab.lib.enums import TA_CENTER

    BLUE=colors.HexColor("#0F4C81"); LT=colors.HexColor("#E8F0F8"); DRK=colors.HexColor("#082244")
    GRN=colors.HexColor("#1A7F37"); ORG=colors.HexColor("#E67E22")
    PRP=colors.HexColor("#6C3483"); TEL=colors.HexColor("#117A8B")

    buf=io.BytesIO()
    pdoc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=1.5*cm,rightMargin=1.5*cm,topMargin=2*cm,bottomMargin=2*cm)
    styles=getSampleStyleSheet()
    H1=ParagraphStyle("H1",parent=styles["Heading1"],textColor=BLUE,fontSize=13,spaceAfter=3,spaceBefore=8)
    H2=ParagraphStyle("H2",parent=styles["Heading2"],textColor=DRK,fontSize=10,spaceAfter=2,spaceBefore=5)
    H3=ParagraphStyle("H3",parent=styles["Heading3"],textColor=BLUE,fontSize=8.5,spaceAfter=2,spaceBefore=3)
    BD=ParagraphStyle("BD",parent=styles["Normal"],fontSize=8,leading=11,spaceAfter=2)
    BDM=ParagraphStyle("BDM",parent=styles["Normal"],fontSize=7.5,leading=10,spaceAfter=2,fontName="Courier")
    BLT=ParagraphStyle("BLT",parent=styles["Normal"],fontSize=8,leading=11,leftIndent=10,spaceAfter=1)
    WH=ParagraphStyle("WH",parent=styles["Normal"],fontSize=8,textColor=colors.white,fontName="Helvetica-Bold")
    CTR=ParagraphStyle("CTR",parent=styles["Normal"],fontSize=20,textColor=BLUE,alignment=TA_CENTER,spaceAfter=6,leading=26,fontName="Helvetica-Bold")
    SUB=ParagraphStyle("SUB",parent=styles["Normal"],fontSize=11,textColor=colors.grey,alignment=TA_CENTER,spaceAfter=18)

    import json as _jmod2
    def _j2(v):
        if v is None: return {}
        if isinstance(v, str):
            try: return _jmod2.loads(v)
            except: return {}
        return v

    story=[]
    pm=_pm(document)
    st=pm.get("source_type","")
    is_sf=st=="smartform_xml"

    def sec(t,c=BLUE): story.extend([Spacer(1,.25*cm),Paragraph(t,H1),HRFlowable(width="100%",thickness=2,color=c),Spacer(1,.08*cm)])
    def ss(t): story.append(Paragraph(t,H2))
    def fld(l,v,m=False): 
        if v and v not in ("","N/A"): story.append(Paragraph(f"<b>{l}:</b>  {v}",BDM if m else BD))
    def blt(t): story.append(Paragraph(f"• {t}",BLT))
    def mt(hdrs,rows,ws=None,hc=None):
        hc=hc or BLUE
        if not rows: story.append(Paragraph("No records.",BD)); return
        data=[[Paragraph(f"<b>{h}</b>",WH) for h in hdrs]]
        for r in rows: data.append([Paragraph(str(c or ""),BD) for c in r])
        w=ws or [17*cm/len(hdrs)]*len(hdrs)
        t=Table(data,colWidths=w,repeatRows=1,splitByRow=True)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),hc),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),8),("GRID",(0,0),(-1,-1),.4,colors.lightgrey),("ROWBACKGROUNDS",(1,0),(-1,-1),[colors.white,LT]),("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("FONTSIZE",(0,1),(-1,-1),7.5)]))
        story.append(t); story.append(Spacer(1,.15*cm))

    # ── COVER ────────────────────────────────────────────────────────────
    cv=_j2(document.cover_data); hdr=pm.get("header",{})
    story.append(Spacer(1,2*cm))
    story.append(Paragraph("SAP Technical Knowledge Transfer Document",CTR))
    story.append(Paragraph(document.title or "SAP Object Analysis",SUB))
    story.append(HRFlowable(width="90%",thickness=3,color=BLUE,hAlign="CENTER"))
    story.append(Spacer(1,.4*cm))
    crows=[]
    def cr(k,v):
        if v: crows.append([k,str(v)])
    cr("Program / Form Name", pm.get("program_name") or _s(cv,"program_name"))
    cr("Description",         pm.get("description")  or _s(cv,"description"))
    cr("SAP Module",          _s(cv,"module"))
    cr("Object Type",         st.replace("_"," ").title() or _s(cv,"object_type"))
    cr("Package (DevClass)",  hdr.get("devclass") or _s(cv,"package"))
    cr("Version",             hdr.get("version")  or _s(cv,"version"))
    cr("Transaction Code",    _s(cv,"tcode"))
    cr("Message Class",       _s(cv,"message_class"))
    cr("First User / Author", hdr.get("firstuser") or _s(cv,"author"))
    cr("Creation Date",       hdr.get("firstdate") or _s(cv,"creation_date"))
    cr("Last Modified By",    hdr.get("lastuser"))
    cr("Last Modified Date",  hdr.get("lastdate")  or _s(cv,"last_modified_date"))
    cr("Master Language",     hdr.get("masterlang",""))
    cr("Technical Consultant",_s(cv,"technical_consultant"))
    cr("Functional Consultant",_s(cv,"functional_consultant"))
    cr("Project",             _s(cv,"project_name"))
    if crows:
        from reportlab.lib import colors as _c
        ct=Table([[Paragraph(f"<b>{r[0]}</b>",BD),Paragraph(r[1],BD)] for r in crows],colWidths=[5*cm,12*cm])
        ct.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),LT),("TEXTCOLOR",(0,0),(0,-1),DRK),("GRID",(0,0),(-1,-1),.4,_c.lightgrey),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("FONTSIZE",(0,0),(-1,-1),8)]))
        story.append(ct)
    if is_sf:
        iface=pm.get("interface",{})
        inv=[["SmartForm Pages",len(pm.get("pages",[]))],["SmartForm Windows",len(pm.get("windows",[]))],
             ["Business Rule Conditions",len(pm.get("conditions",[]))],["Text Elements",len(pm.get("text_elements",[]))],
             ["Embedded ABAP Blocks",len(pm.get("code_blocks",[]))],["Database Tables",len(pm.get("tables_used",[]))],
             ["Function Calls",len(pm.get("function_calls",[]))],["Field References",len(pm.get("field_references",[]))],
             ["Global Variables",len(pm.get("variables_declared",[]))],["Interface Imports",len(iface.get("imports",[]))],
             ["Interface Tables",len(iface.get("tables",[]))],["Interface Exports",len(iface.get("exports",[]))],
             ["E-Invoice Objects",len(pm.get("einvoice_objects",[]))],["Graphics",len(pm.get("graphics",[]))]]
        story.append(Spacer(1,.3*cm))
        story.append(Paragraph("<b>EXTRACTED OBJECT INVENTORY</b>",H2))
        mt(["Object Category","Extracted Count"],[[r[0],str(r[1])] for r in inv],[10*cm,7*cm])
    story.append(PageBreak())

    # ── SEC 1: PROGRAM INFORMATION ────────────────────────────────────────
    sec("1. PROGRAM INFORMATION")
    bv=_j2(document.business_view)
    fld("Objective",_s(bv,"objective"))
    fld("Business Purpose",_s(bv,"business_purpose"))
    fld("Scope",_s(bv,"scope"))
    rules=bv.get("business_rules",[])
    if rules:
        ss("Business Rules")
        for r in (rules or [])[:50]:
            blt(str(r))
    story.append(PageBreak())

    # ── SEC 2: SMARTFORM INTERFACE PARAMETERS ─────────────────────────────
    if is_sf:
        iface=pm.get("interface",{})
        sec("2. SMARTFORM INTERFACE PARAMETERS",BLUE)
        imports=iface.get("imports",[])
        if imports:
            ss(f"Import Parameters ({len(imports)} total)")
            mt(["#","Parameter Name","Type/Structure","Optional","Purpose"],
               [[str(i+1),p.get("name",""),p.get("type",""),"Yes" if p.get("optional") else "Required",""] for i,p in enumerate(imports)],
               [.8*cm,4.5*cm,4.5*cm,2.2*cm,5*cm])
        tables=iface.get("tables",[])
        if tables:
            ss(f"Table Parameters ({len(tables)} total)")
            mt(["#","Table Name","Like / Structure","Purpose"],
               [[str(i+1),p.get("name",""),p.get("type",""),""] for i,p in enumerate(tables)],
               [.8*cm,4*cm,5.5*cm,6.7*cm])
        exports=iface.get("exports",[])
        if exports:
            ss(f"Export Parameters ({len(exports)} total)")
            mt(["#","Parameter Name","Type","Purpose"],
               [[str(i+1),p.get("name",""),p.get("type",""),""] for i,p in enumerate(exports)],
               [.8*cm,5*cm,5*cm,6.2*cm])
        excs=iface.get("exceptions",[])
        if excs:
            ss(f"Exceptions ({len(excs)} total)")
            mt(["#","Exception Name"],[[str(i+1),e.get("name","")] for i,e in enumerate(excs)],[.8*cm,16.2*cm])
        story.append(PageBreak())

    # ── SEC 3: SMARTFORM PAGES ────────────────────────────────────────────
    if is_sf:
        pages=pm.get("pages",[])
        sec("3. SMARTFORM PAGES",BLUE)
        if pages:
            mt(["#","Page Name","Orientation","Next Page"],
               [[str(i+1),p.get("name",""),p.get("orientation","L"),p.get("next","")] for i,p in enumerate(pages)],
               [.8*cm,4*cm,4*cm,8.2*cm])
        ns=pm.get("node_summary",{})
        if ns:
            ss("Node Type Summary")
            mt(["Node Type","Count","Description"],
               [[k,str(v),{"Text":"Text output nodes","Window":"Window containers","Section":"Layout sections","Table_Row":"Table row definitions","Condition":"Conditional display nodes","Event":"Header/Main/Footer events","Page":"Form pages","Program_Lines":"Embedded ABAP code","Template":"Root template","Graphic":"Image/graphic nodes","Complex":"Complex alternative sections"}.get(k,"")] for k,v in ns.items()],
               [4*cm,3*cm,10*cm])
        story.append(PageBreak())

    # ── SEC 4: SMARTFORM WINDOWS ──────────────────────────────────────────
    if is_sf:
        windows=pm.get("windows",[])
        sec(f"4. SMARTFORM WINDOWS ({len(windows)} TOTAL)",BLUE)
        if windows:
            mt(["#","Window Name","Type","Text Nodes","Conditions","Table Rows","Caption / Purpose"],
               [[str(i+1),w.get("name",""),w.get("window_type",""),str(w.get("text_nodes",0)),str(w.get("conditions",0)),str(w.get("table_rows",0)),w.get("caption","")] for i,w in enumerate(windows)],
               [.7*cm,3.2*cm,2.2*cm,1.8*cm,2*cm,1.8*cm,5.3*cm])
        story.append(PageBreak())

    # ── SEC 5: ALL CONDITIONS / BUSINESS RULES ───────────────────────────
    if is_sf:
        conds=pm.get("conditions",[])
        sec(f"5. ALL CONDITIONS AND BUSINESS RULES ({len(conds)} TOTAL)",GRN)
        if conds:
            mt(["#","Condition ID","Caption","Full Logic Expression"],
               [[str(i+1),c.get("id",""),c.get("caption",""),c.get("logic","")] for i,c in enumerate(conds)],
               [.7*cm,3*cm,4*cm,9.3*cm],hc=GRN)
        story.append(PageBreak())

    # ── SEC 6: ALL GLOBAL VARIABLES / PLIST ───────────────────────────────
    if is_sf:
        varlist=pm.get("variables_declared",[])
        sec(f"6. ALL GLOBAL VARIABLES AND PARAMETERS ({len(varlist)} TOTAL)",ORG)
        if varlist:
            rows=[]
            for i,v in enumerate(varlist):
                n=v.get("name",""); d=v.get("direction","?")
                purpose = "Output variable (computed in form)" if d=="O" else "Input parameter (passed from caller)" if d=="I" else "Internal work variable"
                rows.append([str(i+1),n,d,purpose])
            mt(["#","Variable Name","Direction (I/O)","Purpose / Usage"],rows,[.7*cm,4.5*cm,2.5*cm,9.3*cm],hc=ORG)
        story.append(PageBreak())

    # ── SEC 7: ALL FIELD REFERENCES ──────────────────────────────────────
    if is_sf:
        frefs=pm.get("field_references",[])
        sec(f"7. ALL FIELD AND VARIABLE REFERENCES IN FORM ({len(frefs)} TOTAL)",PRP)
        if frefs:
            rows=[]
            for i,f in enumerate(frefs):
                category = ("E-Invoice/IRN" if any(x in f.upper() for x in ["IRN","ACK","QR","ZFTEI","EWAY"]) else
                            "GST/Tax" if any(x in f.upper() for x in ["GST","SGST","CGST","IGST","TCS","TAX"]) else
                            "Header Field" if f.startswith("HEADER-") or f.startswith("header-") else
                            "Global Variable" if f.startswith("GV_") or f.startswith("gv_") else
                            "Work Variable" if f.startswith("V_") or f.startswith("v_") else
                            "Work Area Field" if f.startswith("WA-") or f.startswith("wa-") else
                            "Line Item Field" if f.startswith("WA-") else
                            "Control Parameter" if f.upper() in ["DUPIND","CANINV","REFLAG","PAGE","PLANT","NXTPAGE","PRINTBATCH"] else
                            "Local Variable" if f.startswith("LV_") or f.startswith("lv_") else
                            "System Field")
                rows.append([str(i+1),f"&{f}&",category])
            mt(["#","Field Reference","Category"],rows,[.7*cm,6*cm,10.3*cm],hc=PRP)
        story.append(PageBreak())

    # ── SEC 8: TEXT ELEMENTS 
    if is_sf:
        texts=pm.get("text_elements",[])
        sec(f"8. TEXT ELEMENTS ({len(texts)} TOTAL)",TEL)
        if texts:
            mt(["#","Element ID","Caption / Label","Content / Field Expression"],
               [[str(i+1),t.get("id",""),t.get("caption",""),t.get("content","")[:120]] for i,t in enumerate(texts)],
               [.7*cm,2.5*cm,4*cm,9.8*cm],hc=TEL)
        story.append(PageBreak())

    # ── SEC 9: DATABASE TABLES ────────────────────────────────────────────
    db_tables=pm.get("tables_used",[])
    sec(f"9. DATABASE TABLES ACCESSED ({len(db_tables)} TOTAL)",BLUE)
    if db_tables:
        rows=[]
        for i,t in enumerate(db_tables):
            n=t.get("name","") if isinstance(t,dict) else str(t)
            op=t.get("operation",t.get("source","")) if isinstance(t,dict) else ""
            desc={"VBRP":"Billing Document Items","VBRK":"Billing Document Header","KNA1":"Customer Master",
                  "VBPA":"Sales Doc Partner","T001W":"Plant Master","T005U":"Region Text","T001K":"Valuation Area",
                  "T001":"Company Codes","ADRC":"Address Records","J_1BBRANCH":"India Branch/GSTIN",
                  "VBAK":"Sales Order Header","VBFA":"Document Flow","LIPS":"Delivery Item",
                  "V_KONV":"Pricing Conditions View","VBRP":"Billing Document Items","MARA":"Material Master",
                  "KNMT":"Customer-Material Info","PRPS":"WBS Elements","VBKD":"Sales Business Data",
                  "VBAP":"Sales Order Items","LIKP":"Delivery Header","ZASN_NAPL":"Custom ASN Table",
                  "ZFTEI_HDR_DATA":"E-Invoice Header Data"}.get(n,"")
            src=t.get("source","embedded_abap") if isinstance(t,dict) else ""
            rows.append([str(i+1),n,desc,op,src])
        mt(["#","Table Name","Description","Operation","Source"],rows,[.7*cm,3.5*cm,6*cm,2.5*cm,4.3*cm])
    da=_j2(document.database_analysis)
    wops=da.get("write_operations",[])
    if wops:
        ss("Database Write Operations (INSERT / UPDATE / DELETE / MODIFY)")
        mt(["#","Table","Operation","When / Trigger","Data Written","Purpose"],
           [[str(i+1),op.get("table",""),op.get("operation",""),op.get("when",""),op.get("data_written",""),op.get("purpose","")] for i,op in enumerate(wops)],
           [.7*cm,3*cm,2.2*cm,3.5*cm,3.5*cm,4.1*cm],hc=ORG)
    story.append(PageBreak())

    # ── SEC 10: FUNCTION MODULES ──────────────────────────────────────────
    ad=_j2(document.api_dependency)
    all_fms=[]
    for cat in ["function_modules","bapis","rfcs"]:
        its=ad.get(cat,[])
        if isinstance(its,list): all_fms.extend(its)
    fm_from_pm=[f for f in pm.get("function_calls",[]) if not any(x.get("name","")==f.get("name","") for x in all_fms)]
    sec(f"10. FUNCTION MODULES AND API CALLS ({len(all_fms)+len(fm_from_pm)} TOTAL)",PRP)
    tv=_j2(document.technical_view)
    cfms=tv.get("call_function_statements",[])
    if cfms and isinstance(cfms,list):
        ss(f"Call Function Statements ({len(cfms)} extracted)")
        mt(["#","Function Module","Type","Where Called","Parameters","Returns","Purpose"],
           [[str(i+1),f.get("name",""),f.get("type",""),f.get("where_called",""),str(f.get("parameters_passed",""))[:60],f.get("returns",""),f.get("purpose","")[:80]] for i,f in enumerate(cfms) if isinstance(f,dict)],
           [.7*cm,4*cm,2.2*cm,2.8*cm,3*cm,2*cm,2.3*cm],hc=PRP)
    elif all_fms:
        mt(["#","Name","Description","Type","Direction","Purpose"],
           [[str(i+1),f.get("name",""),f.get("description","")[:60],f.get("type",""),f.get("direction",""),f.get("purpose","")[:60]] for i,f in enumerate(all_fms) if isinstance(f,dict)],
           [.7*cm,4*cm,4.5*cm,2*cm,2*cm,4.8*cm],hc=PRP)
    elif fm_from_pm:
        mt(["#","Function Module","Source"],
           [[str(i+1),f.get("name",""),f.get("source","")] for i,f in enumerate(fm_from_pm) if isinstance(f,dict)],
           [.7*cm,9*cm,7.3*cm],hc=PRP)
    story.append(PageBreak())

    # ── SEC 11: EMBEDDED ABAP CODE BLOCKS ────────────────────────────────
    code_blocks=pm.get("code_blocks",[])
    sec(f"11. EMBEDDED ABAP CODE BLOCKS ({len(code_blocks)} TOTAL)",DRK)
    for i,cb in enumerate(code_blocks):
        lines=cb.get("lines",[])
        story.append(Paragraph(f"<b>Code Block {cb.get('block_index',i+1)}</b> — {len(lines)} lines",H2))
        for start in range(0,len(lines),40):
            chunk=lines[start:start+40]
            code_str="\n".join(str(l) for l in chunk)
            story.append(Paragraph(code_str.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"),BDM))
        story.append(Spacer(1,.2*cm))
    story.append(PageBreak())

    # ── SEC 12: CALL TRANSACTIONS ─────────────────────────────────────────
    txns_pm=pm.get("call_transactions",[])
    txns_tv=tv.get("call_transaction_statements",[])
    all_txns=txns_tv if (txns_tv and isinstance(txns_tv,list)) else txns_pm
    sec(f"12. CALL TRANSACTION STATEMENTS ({len(all_txns)} TOTAL)",TEL)
    if all_txns and isinstance(all_txns,list):
        if all_txns and isinstance(all_txns[0],dict) and "when_called" in all_txns[0]:
            mt(["#","Transaction","When Called","Memory Used","Purpose"],
               [[str(i+1),t.get("transaction",t.get("name","")),t.get("when_called",""),t.get("memory_used",""),t.get("purpose","")] for i,t in enumerate(all_txns) if isinstance(t,dict)],
               [.7*cm,3.5*cm,4*cm,3*cm,5.8*cm],hc=TEL)
        else:
            mt(["#","Transaction Code","Source"],
               [[str(i+1),t.get("name","") if isinstance(t,dict) else str(t),t.get("source","") if isinstance(t,dict) else ""] for i,t in enumerate(all_txns)],
               [.7*cm,6*cm,10.3*cm],hc=TEL)
    story.append(PageBreak())

    # ── SEC 13: E-INVOICE ──────────────────────────────────────────────────
    einv=pm.get("einvoice_objects",[])
    sec(f"13. E-INVOICE AND IRN/QR OBJECTS ({len(einv)} DETECTED)",GRN)
    if einv:
        desc_map={"IRN":"Invoice Reference Number from NIC/GST portal","ACKNO":"Acknowledgement Number from NIC","ACKDT":"Acknowledgement Date","QRCODE":"QR Code image","ZFTEI":"Custom Z-table/FM for E-Invoice","SIGNEDQRCODE":"NIC-signed QR code string","IRN_NO":"IRN Number field","IRN_DT":"IRN Date field","EWAYNO":"E-Way Bill Number","EWAYDT":"E-Way Bill Date"}
        mt(["#","Keyword","Occurrences","Description"],
           [[str(i+1),e.get("keyword",""),str(e.get("occurrences",0)),desc_map.get(e.get("keyword",""),"E-Invoice identifier")] for i,e in enumerate(einv)],
           [.7*cm,4*cm,3*cm,9.3*cm],hc=GRN)
        for line in ["IT_ZFTEI_AUTH_WRKV NE INITIAL → E-Invoice authenticated → Show IRN + ACK + QR code",
                      "IT_ZFTEI_AUTH_WRKV EQ INITIAL → Not authenticated → Standard invoice without IRN",
                      "HEADER-QR_FLAG = X → Display QR code in form","HEADER-BAR_FLAG = X → Display barcode"]:
            story.append(Paragraph(line,BDM))
    story.append(PageBreak())

    # ── SEC 14: GRAPHICS ──────────────────────────────────────────────────
    graphics=pm.get("graphics",[])
    sec(f"14. GRAPHICS ({len(graphics)} TOTAL)",ORG)
    if graphics:
        mt(["#","Graphic ID","Type","Caption"],
           [[str(i+1),g.get("id",""),g.get("type",""),g.get("caption","")] for i,g in enumerate(graphics)],
           [.7*cm,4*cm,3*cm,9.3*cm],hc=ORG)
    story.append(PageBreak())

    # ── SEC 15: BUSINESS RULES ────────────────────────────────────────────
    biz=pm.get("business_rules_discovered",[])
    sec(f"15. BUSINESS RULES DISCOVERED FROM CONDITIONS ({len(biz)} TOTAL)",GRN)
    if biz:
        for i,r in enumerate(biz):
            story.append(Paragraph(f"<b>{i+1}.</b> {str(r).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}",BDM))
        story.append(Spacer(1,.2*cm))
    story.append(PageBreak())

    # ── SEC 16: AI TECHNICAL ANALYSIS ────────────────────────────────────
    sec("16. TECHNICAL ANALYSIS (AI GENERATED)",BLUE)
    bm=tv.get("behavior_matrix",[])
    if bm and isinstance(bm,list) and len(bm)>0 and isinstance(bm[0],dict):
        ss("Billing Type / Behavior Matrix")
        keys=list(bm[0].keys())
        mt(["#"]+[k.replace("_"," ").title() for k in keys],[[str(i+1)]+[str(r.get(k,"")) for k in keys] for i,r in enumerate(bm)],[.7*cm]+[16.3*cm/len(keys)]*len(keys))
    perf=_j2(document.performance_review)
    sil=perf.get("select_in_loop",[])
    if sil and isinstance(sil,list) and len(sil)>0 and isinstance(sil[0],dict):
        ss("Performance: SELECT in LOOP Issues")
        mt(["Location","Issue","Impact","Suggestion"],[[ p.get("location",""),p.get("issue",""),p.get("impact",""),p.get("suggestion","")] for p in sil if isinstance(p,dict)],[4*cm,4*cm,3.5*cm,5.5*cm],hc=ORG)
    sec_r=_j2(document.security_review)
    aobjs=sec_r.get("auth_objects",[])
    if aobjs and isinstance(aobjs,list) and len(aobjs)>0 and isinstance(aobjs[0],dict):
        ss("Security: Authorization Objects")
        mt(["Name","Field","Description","Severity"],[[a.get("name",""),a.get("field",""),a.get("description",""),a.get("severity","")] for a in aobjs if isinstance(a,dict)])
    story.append(PageBreak())

    # ── SEC 17: MODIFICATION HISTORY ─────────────────────────────────────
    mh=_j2(document.modification_history)
    hist=mh.get("history",[])
    sec(f"17. MODIFICATION HISTORY ({len(hist)} ENTRIES)",DRK)
    if hist and isinstance(hist,list):
        mt(["#","Date","Object","Modification Description","Author","Transport","Impact"],
           [[str(i+1),h.get("date",""),h.get("object",""),h.get("modification",""),h.get("author",""),h.get("transport_ref",""),h.get("impact","")] for i,h in enumerate(hist) if isinstance(h,dict)],
           [.6*cm,2*cm,2.2*cm,4*cm,2.5*cm,2.2*cm,3.5*cm],hc=DRK)
    story.append(PageBreak())

    # ── SEC 18: S/4HANA READINESS ────────────────────────────────────────
    ar=_j2(document.ai_recommendations)
    if ar:
        sec("18. S/4HANA READINESS AND MODERNIZATION RECOMMENDATIONS",BLUE)
        scores=[("Code Quality",ar.get("code_quality_score")),("Maintainability",ar.get("maintainability_score")),("Performance",ar.get("performance_score")),("Security",ar.get("security_score")),("S/4HANA Readiness",ar.get("s4hana_readiness_score")),("RAP Migration",ar.get("rap_migration_score"))]
        mt(["Metric","Score / 100"],[[s[0],str(s[1])] for s in scores if s[1] is not None],[8*cm,9*cm])
        sug=ar.get("refactoring_suggestions",[])
        if sug and isinstance(sug,list) and len(sug)>0 and isinstance(sug[0],dict):
            ss("Refactoring Suggestions")
            mt(["#","Title","Description","Priority","Effort","Impact"],
               [[str(i+1),s.get("title",""),s.get("description","")[:80],s.get("priority",""),s.get("effort",""),s.get("impact","")] for i,s in enumerate(sug) if isinstance(s,dict)],
               [.7*cm,3*cm,5*cm,2*cm,2.5*cm,4*cm])
        mpath=ar.get("s4hana_migration_path","")
        if mpath:
            ss("S/4HANA Migration Path")
            story.append(Paragraph(str(mpath),BD))

    pdoc.build(story)
    return buf.getvalue()
