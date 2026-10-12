const query = require('N/query');
const runtime = require('N/runtime');
const gate = require('../src/FileCabinet/SuiteScripts/acme_inbship/acme_inbship_gate_ue');
const { fakeRecord, fakeForm, ctx } = require('./helpers/fake');

const facts = (f) => jest.spyOn(query, 'runSuiteQL').mockReturnValue({ asMappedResults: () => (f ? [f] : []) });
const shipment = (status = 'inTransit') => fakeRecord({ id: 5001, body: { shipmentstatus: status } });

beforeEach(() => { jest.restoreAllMocks(); runtime.__setParams({ custscript_acme_gate2_lc_confirmed_id: '3' }); });

test('disables Receive and shows why when landed cost is missing', () => {
  facts({ lcrows: 0, lcstatus: null, customsno: null });
  const form = fakeForm();
  gate.beforeLoad(ctx(shipment(), 'view', form));
  expect(form.buttons.receive.isDisabled).toBe(true);
  expect(form.fields[0].defaultValue).toMatch(/landed cost/i);
  expect(form.fields[0].defaultValue).toMatch(/customs clearance number is missing/i);
});

test('leaves a ready shipment alone', () => {
  facts({ lcrows: 3, lcstatus: '3', customsno: '26471234 6001234' });
  const form = fakeForm();
  gate.beforeLoad(ctx(shipment(), 'view', form));
  expect(form.buttons.receive.isDisabled).toBe(false);
  expect(form.fields).toHaveLength(0);
});

test('does nothing for shipments that are already received', () => {
  const spy = facts({ lcrows: 0 });
  const form = fakeForm();
  gate.beforeLoad(ctx(shipment('received'), 'view', form));
  expect(spy).not.toHaveBeenCalled();
});

test('uses the same rules as the receipt gate (LC status not confirmed, bad customs format)', () => {
  facts({ lcrows: 3, lcstatus: '2', customsno: 'TBD' });
  const form = fakeForm();
  gate.beforeLoad(ctx(shipment(), 'view', form));
  expect(form.buttons.receive.isDisabled).toBe(true);
  expect(form.fields[0].defaultValue).toMatch(/not Confirmed/);
  expect(form.fields[0].defaultValue).toMatch(/not a valid customs/);
});

test('disables Receive when the Confirmed id parameter is missing (fail closed, same as the receipt gate)', () => {
  runtime.__setParams({});
  facts({ lcrows: 3, lcstatus: '3', customsno: '264215269402249' });
  const form = fakeForm();
  gate.beforeLoad(ctx(shipment(), 'view', form));
  expect(form.buttons.receive.isDisabled).toBe(true);
});

test('never throws', () => {
  jest.spyOn(query, 'runSuiteQL').mockImplementation(() => { throw new Error('boom'); });
  expect(() => gate.beforeLoad(ctx(shipment(), 'view', fakeForm()))).not.toThrow();
});
