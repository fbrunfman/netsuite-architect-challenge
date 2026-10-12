const query = require('N/query');
const runtime = require('N/runtime');
const gate = require('../src/FileCabinet/SuiteScripts/acme_inbship/acme_itemreceipt_gate_ue');
const { fakeRecord, ctx } = require('./helpers/fake');

const facts = (f) => jest.spyOn(query, 'runSuiteQL').mockReturnValue({ asMappedResults: () => (f ? [f] : []) });
const PED = '264215269402249';
const ready = { shipmentnumber: 'INBSHIP-MX-0001', lcrows: 4, lcstatus: '3', customsno: PED };
const receipt = (body = {}, lines = [{ item: '10', itemreceive: true, cseg_acme_customs: '7' }]) =>
  fakeRecord({ body: { inboundshipment: '5001', cseg_acme_customs: '7', subsidiary: '2', ...body }, lines });
const thrown = (name) => expect.objectContaining({ name });
const params = (p = {}) => runtime.__setParams({ custscript_acme_gate_lc_confirmed_id: '3', ...p });

beforeEach(() => { jest.restoreAllMocks(); params(); });

// ---------------------------------------------------------------- behaviour that must not change
test('lets a ready shipment be received', () => {
  facts(ready);
  expect(() => gate.beforeSubmit(ctx(receipt()))).not.toThrow();
});

test('ignores receipts that do not come from an inbound shipment', () => {
  const spy = facts(ready);
  gate.beforeSubmit(ctx(fakeRecord({ body: {}, lines: [{ item: '10' }] })));
  expect(spy).not.toHaveBeenCalled();
});

test('only acts on create', () => {
  const spy = facts({ ...ready, lcrows: 0 });
  expect(() => gate.beforeSubmit(ctx(receipt(), 'edit'))).not.toThrow();
  expect(spy).not.toHaveBeenCalled();
});

test('finds the shipment on the lines when the header link is empty', () => {
  facts({ ...ready, lcrows: 0 });
  const rec = fakeRecord({ body: { cseg_acme_customs: '7' }, lines: [{ item: '10', inboundshipment: '5001' }] });
  expect(() => gate.beforeSubmit(ctx(rec))).toThrow(thrown('ACME_GATE_NO_LANDED_COST'));
});

test('blocks when the shipment has no landed cost rows', () => {
  facts({ ...ready, lcrows: 0 });
  expect(() => gate.beforeSubmit(ctx(receipt()))).toThrow(thrown('ACME_GATE_NO_LANDED_COST'));
});

test('blocks when landed cost is not confirmed', () => {
  facts({ ...ready, lcstatus: '2' });
  expect(() => gate.beforeSubmit(ctx(receipt()))).toThrow(thrown('ACME_GATE_LC_NOT_CONFIRMED'));
});

test('blocks when the shipment has no customs number', () => {
  facts({ ...ready, customsno: null });
  expect(() => gate.beforeSubmit(ctx(receipt()))).toThrow(thrown('ACME_GATE_NO_CUSTOMS'));
});

test('blocks when the receipt header has no customs segment', () => {
  facts(ready);
  expect(() => gate.beforeSubmit(ctx(receipt({ cseg_acme_customs: null })))).toThrow(thrown('ACME_GATE_NO_CUSTOMS'));
});

test('warn-only mode logs instead of blocking', () => {
  params({ custscript_acme_gate_enforce_lc: false });
  facts({ ...ready, lcrows: 0 });
  expect(() => gate.beforeSubmit(ctx(receipt()))).not.toThrow();
});

// ---------------------------------------------------------------- R4: customs segment on every line (bug found in Sep close)
describe('R4 customs segment on lines', () => {
  test('blocks when a received line has no customs segment even though the header has one', () => {
    facts(ready);
    const rec = receipt({}, [
      { item: '10', itemreceive: true, cseg_acme_customs: '7' },
      { item: '11', itemreceive: true, cseg_acme_customs: null },
    ]);
    expect(() => gate.beforeSubmit(ctx(rec))).toThrow(thrown('ACME_GATE_NO_CUSTOMS'));
    expect(() => gate.beforeSubmit(ctx(rec))).toThrow(/line\(s\) 2/);
  });

  test('ignores lines that are not being received (itemreceive unticked or quantity 0)', () => {
    facts(ready);
    const rec = receipt({}, [
      { item: '10', itemreceive: true, cseg_acme_customs: '7' },
      { item: '11', itemreceive: false, cseg_acme_customs: null },
      { item: '12', itemreceive: true, quantity: 0, cseg_acme_customs: null },
    ]);
    expect(() => gate.beforeSubmit(ctx(rec))).not.toThrow();
  });

  test('line segment rule follows the customs warn-only switch', () => {
    params({ custscript_acme_gate_enforce_customs: false });
    facts(ready);
    expect(() => gate.beforeSubmit(ctx(receipt({}, [{ item: '10', itemreceive: true, cseg_acme_customs: null }])))).not.toThrow();
  });
});

// ---------------------------------------------------------------- R5: lot = customs number (CFDI pedimento lookup is by lot)
describe('R5 lot = customs number', () => {
  const lotLine = (lot) => ({ item: '10', itemreceive: true, cseg_acme_customs: '7', inventorydetail: [{ receiptinventorynumber: lot, quantity: 5 }] });

  test('accepts lots equal to the pedimento (ignoring spaces in the customs number)', () => {
    facts({ ...ready, customsno: '26 42 1526 9402249' });
    expect(() => gate.beforeSubmit(ctx(receipt({}, [lotLine(PED)])))).not.toThrow();
  });

  test('blocks when a lot is not the pedimento', () => {
    facts(ready);
    const rec = receipt({}, [lotLine(PED), lotLine('L373483')]);
    expect(() => gate.beforeSubmit(ctx(rec))).toThrow(thrown('ACME_GATE_LOT_MISMATCH'));
    expect(() => gate.beforeSubmit(ctx(rec))).toThrow(/line 2 lot "L373483"/);
  });

  test('skips lines without inventory detail (non-lot items)', () => {
    facts(ready);
    expect(() => gate.beforeSubmit(ctx(receipt({}, [{ item: '10', itemreceive: true, cseg_acme_customs: '7' }])))).not.toThrow();
  });

  test('applies only to the configured subsidiaries', () => {
    params({ custscript_acme_gate_lot_subsidiaries: '2, 5' });
    facts(ready);
    expect(() => gate.beforeSubmit(ctx(receipt({ subsidiary: '2' }, [lotLine('OTHER')])))).toThrow(thrown('ACME_GATE_LOT_MISMATCH'));
    expect(() => gate.beforeSubmit(ctx(receipt({ subsidiary: '3' }, [lotLine('OTHER')])))).not.toThrow();
  });

  test('can be set to warn-only', () => {
    params({ custscript_acme_gate_enforce_lot: false });
    facts(ready);
    expect(() => gate.beforeSubmit(ctx(receipt({}, [lotLine('OTHER')])))).not.toThrow();
  });
});

// ---------------------------------------------------------------- customs number format
describe('R3 customs number format', () => {
  test('blocks a customs number that is not a 15-digit pedimento', () => {
    facts({ ...ready, customsno: 'PENDIENTE' });
    expect(() => gate.beforeSubmit(ctx(receipt()))).toThrow(thrown('ACME_GATE_NO_CUSTOMS'));
  });

  test('format check can be disabled with an empty parameter', () => {
    params({ custscript_acme_gate_customs_format: '' });
    facts({ ...ready, customsno: 'DESPACHO-AR-123' });
    expect(() => gate.beforeSubmit(ctx(receipt()))).not.toThrow();
  });
});

// ---------------------------------------------------------------- fail closed (previously fail open)
describe('fail closed', () => {
  test('blocks when the Confirmed id parameter is not set (was: logged and skipped R2)', () => {
    runtime.__setParams({});
    facts({ ...ready, lcstatus: '1' });
    expect(() => gate.beforeSubmit(ctx(receipt()))).toThrow(thrown('ACME_GATE_CONFIG'));
  });

  test('blocks when the shipment cannot be read (was: logged and returned)', () => {
    facts(null);
    expect(() => gate.beforeSubmit(ctx(receipt()))).toThrow(thrown('ACME_GATE_SHIPMENT_NOT_FOUND'));
  });

  test('blocks with a gate error when the lookup itself fails', () => {
    jest.spyOn(query, 'runSuiteQL').mockImplementation(() => { throw new Error('SSS_TIME_LIMIT_EXCEEDED'); });
    expect(() => gate.beforeSubmit(ctx(receipt()))).toThrow(thrown('ACME_GATE_ERROR'));
  });

  test('treats a checkbox parameter returned as "F" as warn-only, anything else as enforced', () => {
    params({ custscript_acme_gate_enforce_lc: 'F' });
    facts({ ...ready, lcrows: 0 });
    expect(() => gate.beforeSubmit(ctx(receipt()))).not.toThrow();
    params({ custscript_acme_gate_enforce_lc: null });
    expect(() => gate.beforeSubmit(ctx(receipt()))).toThrow(thrown('ACME_GATE_NO_LANDED_COST'));
  });
});
