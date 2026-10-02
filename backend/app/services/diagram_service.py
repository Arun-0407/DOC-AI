"""
Diagram generation utilities — build valid Mermaid diagrams from
actual extracted SAP object data. No hardcoded object names or relationships.
"""


def generate_er_diagram(tables: list) -> str:
    """Generate Mermaid ER diagram from actual table list."""
    if not tables:
        return "erDiagram\n  %% No tables extracted from source"
    lines = ["erDiagram"]
    for t in tables[:20]:
        name = t.get("name", "TABLE") if isinstance(t, dict) else str(t)
        lines.append(f'  {name.replace("-","_")} {{')
        lines.append(f'    string key "Primary Key"')
        lines.append(f'  }}')
    return "\n".join(lines)


def generate_dependency_diagram(parsed_data: dict) -> str:
    """Generate Mermaid dependency graph from actual extracted dependencies."""
    prog = parsed_data.get("program_name", "PROGRAM")
    lines = ["graph TD"]
    lines.append(f'  PROG["{prog}"]')
    for fm in parsed_data.get("function_calls", [])[:15]:
        name = fm.get("name", "") if isinstance(fm, dict) else str(fm)
        safe = name.replace("-","_").replace("/","_")
        lines.append(f'  PROG --> FM_{safe}["{name}"]')
    for tx in parsed_data.get("call_transactions", [])[:10]:
        name = tx.get("name", "") if isinstance(tx, dict) else str(tx)
        lines.append(f'  PROG --> TX_{name}["{name}"]')
    for t in parsed_data.get("tables_used", [])[:10]:
        name = t.get("name", "") if isinstance(t, dict) else str(t)
        lines.append(f'  PROG --> TBL_{name}[("{name}")]')
    return "\n".join(lines)


def generate_class_diagram(classes: list) -> str:
    """Generate class diagram from extracted classes."""
    if not classes:
        return "classDiagram\n  %% No classes found in source"
    lines = ["classDiagram"]
    for cls in classes[:10]:
        name = cls.get("name", "CLASS") if isinstance(cls, dict) else str(cls)
        lines.append(f"  class {name} {{")
        for m in (cls.get("methods", []) if isinstance(cls, dict) else [])[:5]:
            lines.append(f"    +{m}()")
        lines.append("  }")
    return "\n".join(lines)


def generate_sequence_diagram(parsed_data: dict) -> str:
    """Generate sequence diagram from extracted calls."""
    prog = parsed_data.get("program_name", "PROGRAM")
    lines = ["sequenceDiagram", f"  participant {prog}"]
    fms = [f.get("name","") if isinstance(f,dict) else str(f) for f in parsed_data.get("function_calls",[])[:8]]
    for fm in fms:
        safe = fm.replace(" ","_").replace("/","_").replace("-","_")
        lines.append(f"  participant {safe}")
    for fm in fms:
        safe = fm.replace(" ","_").replace("/","_").replace("-","_")
        lines.append(f"  {prog}->>+{safe}: CALL FUNCTION '{fm}'")
        lines.append(f"  {safe}-->>-{prog}: Return")
    return "\n".join(lines)


def generate_flowchart(parsed_data: dict) -> str:
    """Generate basic flowchart from extracted events and forms."""
    prog = parsed_data.get("program_name", "PROGRAM")
    lines = ["flowchart TD", f'  START(["{prog} Start"])']
    events = parsed_data.get("events", [])
    prev = "START"
    for i, evt in enumerate(events[:8]):
        name = evt.get("name","") if isinstance(evt,dict) else str(evt)
        node_id = f"EVT{i}"
        safe = name.replace(" ","_").replace("-","_")
        lines.append(f'  {node_id}["{name}"]')
        lines.append(f"  {prev} --> {node_id}")
        prev = node_id
    lines.append(f'  END_NODE([End])')
    lines.append(f"  {prev} --> END_NODE")
    return "\n".join(lines)


def generate_html_flowchart(parsed_data: dict) -> str:
    """Generate HTML-based program execution flowchart."""
    prog = parsed_data.get('program_name', 'PROGRAM')
    nodes = []
    
    def pill(text, color='#1a3a6b'):
        return f'<div class="fc-node pill" style="background:{color}">{text}</div>'
    def proc(title, desc=''):
        return f'<div class="fc-node proc"><strong>{title}</strong><span>{desc}</span></div>'
    def dec(title, desc=''):
        return f'<div class="fc-node dec"><strong>{title}</strong><span>{desc}</span></div>'
    def loop_bar(text):
        return f'<div class="fc-node loop-bar">{text}</div>'
    def arrow():
        return '<div class="fc-arrow"></div>'
    
    nodes.append(pill('START'))
    nodes.append(arrow())
    
    # Events
    events = parsed_data.get('events', [])
    for evt in events[:3]:
        name = evt.get('name', '') if isinstance(evt, dict) else str(evt)
        nodes.append(proc(name))
        nodes.append(arrow())
    
    # Function calls
    for fm in parsed_data.get('function_calls', [])[:8]:
        name = fm.get('name', '') if isinstance(fm, dict) else str(fm)
        nodes.append(proc(f'CALL FUNCTION {name}'))
        nodes.append(arrow())
    
    # Forms/Performs
    for form in parsed_data.get('forms', parsed_data.get('perform_calls', []))[:5]:
        name = form.get('name', '') if isinstance(form, dict) else str(form)
        nodes.append(proc(f'PERFORM {name}'))
        nodes.append(arrow())
    
    nodes.append(pill('END', '#059669'))
    
    inner = '\n'.join(nodes)
    return f'<div class="fc-wrap"><div class="fc">{inner}</div></div>'


def generate_html_dfd(parsed_data: dict) -> str:
    """Generate HTML-based Data Flow Diagram Level 1."""
    tables = parsed_data.get('tables_used', [])
    fms = parsed_data.get('function_calls', [])
    prog = parsed_data.get('program_name', 'PROGRAM')
    
    # Build process nodes
    processes = []
    processes.append(('P1', 'Validate', 'Input'))
    processes.append(('P2', 'Fetch', 'Data'))
    processes.append(('P3', 'Process', 'Logic'))
    processes.append(('P4', 'Generate', 'Output'))
    
    proc_html = []
    for pid, name, sub in processes:
        proc_html.append(f'<div class="dfd-proc"><strong>{pid}</strong><span>{name}</span><span style="font-size:10px">{sub}</span></div>')
        proc_html.append('<div style="display:flex;flex-direction:column;align-items:center;margin:0 8px"><div style="width:60px;height:2px;background:#6b7280;margin-top:35px"></div></div>')
    
    # Data stores from tables
    stores = []
    custom_tables = [t.get('name','') if isinstance(t,dict) else str(t) for t in tables if (t.get('name','') if isinstance(t,dict) else str(t)).startswith('Z')]
    std_tables = [t.get('name','') if isinstance(t,dict) else str(t) for t in tables if not (t.get('name','') if isinstance(t,dict) else str(t)).startswith('Z')]
    
    if std_tables:
        stores.append(f'<div class="dfd-store">D1: {", ".join(std_tables[:6])}</div>')
    if custom_tables:
        stores.append(f'<div class="dfd-store">D2: {", ".join(custom_tables[:6])}</div>')
    
    stores_html = '<div style="margin:0 12px;font-size:18px;color:#6b7280">↕</div>'.join(stores)
    
    return f'''<div class="dfd-wrap">
    <div class="dfd-row"><div class="dfd-ext">USER<br/><span style="font-size:10px;opacity:.8">Input</span></div>
    <div style="display:flex;flex-direction:column;align-items:center;margin:0 8px"><div style="width:60px;height:2px;background:#6b7280;margin-top:35px"></div></div>
    {''.join(proc_html)}
    <div class="dfd-ext">OUTPUT<br/><span style="font-size:10px;opacity:.8">Print/PDF</span></div></div>
    <div style="display:flex;justify-content:center;margin:12px 0"><div style="width:2px;height:32px;background:#6b7280"></div></div>
    <div class="dfd-row">{stores_html}</div>
    </div>'''


def generate_html_connectivity(parsed_data: dict) -> str:
    """Generate HTML-based Connectivity/Integration diagram."""
    prog = parsed_data.get('program_name', 'PROGRAM')
    tcode = ''
    fms = parsed_data.get('function_calls', [])
    tables = parsed_data.get('tables_used', [])
    txns = parsed_data.get('call_transactions', [])
    smart_forms = parsed_data.get('smart_forms', [])
    
    # Left side: FMs + SmartForms
    left_items = []
    for fm in fms[:8]:
        name = fm.get('name','') if isinstance(fm,dict) else str(fm)
        left_items.append(f'<div class="conn-item ci-fm"><strong>{name}</strong><span>Function Module</span></div>')
    for sf in smart_forms[:4]:
        name = sf.get('name','') if isinstance(sf,dict) else str(sf)
        left_items.append(f'<div class="conn-item ci-sf"><strong>{name}</strong><span>Smart Form</span></div>')
    
    # Right side: Tables
    right_items = []
    
    custom_t = [t for t in tables if (t.get('name','') if isinstance(t,dict) else str(t)).startswith('Z')]
    std_t = [t for t in tables if not (t.get('name','') if isinstance(t,dict) else str(t)).startswith('Z')]
    
    for t in custom_t[:8]:
        name = t.get('name','') if isinstance(t,dict) else str(t)
        right_items.append(f'<div class="conn-item ci-zt"><strong>{name}</strong><span>Custom Z-Table</span></div>')
    
    if std_t:
        names = ' · '.join(t.get('name','') if isinstance(t,dict) else str(t) for t in std_t[:8])
        right_items.append(f'<div class="conn-item" style="background:#f8fafc;border:1px solid #e2e8f0"><strong>{names}</strong><span>SAP Standard Tables</span></div>')
    
    # Bottom: Transactions
    txn_items = []
    for tx in txns[:6]:
        name = tx.get('name','') if isinstance(tx,dict) else str(tx)
        txn_items.append(f'<div class="conn-item ci-tr"><strong>{name}</strong><span>Transaction</span></div>')
    
    return f'''<div class="conn-wrap">
    <div class="conn-grid">
    <div class="conn-left">{''.join(left_items)}</div>
    <div><div class="conn-center"><div class="prog">{prog}</div><div style="margin-top:12px;font-size:10px;color:rgba(255,255,255,.6)">← CALLS →</div></div></div>
    <div class="conn-right">{''.join(right_items)}</div>
    </div>
    {'<div style="margin-top:16px;border-top:1px dashed #e2e8f0;padding-top:14px"><div style="font-size:10px;font-weight:700;color:#1a3a6b;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;text-align:center">Downstream Transactions Called</div><div class="conn-bot">' + ''.join(txn_items) + '</div></div>' if txn_items else ''}
    </div>'''
