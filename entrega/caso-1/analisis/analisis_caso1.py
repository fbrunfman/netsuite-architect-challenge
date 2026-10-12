#!/usr/bin/env python3
"""Caso 1 · Inbound MX — análisis de los CSV de data/.
Uso: python3 analisis_caso1.py [ruta a caso-1-inbound-mx/data]
Imprime la evidencia que respalda entrega/caso-1/nota.md.
"""
import csv, sys, os, re
from collections import defaultdict, Counter

DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '../../../caso-1-inbound-mx/data')

def load(name):
    with open(os.path.join(DATA, name), newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

ships = {r['shipment_id']: r for r in load('inbound_shipments.csv')}
lcs = defaultdict(list)
for r in load('landed_costs.csv'): lcs[r['shipment_id']].append(r)
irs = {r['receipt_id']: r for r in load('item_receipts.csv')}
lines = load('receipt_lines.csv')
pm = load('pedimento_master.csv')
inv = load('invoices_mx.csv')

PED = re.compile(r'^\d{15}$')
sec = lambda t: print('\n' + '=' * 78 + '\n' + t + '\n' + '=' * 78)

# ---------------------------------------------------------------- 1. recepciones
sec('1. Recepciones vs. estado del embarque AL MOMENTO de recibir')
print(f"{'IR':<12}{'INBSHIP':<16}{'source':<30}{'flow':<14}{'recv':<12}{'lc_status':<10}{'lc_conf':<12}{'lc rows≤recv':<13}{'lc total'}")
bad = []
for ir in irs.values():
    s = ships[ir['shipment_id']]
    rows = lcs[ir['shipment_id']]
    rows_before = [r for r in rows if r['loaded_date'] <= ir['received_date']]
    conf_after = s['lc_confirmed_date'] and s['lc_confirmed_date'] > ir['received_date']
    flag = ''
    if s['lc_status'] != 'Confirmed': flag = 'LC_NOT_CONFIRMED'
    elif conf_after: flag = 'CONFIRMED_AFTER_RECEIPT'
    elif len(rows_before) < len(rows): flag = 'LC_ROWS_AFTER_RECEIPT'
    if flag: bad.append((ir, s, flag))
    print(f"{ir['receipt_number']:<12}{s['shipment_number']:<16}{ir['source']:<30}{ir['receiving_flow']:<14}{ir['received_date']:<12}"
          f"{s['lc_status']:<10}{(s['lc_confirmed_date'] or '-'):<12}{len(rows_before):>3}/{len(rows):<9}{flag}")
print('\nRecepciones que NO debieron pasar el gate (R1/R2):')
for ir, s, flag in bad:
    print(f"  {ir['receipt_number']} ({ir['source']}, {ir['receiving_flow']}): {flag}; LC {s['lc_status']} conf={s['lc_confirmed_date'] or '-'} recv={ir['received_date']}")
print('\nPor source:', Counter(ir['source'] for ir, _, _ in bad))
print('Total recepciones por source:', Counter(r['source'] for r in irs.values()))
print('Total recepciones por flow:', Counter(r['receiving_flow'] for r in irs.values()))

# ---------------------------------------------------------------- 2. landed cost incompleto
sec('2. Landed cost cargado DESPUÉS de la recepción (inventario entró sin costo completo)')
tot_late = 0
for sid, s in ships.items():
    ir = next((i for i in irs.values() if i['shipment_id'] == sid), None)
    if not ir: continue
    late = [r for r in lcs[sid] if r['loaded_date'] > ir['received_date']]
    if late or not lcs[sid]:
        amt = {}
        for r in late: amt[r['currency']] = amt.get(r['currency'], 0) + float(r['amount'])
        tot_late += len(late)
        print(f"  {s['shipment_number']} -> {ir['receipt_number']} ({ir['source']}): {len(late)}/{len(lcs[sid])} filas LC posteriores a recv "
              f"{ir['received_date']}: {', '.join(r['cost_category']+' '+r['loaded_date'] for r in late) or 'SIN LANDED COST'}  {amt}")
print(f"\nFilas de landed cost posteriores a la recepción: {tot_late}")
print('Ventas facturadas antes de tener el LC completo (lote = pedimento del embarque):')
for sid, s in ships.items():
    ir = next((i for i in irs.values() if i['shipment_id'] == sid), None)
    if not ir: continue
    cutoff = s['lc_confirmed_date'] or '9999-12-31'
    sold = [i for i in inv if i['lot'] == s['customs_number'] and i['invoice_date'] < cutoff]
    if sold: print(f"  {s['shipment_number']} (LC {s['lc_status']} conf={s['lc_confirmed_date'] or '-'}): {len(sold)} facturas, {sum(int(i['qty']) for i in sold)} unidades")
cats = Counter(r['cost_category'] for rows in lcs.values() for r in rows)
print('Categorías de LC (por embarque completo se esperan 5):', dict(cats))
for sid, rows in lcs.items():
    if len(rows) < 5: print(f"  {ships[sid]['shipment_number']}: sólo {len(rows)} categorías -> {[r['cost_category'] for r in rows]}")
print('Embarques sin ninguna fila LC:', [ships[s]['shipment_number'] for s in ships if not lcs[s]])

# ---------------------------------------------------------------- 3. lotes / segmento
sec('3. Líneas de recepción: lote ≠ pedimento, segmento de aduana vacío, datos regulados')
by_ir = defaultdict(list)
for l in lines: by_ir[l['receipt_id']].append(l)
stats = Counter()
problem_irs = defaultdict(list)
for rid, ls in by_ir.items():
    ir = irs[rid]; s = ships[ir['shipment_id']]; ped = s['customs_number']
    for l in ls:
        stats['lines'] += 1
        if l['lot'] != ped:
            stats['lot_mismatch'] += 1; problem_irs[rid].append(f"L{l['line']} lot={l['lot']!r}")
        if not PED.match(l['lot'] or ''): stats['lot_not_15_digits'] += 1
        if not l['customs_segment']:
            stats['line_segment_empty'] += 1; problem_irs[rid].append(f"L{l['line']} seg vacío")
        elif l['customs_segment'] != ped: stats['line_segment_wrong'] += 1
        if l['regulated'] == 'Y' and (not l['mfg_lot'] or not l['expiry_date']):
            stats['regulated_missing_mfg_or_expiry'] += 1; problem_irs[rid].append(f"L{l['line']} regulado sin mfg/expiry")
print(dict(stats))
print('\nRecepciones con problemas de línea:')
for rid, probs in problem_irs.items():
    ir = irs[rid]
    print(f"  {ir['receipt_number']} ({ir['source']}, {ir['receiving_flow']}, hdr seg={ir['customs_segment'] or 'VACÍO'}): {len(probs)} -> {probs[:4]}{' ...' if len(probs) > 4 else ''}")
print('\nSegmento de cabecera vacío:', [i['receipt_number'] for i in irs.values() if not i['customs_segment']])
print('Problemas de línea por flow:', Counter(irs[r]['receiving_flow'] for r in problem_irs))
print('Problemas de línea por source:', Counter(irs[r]['source'] for r in problem_irs))
print('\nPatrones de lote que no son el pedimento:')
for l in lines:
    ped = ships[irs[l['receipt_id']]['shipment_id']]['customs_number']
    if l['lot'] != ped: print(f"  {irs[l['receipt_id']]['receipt_number']} L{l['line']} item={l['item_id']} lot={l['lot']!r} pedimento={ped} mfg_lot={l['mfg_lot']!r}")

# ---------------------------------------------------------------- 4. maestro de pedimentos
sec('4. Maestro de pedimentos vs. líneas recibidas')
pm_keys = {(r['item_id'], r['location'], r['lot']): r for r in pm}
missing = []
for l in lines:
    ir = irs[l['receipt_id']]
    k = (l['item_id'], ir['location'], l['lot'])
    if k not in pm_keys: missing.append((ir, l))
print(f"Líneas recibidas: {len(lines)}; filas en maestro: {len(pm)}; líneas SIN fila en maestro: {len(missing)}")
print('  por recepción:', Counter(ir['receipt_number'] for ir, _ in missing))
print('  por flow:', Counter(ir['receiving_flow'] for ir, _ in missing), ' por source:', Counter(ir['source'] for ir, _ in missing))
qty_missing = sum(int(l['qty']) for _, l in missing)
print(f"  unidades sin pedimento en maestro: {qty_missing}")
bad_pm = [r for r in pm if r['lot'] != r['pedimento'] or not PED.match(r['pedimento'])]
print('Filas del maestro con lot≠pedimento o pedimento inválido:', len(bad_pm), bad_pm[:3])
# qty del maestro vs qty recibida
qdiff = []
for (item, loc, lot), r in pm_keys.items():
    recv = sum(int(l['qty']) for l in lines if l['item_id'] == item and l['lot'] == lot and irs[l['receipt_id']]['location'] == loc)
    if recv != int(r['qty_received']): qdiff.append((item, loc, lot, recv, r['qty_received']))
print('Filas del maestro con qty distinta a lo recibido:', len(qdiff), qdiff[:5])

# ---------------------------------------------------------------- 5. CFDI
sec('5. CFDI timbrados sin número de pedimento')
no_ped = [i for i in inv if not i['numero_pedimento']]
print(f"Facturas: {len(inv)}; sin numero_pedimento: {len(no_ped)} ({100*len(no_ped)/len(inv):.1f}%); unidades: {sum(int(i['qty']) for i in no_ped)}")
print('  por mes:', Counter(i['invoice_date'][:7] for i in no_ped))
lot_to_ir = defaultdict(set)
for l in lines: lot_to_ir[(l['item_id'], l['lot'])].add(l['receipt_id'])
src = Counter()
for i in no_ped:
    rids = lot_to_ir.get((i['item_id'], i['lot']), set())
    for rid in rids: src[(irs[rid]['receipt_number'], irs[rid]['receiving_flow'], irs[rid]['source'])] += 1
    if not rids: src[('lote no recibido: ' + i['lot'], '', '')] += 1
print('  origen (recepción del lote facturado):')
for k, v in src.most_common(): print('   ', k, v)
mism = [i for i in inv if i['numero_pedimento'] and i['numero_pedimento'] != i['lot']]
print('Facturas con pedimento ≠ lote:', len(mism))
print('Lotes facturados que no son 15 dígitos:', Counter(i['lot'] for i in inv if not PED.match(i['lot'])))
# ¿las facturas sin pedimento son exactamente las de líneas sin fila en maestro?
miss_keys = {(l['item_id'], l['lot']) for _, l in missing}
print('Facturas sin pedimento cuyo (item,lot) NO está en el maestro:', sum(1 for i in no_ped if (i['item_id'], i['lot']) in miss_keys), 'de', len(no_ped))
print('Facturas CON pedimento cuyo (item,lot) NO está en el maestro:', sum(1 for i in inv if i['numero_pedimento'] and (i['item_id'], i['lot']) in miss_keys))

# ---------------------------------------------------------------- 6. segmento contable
sec('6. Reporte por segmento de aduana vs. recibido (cabecera vs. línea)')
hdr = Counter(); lin = Counter()
for l in lines:
    ir = irs[l['receipt_id']]; q = int(l['qty'])
    hdr[ir['customs_segment'] or '(vacío)'] += q
    lin[l['customs_segment'] or '(vacío)'] += q
print('Unidades recibidas con segmento de LÍNEA vacío:', lin['(vacío)'], 'de', sum(lin.values()))
print('Unidades recibidas con segmento de CABECERA vacío:', hdr['(vacío)'])
diff = [(k, hdr[k], lin.get(k, 0)) for k in hdr if hdr[k] != lin.get(k, 0)]
print('Segmentos cuya suma por cabecera ≠ suma por línea:', len(diff))
for k, h, l_ in diff: print(f"  {k}: cabecera {h} vs línea {l_}")
