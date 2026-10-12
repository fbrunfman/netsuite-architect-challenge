/**
 * acme_inbship_rules.js — Single source of truth for "is this inbound shipment ready to be received?"
 * Shared by acme_itemreceipt_gate_ue (the real, blocking control) and acme_inbship_gate_ue (UI hint),
 * so both controls evaluate exactly the same rules and cannot drift apart.
 *
 * Shipment rules (R1–R3) need only the shipment facts; receipt rules (R4–R5) need the receipt record:
 *   R1  ACME_GATE_NO_LANDED_COST     the shipment has at least one landed-cost row
 *   R2  ACME_GATE_LC_NOT_CONFIRMED   the shipment's Landed Cost Status is Confirmed
 *   R3  ACME_GATE_NO_CUSTOMS         customs clearance number set on the shipment (+ optional format check)
 *   R4  ACME_GATE_NO_CUSTOMS         customs segment set on the receipt header AND on every received line
 *   R5  ACME_GATE_LOT_MISMATCH       every lot received equals the customs number (MX: lot = pedimento)
 *   --  ACME_GATE_CONFIG / ACME_GATE_SHIPMENT_NOT_FOUND / ACME_GATE_ERROR  always block (fail closed)
 *
 * @NApiVersion 2.1
 * @NModuleScope SameAccount
 */
define(['N/query'], (query) => {

    const CUSTOMS_SEGMENT = 'cseg_acme_customs';
    const DEFAULT_CUSTOMS_FORMAT = '^\\d{15}$'; // pedimento: 15 digits once spaces are removed

    const norm = (v) => String(v == null ? '' : v).replace(/\s+/g, '');
    const isOff = (v) => v === false || v === 'F' || v === 'false' || v === 'N';

    /** Reads the facts the rules need. Returns null when the shipment does not exist. */
    const shipmentFacts = (shipId) => {
        const rows = query.runSuiteQL({
            query: `SELECT s.shipmentnumber, s.custrecord_acme_inb_lc_status AS lcstatus,
                           s.custrecord_acme_inb_customs_no AS customsno,
                           (SELECT COUNT(*) FROM inboundshipmentlandedcost l WHERE l.landedcostinboundshipment = s.id) AS lcrows
                    FROM inboundshipment s WHERE s.id = ?`,
            params: [shipId]
        }).asMappedResults();
        return rows.length ? rows[0] : null;
    };

    /**
     * R1–R3 on the shipment facts.
     * @param {Object|null} f            result of shipmentFacts()
     * @param {Object} o
     * @param {string} o.confirmedId     internal id of the "Confirmed" LC status (script parameter)
     * @param {string} [o.customsFormat] regex the customs number must match (empty = no format check)
     * @returns {{code:string, rule:string, msg:string}[]}
     */
    const shipmentProblems = (f, o) => {
        if (!f) return [{ code: 'ACME_GATE_SHIPMENT_NOT_FOUND', rule: 'always', msg: 'the inbound shipment could not be read; receiving is blocked.' }];
        const p = [];
        if (Number(f.lcrows || 0) === 0) {
            p.push({ code: 'ACME_GATE_NO_LANDED_COST', rule: 'lc', msg: 'landed cost is not loaded on the shipment. Costs must load it before receiving.' });
        }
        const confirmedId = norm(o && o.confirmedId);
        if (!confirmedId) {
            p.push({ code: 'ACME_GATE_CONFIG', rule: 'always', msg: "the 'LC Status Confirmed id' script parameter is not set; receiving is blocked until it is configured." });
        } else if (norm(f.lcstatus) !== confirmedId) {
            p.push({ code: 'ACME_GATE_LC_NOT_CONFIRMED', rule: 'lcstatus', msg: 'Landed Cost Status is not Confirmed. Costs must confirm the landed cost before receiving.' });
        }
        const customs = norm(f.customsno);
        if (!customs) {
            p.push({ code: 'ACME_GATE_NO_CUSTOMS', rule: 'customs', msg: 'customs clearance number is missing on the shipment.' });
        } else {
            const fmt = o && o.customsFormat !== undefined ? o.customsFormat : DEFAULT_CUSTOMS_FORMAT;
            if (fmt && !new RegExp(fmt).test(customs)) {
                p.push({ code: 'ACME_GATE_NO_CUSTOMS', rule: 'customs', msg: `customs clearance number "${f.customsno}" is not a valid customs/pedimento number (expected ${fmt}).` });
            }
        }
        return p;
    };

    /** Lines the user is actually receiving (Receive page / job untick lines that are not received). */
    const receivedLines = (rec) => {
        const out = [];
        const n = rec.getLineCount({ sublistId: 'item' });
        for (let i = 0; i < n; i++) {
            const recv = rec.getSublistValue({ sublistId: 'item', line: i, fieldId: 'itemreceive' });
            const qty = rec.getSublistValue({ sublistId: 'item', line: i, fieldId: 'quantity' });
            if (isOff(recv)) continue;
            if (qty !== null && qty !== undefined && qty !== '' && Number(qty) === 0) continue;
            out.push(i);
        }
        return out;
    };

    /** Lots assigned on the line's inventory detail. [] when the line has no inventory detail (non-lot item). */
    const lineLots = (rec, line) => {
        try {
            if (typeof rec.hasSublistSubrecord === 'function'
                && !rec.hasSublistSubrecord({ sublistId: 'item', fieldId: 'inventorydetail', line })) return [];
            const sub = rec.getSublistSubrecord({ sublistId: 'item', fieldId: 'inventorydetail', line });
            if (!sub) return [];
            const lots = [];
            const n = sub.getLineCount({ sublistId: 'inventoryassignment' });
            for (let i = 0; i < n; i++) {
                const lot = sub.getSublistValue({ sublistId: 'inventoryassignment', line: i, fieldId: 'receiptinventorynumber' });
                if (lot) lots.push(String(lot));
            }
            return lots;
        } catch (e) {
            return [];
        }
    };

    /**
     * R4–R5 on the item receipt being created.
     * @param {Record} rec   the item receipt (ctx.newRecord)
     * @param {Object} f     shipment facts (for the customs number)
     * @param {Object} o
     * @param {boolean} [o.checkLot=true]  whether lots must equal the customs number
     */
    const receiptProblems = (rec, f, o) => {
        const p = [];
        if (!rec.getValue(CUSTOMS_SEGMENT)) {
            p.push({ code: 'ACME_GATE_NO_CUSTOMS', rule: 'customs', msg: 'customs segment is not set on the receipt header.' });
        }
        const lines = receivedLines(rec);
        const noSeg = lines.filter((i) => !rec.getSublistValue({ sublistId: 'item', line: i, fieldId: CUSTOMS_SEGMENT }));
        if (noSeg.length) {
            p.push({ code: 'ACME_GATE_NO_CUSTOMS', rule: 'customs',
                msg: `customs segment is not set on receipt line(s) ${noSeg.map((i) => i + 1).join(', ')}. The segment must be on every line for the customs report to reconcile.` });
        }
        const checkLot = !(o && o.checkLot === false);
        const customs = norm(f && f.customsno);
        if (checkLot && customs) {
            const bad = [];
            lines.forEach((i) => lineLots(rec, i).forEach((lot) => { if (norm(lot) !== customs) bad.push(`line ${i + 1} lot "${lot}"`); }));
            if (bad.length) {
                p.push({ code: 'ACME_GATE_LOT_MISMATCH', rule: 'lot',
                    msg: `lot must equal the customs number ${f.customsno} (the localization bundle looks the pedimento up by lot): ${bad.join('; ')}.` });
            }
        }
        return p;
    };

    return { CUSTOMS_SEGMENT, DEFAULT_CUSTOMS_FORMAT, norm, isOff, shipmentFacts, shipmentProblems, receivedLines, lineLots, receiptProblems };
});
