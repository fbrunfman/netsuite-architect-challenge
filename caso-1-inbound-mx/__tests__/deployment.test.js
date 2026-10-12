// The September incident was not only a code problem: the deployment itself excluded the execution
// context the "Receive Inbound Shipment" bulk job runs under. These tests pin the deployment configuration.
const fs = require('fs');
const path = require('path');

const read = (f) => fs.readFileSync(path.join(__dirname, '../src/Objects', f), 'utf8').replace(/<!--[\s\S]*?-->/g, '');
const ir = read('customscript_acme_itemreceipt_gate_ue.xml');

test('the Item Receipt gate deployment is not restricted to a list of execution contexts', () => {
  // A whitelist that forgets one context (bulk job, scheduled, map/reduce, workflow...) is a silent hole.
  expect(ir).not.toMatch(/<executioncontext>/);
});

test('the Item Receipt gate is deployed, released, for all roles, on item receipts', () => {
  expect(ir).toMatch(/<isdeployed>T<\/isdeployed>/);
  expect(ir).toMatch(/<status>RELEASED<\/status>/);
  expect(ir).toMatch(/<allroles>T<\/allroles>/);
  expect(ir).toMatch(/<recordtype>ITEMRECEIPT<\/recordtype>/);
  expect(ir).toMatch(/<isinactive>F<\/isinactive>/);
});

test('every enforce switch defaults to blocking and the Confirmed id is set on the deployment', () => {
  for (const p of ['enforce_lc', 'enforce_lcstatus', 'enforce_customs', 'enforce_lot']) {
    expect(ir).toMatch(new RegExp(`<custscript_acme_gate_${p}>T</custscript_acme_gate_${p}>`));
  }
  expect(ir).toMatch(/<custscript_acme_gate_lc_confirmed_id>\d+<\/custscript_acme_gate_lc_confirmed_id>/);
});

test('both scripts use the same Confirmed id and customs format', () => {
  const inb = read('customscript_acme_inbship_gate_ue.xml');
  const val = (xml, tag) => (xml.match(new RegExp(`<${tag}>(.*?)</${tag}>`)) || [])[1];
  expect(val(inb, 'custscript_acme_gate2_lc_confirmed_id')).toBe(val(ir, 'custscript_acme_gate_lc_confirmed_id'));
  expect(val(inb, 'custscript_acme_gate2_customs_format')).toBe(val(ir, 'custscript_acme_gate_customs_format'));
});

test('the shared rules module is deployed with the scripts', () => {
  expect(fs.existsSync(path.join(__dirname, '../src/FileCabinet/SuiteScripts/acme_inbship/acme_inbship_rules.js'))).toBe(true);
  expect(read('../deploy.xml')).toMatch(/acme_inbship\/\*/);
});
