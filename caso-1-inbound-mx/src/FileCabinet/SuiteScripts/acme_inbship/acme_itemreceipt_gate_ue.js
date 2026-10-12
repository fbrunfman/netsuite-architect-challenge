/**
 * acme_itemreceipt_gate_ue.js — Receipt gate: blocks Item Receipts created from an Inbound Shipment
 * when the shipment is not ready to be received. This is THE control: it must run in every execution
 * context (UI, "Receive Inbound Shipment" bulk job, CSV, web services, scripts) — see the deployment XML,
 * which deliberately has no execution-context filter.
 *
 * Rules live in acme_inbship_rules.js (shared with the Inbound Shipment UI hint):
 *   R1 landed cost loaded · R2 LC status Confirmed · R3 customs number on shipment
 *   R4 customs segment on header AND every received line · R5 lot = customs number (MX pedimento)
 * Receipts not linked to an inbound shipment are ignored.
 * R1–R5 can each be set to warn-only via script parameter (audit log instead of block).
 * Configuration / lookup failures always block (fail closed): a gate that silently lets goods in is worse
 * than one that asks an admin to fix a parameter.
 *
 * @NApiVersion 2.1
 * @NScriptType UserEventScript
 * @NModuleScope SameAccount
 */
define(['N/runtime', 'N/error', 'N/log', './acme_inbship_rules'], (runtime, error, log, rules) => {

    const P = {
        enforceLc: 'custscript_acme_gate_enforce_lc',
        enforceLcStatus: 'custscript_acme_gate_enforce_lcstatus',
        enforceCustoms: 'custscript_acme_gate_enforce_customs',
        enforceLot: 'custscript_acme_gate_enforce_lot',
        lotSubsidiaries: 'custscript_acme_gate_lot_subsidiaries',
        customsFormat: 'custscript_acme_gate_customs_format',
        confirmedId: 'custscript_acme_gate_lc_confirmed_id'
    };
    const ENFORCE_PARAM = { lc: P.enforceLc, lcstatus: P.enforceLcStatus, customs: P.enforceCustoms, lot: P.enforceLot };

    const param = (id) => runtime.getCurrentScript().getParameter({ name: id });
    const enforced = (rule) => rule === 'always' || !rules.isOff(param(ENFORCE_PARAM[rule]));

    const stop = (code, msg) => { throw error.create({ name: code, message: msg, notifyOff: true }); };

    // The header link can be empty (bulk job / partial receipts); fall back to the line-level link.
    const findShipment = (rec) => {
        const shipId = rec.getValue('inboundshipment');
        if (shipId) return shipId;
        const n = rec.getLineCount({ sublistId: 'item' });
        for (let i = 0; i < n; i++) {
            const v = rec.getSublistValue({ sublistId: 'item', line: i, fieldId: 'inboundshipment' });
            if (v) return v;
        }
        return null;
    };

    // Lot = customs number applies to the subsidiaries listed in the parameter (blank = all).
    const lotRuleApplies = (rec) => {
        if (rules.isOff(param(P.enforceLot))) return false;
        const list = String(param(P.lotSubsidiaries) || '').split(',').map((s) => s.trim()).filter(Boolean);
        if (!list.length) return true;
        return list.includes(String(rec.getValue('subsidiary') || ''));
    };

    const beforeSubmit = (ctx) => {
        if (ctx.type !== ctx.UserEventType.CREATE) return;
        const rec = ctx.newRecord;
        const shipId = findShipment(rec);
        if (!shipId) return;

        let f;
        try {
            f = rules.shipmentFacts(shipId);
        } catch (e) {
            log.error('gate', 'shipment lookup failed for ' + shipId + ': ' + e.message);
            stop('ACME_GATE_ERROR', 'shipment ' + shipId + ': the readiness check failed (' + e.message + '). Receiving is blocked; contact the NetSuite team.');
        }
        const tag = ((f && f.shipmentnumber) || ('shipment ' + shipId)) + ': ';
        const customsFormat = param(P.customsFormat);
        const problems = rules.shipmentProblems(f, {
            confirmedId: param(P.confirmedId),
            customsFormat: customsFormat === null || customsFormat === undefined ? rules.DEFAULT_CUSTOMS_FORMAT : String(customsFormat)
        });
        if (f) problems.push(...rules.receiptProblems(rec, f, { checkLot: lotRuleApplies(rec) }));

        const ctxName = (runtime.executionContext || 'unknown');
        problems.forEach((p) => {
            if (enforced(p.rule)) stop(p.code, tag + p.msg);
            log.audit('gate warn-only [' + ctxName + ']', tag + p.msg);
        });
    };

    return { beforeSubmit };
});
