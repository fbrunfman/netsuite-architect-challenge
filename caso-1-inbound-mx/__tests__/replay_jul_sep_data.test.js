// Replays the 48 item receipts of Jul–Sep 2026 (data/) through the fixed gate, reconstructing what the
// shipment looked like ON the receipt date. It documents the incident: 8 receipts should have been blocked.
const query = require('N/query');
const runtime = require('N/runtime');
const gate = require('../src/FileCabinet/SuiteScripts/acme_inbship/acme_itemreceipt_gate_ue');
const { fakeRecord, ctx } = require('./helpers/fake');
const { readCsv } = require('./helpers/csv');

const CONFIRMED = '3', LOADED = '2', PENDING = '1';
const ships = Object.fromEntries(readCsv('inbound_shipments.csv').map((s) => [s.shipment_id, s]));
const landed = readCsv('landed_costs.csv');
const receipts = readCsv('item_receipts.csv');
const lines = readCsv('receipt_lines.csv');

const factsOn = (s, date) => {
  const rows = landed.filter((l) => l.shipment_id === s.shipment_id && l.loaded_date <= date).length;
  const confirmed = s.lc_confirmed_date && s.lc_confirmed_date <= date;
  return { shipmentnumber: s.shipment_number, lcrows: rows, lcstatus: confirmed ? CONFIRMED : (rows ? LOADED : PENDING), customsno: s.customs_number };
};

const recordFor = (ir) => fakeRecord({
  body: { inboundshipment: ir.shipment_id, cseg_acme_customs: ir.customs_segment || null, subsidiary: '2' },
  lines: lines.filter((l) => l.receipt_id === ir.receipt_id).map((l) => ({
    item: l.item_id, itemreceive: true, quantity: Number(l.qty), cseg_acme_customs: l.customs_segment || null,
    inventorydetail: [{ receiptinventorynumber: l.lot, quantity: Number(l.qty) }],
  })),
});

const run = (ir) => {
  jest.spyOn(query, 'runSuiteQL').mockReturnValue({ asMappedResults: () => [factsOn(ships[ir.shipment_id], ir.received_date)] });
  try { gate.beforeSubmit(ctx(recordFor(ir))); return null; } catch (e) { return e.name; }
};

beforeEach(() => { jest.restoreAllMocks(); runtime.__setParams({ custscript_acme_gate_lc_confirmed_id: CONFIRMED }); });

test('the fixed gate blocks exactly the receipts behind the September findings', () => {
  const blocked = Object.fromEntries(receipts.map((ir) => [ir.receipt_number, run(ir)]).filter(([, e]) => e));
  expect(blocked).toEqual({
    // Costs: received by the bulk job while landed cost was missing / not yet confirmed
    'IR-MX-00010': 'ACME_GATE_NO_LANDED_COST',
    'IR-MX-00017': 'ACME_GATE_NO_LANDED_COST',
    'IR-MX-00022': 'ACME_GATE_NO_LANDED_COST',
    'IR-MX-00038': 'ACME_GATE_NO_LANDED_COST',
    // Accounting: customs segment on the header but missing on some lines
    'IR-MX-00008': 'ACME_GATE_NO_CUSTOMS',
    'IR-MX-00011': 'ACME_GATE_NO_CUSTOMS',
    'IR-MX-00021': 'ACME_GATE_NO_CUSTOMS',
    'IR-MX-00044': 'ACME_GATE_NO_CUSTOMS',
  });
});

test('every receipt that got through the old gate was created by the bulk job or had line-only gaps', () => {
  const costBlocked = receipts.filter((ir) => run(ir) === 'ACME_GATE_NO_LANDED_COST');
  expect(costBlocked.map((ir) => ir.source)).toEqual(Array(4).fill('Receive Inbound Shipment job'));
  const segBlocked = receipts.filter((ir) => run(ir) === 'ACME_GATE_NO_CUSTOMS');
  expect(segBlocked.every((ir) => ir.customs_segment)).toBe(true); // header was set: the old header-only check passed
});

test('the 40 remaining receipts (incl. all direct-flow ones) pass: lot = pedimento and segments complete', () => {
  const passed = receipts.filter((ir) => run(ir) === null);
  expect(passed).toHaveLength(40);
  expect(passed.filter((ir) => ir.receiving_flow === 'direct')).toHaveLength(8);
});
