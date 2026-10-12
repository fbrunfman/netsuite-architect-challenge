#!/usr/bin/env python3
"""Genera entrega/caso-3/diagrama.svg — swimlane P2P → O2C de Andina Retail (AR/CO/MX).
Sin dependencias: define carriles, fases, nodos y flechas y emite SVG a mano.
Uso: python3 diagrama_gen.py [salida.svg]
"""
import sys, html

OUT = sys.argv[1] if len(sys.argv) > 1 else 'diagrama.svg'

# ------------------------------------------------------------------ layout
LANE_LABEL_W = 150
COL_W = 205
LANE_H = 150
HEADER_H = 54
TITLE_H = 70
LEGEND_H = 120
PAD = 14
NODE_W = COL_W - 2 * PAD
NODE_H = 58

LANES = [
    ('plan', 'Planificación /\nCompras'),
    ('prov', 'Proveedor\n(externo)'),
    ('comex', 'Comex / Agente\nde aduana (ext.)'),
    ('cost', 'Costos y\nContabilidad'),
    ('log', 'Logística /\nDepósito'),
    ('qa', 'Calidad /\nRegulatorio'),
    ('ns', 'NetSuite\n(transacciones\ny controles)'),
    ('o2c', 'O2C · Ventas /\nMarketplace /\nFacturación'),
]
PHASES = ['1 · Necesidad', '2 · Compra', '3 · Embarque', '4 · Aduana', '5 · Costeo',
          '6 · Recepción', '7 · Liberación QA', '8 · Cuentas a pagar', '9 · Disponible → O2C']

# kind: task | tx (transacción NetSuite) | ctl (punto de control) | note
# pos: (lane, col, slot) slot 0 = arriba, 1 = abajo (dos nodos por celda)
NODES = {
    'n_plan':  dict(lane='plan', col=0, slot=0, kind='task', text='Plan de demanda y reposición\npor depósito (mín/máx, lead time\nde importación por país)'),
    'tx_pr':   dict(lane='ns',   col=0, slot=0, kind='tx',   text='Purchase Requisition\n(subsidiaria, depósito destino)'),
    'n_po':    dict(lane='plan', col=1, slot=0, kind='task', text='Emite PO: incoterm, moneda,\ndepósito final, LC estimado,\nflag "importación"'),
    'tx_po':   dict(lane='ns',   col=1, slot=0, kind='tx',   text='Purchase Order\n(aprobación por monto / subsidiaria)'),
    'k1':      dict(lane='ns',   col=1, slot=1, kind='ctl',  text='K1 · Ítem regulado = lot numbered +\nvencimiento + registro sanitario vigente;\nsi falta, la PO no se aprueba'),
    'n_conf':  dict(lane='prov', col=1, slot=0, kind='task', text='Confirma PO, fecha de\ndespacho y cantidades'),
    'n_ship':  dict(lane='prov', col=2, slot=0, kind='task', text='Despacha: factura comercial,\npacking list con lote de fabricación\ny vencimiento (regulados), BL/AWB'),
    'n_inb':   dict(lane='comex', col=2, slot=0, kind='task', text='Crea Inbound Shipment, agrupa\nPOs, adjunta documentos, carga\nlote/venc. declarados por línea'),
    'tx_inb':  dict(lane='ns',   col=2, slot=0, kind='tx',   text='Inbound Shipment\n(LC Status = Pending)'),
    'k3':      dict(lane='ns',   col=2, slot=1, kind='ctl',  text='K3 · Regulados sin lote/venc.\ndeclarados → INBSHIP no pasa\na "listo para aduana"'),
    'n_adu':   dict(lane='comex', col=3, slot=0, kind='task', text='Despacho aduanero → identificador:\nMX pedimento · AR despacho SIM ·\nCO declaración de importación'),
    'n_adu2':  dict(lane='comex', col=3, slot=1, kind='task', text='Carga identificador + fecha de\nliberación en INBSHIP; crea valor\ndel segmento de aduana'),
    'k2':      dict(lane='ns',   col=3, slot=0, kind='ctl',  text='K2 · Formato del identificador\npor país (regex) y segmento\ncreado; obligatorios'),
    'n_lc':    dict(lane='cost', col=4, slot=0, kind='task', text='Carga landed cost real por\ncategoría (plantilla por país)\ny confirma'),
    'tx_lc':   dict(lane='ns',   col=4, slot=0, kind='tx',   text='INBSHIP landed cost\nLoaded → Confirmed'),
    'k4':      dict(lane='ns',   col=4, slot=1, kind='ctl',  text='K4 · Todas las categorías\nobligatorias del país cargadas;\nsólo Costos confirma'),
    'n_rec':   dict(lane='log',  col=5, slot=0, kind='task', text='Recibe directo en depósito final\n(Receive o job masivo): lote,\nvencimiento, bin, cantidad'),
    'tx_ir':   dict(lane='ns',   col=5, slot=0, kind='tx',   text='Item Receipt · inventory detail\n(lote, venc.) · segmento en líneas ·\ncosto = PO + LC · estado Cuarentena'),
    'k5':      dict(lane='ns',   col=5, slot=1, kind='ctl',  text='K5 · Gate IR (todos los contextos):\nLC confirmado, identificador,\nsegmento/línea, lote, venc. regulados'),
    'n_qa':    dict(lane='qa',   col=6, slot=0, kind='task', text='Verifica lote, vencimiento,\nregistro sanitario y documentación;\nlibera o rechaza (regulados)'),
    'tx_st':   dict(lane='ns',   col=6, slot=0, kind='tx',   text='Inventory Status change\nCuarentena → Disponible\n(+ maestro de pedimentos MX)'),
    'k6':      dict(lane='ns',   col=6, slot=1, kind='ctl',  text='K6 · Cuarentena no se compromete\nni se pickea; vencimiento < mínimo\nde vida útil → Bloqueado'),
    'n_vb':    dict(lane='cost', col=7, slot=0, kind='task', text='Vendor Bill 3-way match;\nbills de flete / agente / impuestos\nconciliados contra el LC'),
    'tx_vb':   dict(lane='ns',   col=7, slot=0, kind='tx',   text='Vendor Bills\n(proveedor, forwarder, agente)'),
    'k7':      dict(lane='ns',   col=7, slot=1, kind='ctl',  text='K7 · Variación LC real vs confirmado\n> umbral → ajuste de costo\naprobado (nunca silencioso)'),
    'n_o2c':   dict(lane='o2c',  col=8, slot=0, kind='task', text='SO compromete sólo stock Disponible\n→ pick FEFO → Item Fulfillment →\nfactura electrónica → trazabilidad'),
    'tx_o2c':  dict(lane='ns',   col=8, slot=0, kind='tx',   text='Sales Order / Item Fulfillment /\nInvoice (CFDI con pedimento;\nsegmento en líneas de COGS)'),
    'k8':      dict(lane='ns',   col=8, slot=1, kind='ctl',  text='K8 · Sin lote/venc. no se despacha;\nMX sin pedimento no se timbra;\nK9 · invariantes diarias (saved searches)'),
    'n_mon':   dict(lane='log',  col=8, slot=0, kind='note', text='Logística: TO entre depósitos\nconserva lote, venc. y segmento\n(inventory detail obligatorio)'),
    'n_fin':   dict(lane='cost', col=8, slot=0, kind='note', text='Contabilidad: reporte por\nsegmento de aduana cuadra con\nIR porque está en cada línea'),
}

# (from, to, label) — flechas; label opcional
EDGES = [
    ('n_plan', 'tx_pr', ''), ('tx_pr', 'n_po', ''), ('n_po', 'tx_po', ''), ('tx_po', 'n_conf', ''),
    ('n_conf', 'n_ship', ''), ('n_ship', 'n_inb', ''), ('n_inb', 'tx_inb', ''),
    ('n_inb', 'n_adu', ''), ('n_adu', 'n_adu2', ''), ('n_adu2', 'k2', ''),
    ('k2', 'n_lc', ''), ('n_lc', 'tx_lc', ''), ('tx_lc', 'n_rec', ''),
    ('n_rec', 'tx_ir', ''), ('tx_ir', 'n_qa', ''), ('n_qa', 'tx_st', ''),
    ('tx_st', 'n_vb', ''), ('n_vb', 'tx_vb', ''), ('tx_vb', 'n_o2c', ''), ('n_o2c', 'tx_o2c', ''),
    ('k1', 'tx_po', ''), ('k3', 'tx_inb', ''), ('k4', 'tx_lc', ''), ('k5', 'tx_ir', ''), ('k6', 'tx_st', ''), ('k7', 'tx_vb', ''), ('k8', 'tx_o2c', ''),
]

COLORS = {
    'task': ('#e8f1fb', '#2b6cb0'),
    'tx':   ('#fff4d6', '#b7791f'),
    'ctl':  ('#fde8e8', '#c53030'),
    'note': ('#f0f0f0', '#718096'),
}

lane_index = {k: i for i, (k, _) in enumerate(LANES)}
W = LANE_LABEL_W + COL_W * len(PHASES) + 20
H = TITLE_H + HEADER_H + LANE_H * len(LANES) + LEGEND_H


def node_box(n):
    li = lane_index[n['lane']]
    x = LANE_LABEL_W + n['col'] * COL_W + PAD
    y0 = TITLE_H + HEADER_H + li * LANE_H
    if n['slot'] == 0:
        y = y0 + (LANE_H - 2 * NODE_H - 10) / 2 if any(m['lane'] == n['lane'] and m['col'] == n['col'] and m['slot'] == 1 for m in NODES.values()) else y0 + (LANE_H - NODE_H) / 2
    else:
        y = y0 + (LANE_H - 2 * NODE_H - 10) / 2 + NODE_H + 10
    return x, y, NODE_W, NODE_H


def esc(s):
    return html.escape(s, quote=True)


def text_lines(x, y, w, h, text, size=10.5, weight='normal', fill='#1a202c'):
    lines = text.split('\n')
    lh = size * 1.25
    total = lh * len(lines)
    ty = y + (h - total) / 2 + size
    out = []
    for i, ln in enumerate(lines):
        out.append(f'<text x="{x + w / 2:.1f}" y="{ty + i * lh:.1f}" text-anchor="middle" font-size="{size}" font-weight="{weight}" fill="{fill}">{esc(ln)}</text>')
    return '\n'.join(out)


def draw_node(key, n):
    x, y, w, h = node_box(n)
    fill, stroke = COLORS[n['kind']]
    out = []
    if n['kind'] == 'ctl':
        # hexágono para controles
        d = 10
        pts = f'{x + d},{y} {x + w - d},{y} {x + w},{y + h / 2} {x + w - d},{y + h} {x + d},{y + h} {x},{y + h / 2}'
        out.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    elif n['kind'] == 'tx':
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
        out.append(f'<rect x="{x}" y="{y}" width="6" height="{h}" fill="{stroke}"/>')
    elif n['kind'] == 'note':
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.2" stroke-dasharray="4 3"/>')
    else:
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    out.append(text_lines(x, y, w, h, n['text'], size=9.6 if n['kind'] != 'ctl' else 9.2, fill='#1a202c'))
    return '\n'.join(out)


def center(n):
    x, y, w, h = node_box(n)
    return x + w / 2, y + h / 2


def edge(a, b, label):
    na, nb = NODES[a], NODES[b]
    ax, ay, aw, ah = node_box(na)
    bx, by, bw, bh = node_box(nb)
    out = []
    if na['col'] == nb['col']:
        # vertical dentro de la misma columna
        x = ax + aw / 2 + (12 if na['kind'] == 'ctl' or nb['kind'] == 'ctl' else 0)
        if ay < by:
            y1, y2 = ay + ah, by
        else:
            y1, y2 = ay, by + bh
        dash = ' stroke-dasharray="3 3"' if na['kind'] == 'ctl' else ''
        out.append(f'<line x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}" stroke="#4a5568" stroke-width="1.3" marker-end="url(#arrow)"{dash}/>')
        if label:
            out.append(f'<text x="{x + 5:.1f}" y="{(y1 + y2) / 2:.1f}" font-size="9" fill="#4a5568">{esc(label)}</text>')
    else:
        # sale por la derecha, codo, entra por la izquierda
        x1, y1 = ax + aw, ay + ah / 2
        x2, y2 = bx, by + bh / 2
        xm = x1 + (x2 - x1) / 2
        out.append(f'<polyline points="{x1:.1f},{y1:.1f} {xm:.1f},{y1:.1f} {xm:.1f},{y2:.1f} {x2:.1f},{y2:.1f}" fill="none" stroke="#4a5568" stroke-width="1.3" marker-end="url(#arrow)"/>')
        if label:
            out.append(f'<text x="{xm + 4:.1f}" y="{(y1 + y2) / 2 - 4:.1f}" font-size="9" fill="#4a5568">{esc(label)}</text>')
    return '\n'.join(out)


svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">',
       '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#4a5568"/></marker></defs>',
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
       f'<text x="{LANE_LABEL_W}" y="30" font-size="20" font-weight="bold" fill="#1a202c">Andina Retail · P2P → O2C de importación (AR · CO · MX) · un proceso, variantes por país</text>',
       f'<text x="{LANE_LABEL_W}" y="52" font-size="11.5" fill="#4a5568">Objetivo: que costo total de importación, identificador aduanero, lote de fabricación y vencimiento lleguen a picking, factura electrónica y trazabilidad. Controles K1–K9 frenan donde se indica; K5 es el único que frena la entrada de stock.</text>']

# fases
for i, p in enumerate(PHASES):
    x = LANE_LABEL_W + i * COL_W
    svg.append(f'<rect x="{x}" y="{TITLE_H}" width="{COL_W}" height="{HEADER_H}" fill="#2d3748" stroke="#ffffff"/>')
    svg.append(f'<text x="{x + COL_W / 2}" y="{TITLE_H + HEADER_H / 2 + 4}" text-anchor="middle" font-size="12" font-weight="bold" fill="#ffffff">{esc(p)}</text>')
# carriles
for i, (k, label) in enumerate(LANES):
    y = TITLE_H + HEADER_H + i * LANE_H
    fill = '#f7fafc' if i % 2 == 0 else '#ffffff'
    if k == 'ns':
        fill = '#fffbea'
    svg.append(f'<rect x="{LANE_LABEL_W}" y="{y}" width="{COL_W * len(PHASES)}" height="{LANE_H}" fill="{fill}" stroke="#cbd5e0"/>')
    svg.append(f'<rect x="0" y="{y}" width="{LANE_LABEL_W}" height="{LANE_H}" fill="#e2e8f0" stroke="#cbd5e0"/>')
    svg.append(text_lines(0, y, LANE_LABEL_W, LANE_H, label, size=11.5, weight='bold', fill='#2d3748'))
# flechas primero (debajo de los nodos)
for a, b, l in EDGES:
    svg.append(edge(a, b, l))
for k, n in NODES.items():
    svg.append(draw_node(k, n))

# leyenda + variantes
ly = TITLE_H + HEADER_H + LANE_H * len(LANES) + 14
items = [('task', 'Paso (departamento)'), ('tx', 'Transacción / registro NetSuite'), ('ctl', 'Punto de control (dónde frena)'), ('note', 'Nota de proceso')]
x = LANE_LABEL_W
for kind, lab in items:
    f, s = COLORS[kind]
    svg.append(f'<rect x="{x}" y="{ly}" width="26" height="16" rx="3" fill="{f}" stroke="{s}" stroke-width="1.4"/>')
    svg.append(f'<text x="{x + 32}" y="{ly + 12}" font-size="11" fill="#1a202c">{esc(lab)}</text>')
    x += 250
variants = [
    'Variantes por país (misma secuencia, distintos datos): identificador aduanero → MX pedimento (15 dígitos, va al CFDI vía maestro de pedimentos) · AR despacho de importación SIM (sólo segmento/trazabilidad) · CO declaración de importación DIAN (sólo segmento/trazabilidad).',
    'Landed cost (categorías obligatorias) → MX: flete int., seguro, agente aduanal, IGI, DTA · AR: flete int., seguro, despachante, derechos de importación, tasa estadística · CO: flete int., seguro, agencia de aduanas, arancel. IVA/percepciones de importación NO son costo (crédito fiscal).',
    'Regulatorio → MX COFEPRIS · AR ANMAT (trazabilidad de productos médicos) · CO INVIMA. Lote de inventario: regulados = lote de fabricación (vencimiento en el inventory number); MX no regulados = pedimento (práctica actual). El maestro de pedimentos se alimenta desde el Item Receipt (ítem + depósito + lote → pedimento) para ambos casos.',
]
for i, v in enumerate(variants):
    svg.append(f'<text x="{LANE_LABEL_W}" y="{ly + 36 + i * 17}" font-size="10.5" fill="#2d3748">{esc(v)}</text>')
svg.append('</svg>')
open(OUT, 'w', encoding='utf-8').write('\n'.join(svg))
print('wrote', OUT, W, 'x', H)
