#!/usr/bin/env python3
"""Caso 2 · Marketplace backorder — análisis de los CSV de data/ (corte 30-09-2026).
Uso: python3 analisis_caso2.py [ruta a caso-2-marketplace-backorder/data]
Imprime las cifras citadas en diagnostico.md. Sin dependencias externas.
"""
import csv, sys, os
from collections import Counter, defaultdict
from datetime import datetime, date

DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '../../../caso-2-marketplace-backorder/data')
L = lambda f: list(csv.DictReader(open(os.path.join(DATA, f), encoding='utf-8')))
sec = lambda t: print('\n' + '=' * 78 + '\n' + t + '\n' + '=' * 78)

mo = {o['mp_order_id']: o for o in L('marketplace_orders.csv')}
so = L('sales_orders.csv'); sl = {l['so_id']: l for l in L('so_lines.csv')}
to = L('transfer_orders.csv'); inv = L('inventory_snapshot.csv'); log = L('ipaas_log.csv')
mp = {m['sku_marketplace']: m['item_id'] for m in L('item_mapping.csv')}
invk = {(i['item_id'], i['location']): i for i in inv}
so_by_mp = defaultdict(list)
for s in so: so_by_mp[s['mp_order_id']].append(s)
for v in so_by_mp.values(): v.sort(key=lambda s: s['created_at'])
logby = defaultdict(list)
for l in log: logby[l['mp_order_id']].append(l)
tob = defaultdict(list)
for t in to: tob[t['item_id']].append(t)
q = lambda s: int(sl[s['so_id']]['qty']); bo_q = lambda s: int(sl[s['so_id']]['qty_backordered'])

sec('0. Universo')
print('Órdenes marketplace:', len(mo), dict(Counter(o['status'] for o in mo.values())), dict(Counter(o['fulfillment_type'] for o in mo.values())))
print('Sales Orders:', len(so), dict(Counter(s['status'] for s in so)))
print('SO por estado y depósito:', dict(Counter((s['status'], s['location']) for s in so)))
print('Consistencia: depósito de la SO siempre coincide con fulfillment_type (marketplace→AR-MKP-FC, own→AR-CD-CENTRAL):',
      all((mo[s['mp_order_id']]['fulfillment_type'] == 'marketplace') == (s['location'] == 'AR-MKP-FC') for s in so))
print('Consistencia: qty e ítem de la línea = orden del marketplace:',
      all(q(s) == int(mo[s['mp_order_id']]['qty']) and sl[s['so_id']]['item_id'] == mp.get(mo[s['mp_order_id']]['sku_marketplace']) for s in so))

sec('1. "Entregadas sin facturar": qué ve Cuentas a Cobrar')
deliv = [o for o in mo.values() if o['status'] == 'delivered']
unb = [o for o in deliv if not any(s['status'] == 'Billed' for s in so_by_mp.get(o['mp_order_id'], []))]
print(f'Órdenes entregadas: {len(deliv)}; sin SO facturada en NetSuite: {len(unb)}')
print('  por situación en NetSuite (primera SO):', dict(Counter('SIN SO' if o['mp_order_id'] not in so_by_mp else so_by_mp[o['mp_order_id']][0]['status'] for o in unb)))
dbo_all = [s for s in so if bo_q(s) > 0 and mo[s['mp_order_id']]['status'] == 'delivered']
print(f'SO en backorder cuya orden está entregada (lo que AR cuenta como "más de mil"): {len(dbo_all)} SO, {sum(bo_q(s) for s in dbo_all)} unidades')

sec('2. Causa A · Duplicados por reintento tras TIMEOUT (sin idempotencia)')
dups = {k for k, v in so_by_mp.items() if len(v) > 1}
extra = [s for k in dups for s in so_by_mp[k][1:]]
t_orders = {l['mp_order_id'] for l in log if l['error_code'] == 'TIMEOUT'}
print(f'Órdenes con más de una SO: {len(dups)}; SO sobrantes: {len(extra)} -> {dict(Counter(s["status"] for s in extra))}')
print('En TODAS, #SO = #TIMEOUT + 1:', all(len(so_by_mp[k]) == sum(1 for l in logby[k] if l['error_code'] == 'TIMEOUT') + 1 for k in dups))
print(f'Órdenes con TIMEOUT en el log: {len(t_orders)}; de ellas duplicadas: {sum(1 for k in t_orders if k in dups)} '
      f'({100*sum(1 for k in t_orders if k in dups)/len(t_orders):.0f} %): el request que "falló" por timeout sí creó la SO en NetSuite')
print('Primera SO de cada orden duplicada:', dict(Counter(so_by_mp[k][0]['status'] for k in dups)), '-> la venta real ya está facturada')
print('SO duplicadas que comprometen stock:', sum(1 for s in extra if int(sl[s['so_id']]['qty_committed']) > 0), '| duplicadas facturadas (doble factura):', sum(1 for s in extra if s['status'] in ('Billed', 'Pending Billing')))
worst = max(dups, key=lambda k: len(so_by_mp[k])); print(f'Peor caso: orden {worst} con {len(so_by_mp[worst])} SO')
print('Duplicadas en backorder que AR cuenta como entregadas sin facturar:', sum(1 for s in dbo_all if s['mp_order_id'] in dups))
rl = {l['mp_order_id'] for l in log if l['error_code'] == 'RATE_LIMIT'}
print(f'RATE_LIMIT (429 concurrencia SuiteTalk): {sum(1 for l in log if l["error_code"]=="RATE_LIMIT")} intentos en {len(rl)} órdenes; duplicados por 429: {sum(1 for k in rl if k in dups)}; todas terminaron OK')
print('Timeouts por hora:', dict(sorted(Counter(l['ts'][11:13] for l in log if l['error_code'] == 'TIMEOUT').items())))
print('Timeouts por día (pico):', sorted(Counter(l['ts'][:10] for l in log if l['error_code'] == 'TIMEOUT').items(), key=lambda x: -x[1])[:3])
gaps = Counter()
for k in dups:
    ts = [datetime.strptime(s['created_at'], '%Y-%m-%d %H:%M') for s in so_by_mp[k]]
    for a, b in zip(ts, ts[1:]): gaps[int((b - a).total_seconds() // 60)] += 1
print('Minutos entre SO duplicadas (política de reintento):', dict(gaps))

sec('3. Causa B · Órdenes que nunca entraron: SKU sin mapear (ITEM_NOT_FOUND)')
inf = {l['mp_order_id'] for l in log if l['error_code'] == 'ITEM_NOT_FOUND'}
print(f'Órdenes con ITEM_NOT_FOUND: {len(inf)}; con SO: {sum(1 for k in inf if k in so_by_mp)}; intentos por orden: {dict(Counter(sum(1 for l in logby[k] if l["error_code"]=="ITEM_NOT_FOUND") for k in inf))} y se abandona')
print('Estado marketplace:', dict(Counter(mo[k]['status'] for k in inf)), '| fulfillment:', dict(Counter(mo[k]['fulfillment_type'] for k in inf)), '| unidades:', sum(int(mo[k]['qty']) for k in inf))
print('SKUs sin mapear:', len({mo[k]['sku_marketplace'] for k in inf}), dict(Counter(mo[k]['sku_marketplace'] for k in inf)))
print('Primera / última orden afectada:', min(mo[k]['created_at'] for k in inf), '/', max(mo[k]['created_at'] for k in inf))

sec('4. Backorders reales (sin duplicados): por qué no hay stock en NetSuite')
bo = [s for s in so if bo_q(s) > 0 and s['mp_order_id'] not in dups]
pend = [t for t in to if t['status'] != 'Received']; pend_items = {t['item_id'] for t in pend}
def cat(s):
    l = sl[s['so_id']]; i = invk[(l['item_id'], s['location'])]
    if l['item_id'] in pend_items: return 'C_TO_en_transito'
    if int(i['available']) >= bo_q(s): return 'D_stock_disponible_sin_comprometer'
    if int(i['on_hand']) == 0 and int(i['in_transit']) == 0: return 'E_sin_stock_en_NetSuite'
    return 'otro'
C = Counter((mo[s['mp_order_id']]['status'], s['location'], cat(s)) for s in bo)
U = Counter(); 
for s in bo: U[(mo[s['mp_order_id']]['status'], s['location'], cat(s))] += bo_q(s)
print(f'SO reales en backorder: {len(bo)} ({sum(bo_q(s) for s in bo)} unidades)')
for k, v in sorted(C.items(), key=lambda x: -x[1]): print(f'   {k}: {v} SO, {U[k]} unidades')

print('\nC · Transfer Orders parcialmente recibidas (stock físicamente en el marketplace, en tránsito en NetSuite):')
for t in pend: print(f"   {t['to_id']} {t['item_id']} creada {t['created_date']} enviadas {t['qty_shipped']} recibidas {t['qty_received']} faltan {int(t['qty_shipped'])-int(t['qty_received'])}")
print(f'   {len(pend)} TO, {sum(int(t["qty_shipped"])-int(t["qty_received"]) for t in pend)} unidades en tránsito desde hace {(date(2026,9,30)-max(date.fromisoformat(t["created_date"]) for t in pend)).days}–{(date(2026,9,30)-min(date.fromisoformat(t["created_date"]) for t in pend)).days} días')
cbo = [s for s in bo if cat(s) == 'C_TO_en_transito']
print(f'   backorders entregados que esperan ese stock: {len(cbo)} SO / {sum(bo_q(s) for s in cbo)} unidades; cubiertos por lo en tránsito: '
      f'{all(sum(bo_q(x) for x in cbo if sl[x["so_id"]]["item_id"]==it) <= int(invk[(it,"AR-MKP-FC")]["in_transit"]) for it in pend_items)}')
lag = Counter((date.fromisoformat(t['received_date']) - date.fromisoformat(t['created_date'])).days for t in to if t['status'] == 'Received')
print('   días creación→recepción de las TO recibidas:', dict(lag))

print('\nD · Stock disponible en el depósito pero línea no comprometida:')
anc = [s for s in bo if cat(s) == 'D_stock_disponible_sin_comprometer']
items_anc = {sl[s['so_id']]['item_id'] for s in anc}
after = all(any(t['status'] == 'Received' and t['to_location'] == s['location'] and t['received_date'] >= s['created_at'][:10] for t in tob[sl[s['so_id']]['item_id']]) for s in anc)
print(f'   {len(anc)} SO / {sum(bo_q(s) for s in anc)} unidades en {len(items_anc)} ítems; en el 100 % la TO que trajo el stock se recibió DESPUÉS de crear la SO: {after}')
print('   disponible hoy en AR-MKP-FC para esos ítems:', sum(int(invk[(it, 'AR-MKP-FC')]['available']) for it in items_anc), 'unidades (sobra para comprometer todo)')
print('   el snapshot es coherente: committed = suma de qty_committed de SO abiertas en todos los ítem/depósito:',
      all(int(i['committed']) == sum(int(sl[s['so_id']]['qty_committed']) for s in so if s['status'] == 'Pending Fulfillment' and (sl[s['so_id']]['item_id'], s['location']) == k) for k, i in invk.items()))

print('\nE · Sin stock en NetSuite en ningún depósito ni en tránsito:')
e = [s for s in bo if cat(s) == 'E_sin_stock_en_NetSuite']
ed = [s for s in e if mo[s['mp_order_id']]['status'] == 'delivered']; ep = [s for s in e if mo[s['mp_order_id']]['status'] == 'paid']
print(f'   entregadas por el marketplace desde AR-MKP-FC: {len(ed)} SO / {sum(bo_q(s) for s in ed)} unidades, {len({sl[s["so_id"]]["item_id"] for s in ed})} ítems -> el marketplace vendió stock que NetSuite no tiene (diferencia de inventario en el FC)')
print(f'   pagadas, despacho propio desde AR-CD-CENTRAL: {len(ep)} SO / {sum(bo_q(s) for s in ep)} unidades, {len({sl[s["so_id"]]["item_id"] for s in ep})} ítems -> quiebre de stock real, no es tema de facturación')
print('   ítems sin TO en el período:', sum(1 for it in {sl[s['so_id']]['item_id'] for s in e} if not tob[it]), 'de', len({sl[s['so_id']]['item_id'] for s in e}))

sec('5. Lo que NO es problema (pipeline normal)')
pb = [s for s in so if s['status'] == 'Pending Billing']
f = lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M'); cut = datetime(2026, 9, 30, 23, 59)
print(f'Pending Billing: {len(pb)}, todas entregadas y despachadas, entregadas hace {min((cut-f(mo[s["mp_order_id"]]["delivered_at"])).total_seconds()/3600 for s in pb):.0f}–{max((cut-f(mo[s["mp_order_id"]]["delivered_at"])).total_seconds()/3600 for s in pb):.0f} h -> cola normal de facturación')
pfc = [s for s in so if s['status'] == 'Pending Fulfillment' and bo_q(s) == 0]
print(f'Pending Fulfillment comprometidas (sin backorder): {len(pfc)} -> {dict(Counter(mo[s["mp_order_id"]]["status"] for s in pfc))}; entregadas pendientes de despacho en NS: {sum(1 for s in pfc if mo[s["mp_order_id"]]["status"]=="delivered")}')

sec('6. Resumen para el diagnóstico')
tot = len(unb)
rows = [
 ('Pending Billing: despachadas, en cola de facturación (normal)', len(pb)),
 ('Comprometidas, entregadas, falta correr el despacho', sum(1 for s in pfc if mo[s['mp_order_id']]['status'] == 'delivered')),
 ('D · stock disponible, línea sin comprometer', len([s for s in anc if mo[s['mp_order_id']]['status'] == 'delivered'])),
 ('C · stock en TO parcialmente recibida', len(cbo)),
 ('E · stock inexistente en NetSuite (FC)', len(ed)),
 ('B · sin SO: SKU sin mapear', len(inf)),
]
for n, v in rows: print(f'   {v:>5}  {100*v/tot:5.1f} %  {n}')
print(f'   {sum(v for _, v in rows):>5}  total = {tot}')
print(f'   + {sum(1 for s in dbo_all if s["mp_order_id"] in dups)} SO duplicadas en backorder (A) que inflan el conteo de AR y NO deben facturarse')
