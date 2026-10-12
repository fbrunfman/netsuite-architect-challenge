/**
 * acme_inbship_gate_ue.js — On the Inbound Shipment (view mode), disable the Receive button and show why
 * when the shipment is not ready to be received. Same rules as acme_itemreceipt_gate_ue (shared module).
 *
 * This is a usability hint only: it runs in the UI, on this form, and nowhere else. The bulk
 * "Receive Inbound Shipment" page, CSV imports and integrations never see it; the Item Receipt gate is
 * the control that actually blocks. Never throws: a failure only means the button stays enabled.
 *
 * @NApiVersion 2.1
 * @NScriptType UserEventScript
 * @NModuleScope SameAccount
 */
define(['N/runtime', 'N/ui/serverWidget', 'N/log', './acme_inbship_rules'], (runtime, serverWidget, log, rules) => {

    const P = { confirmedId: 'custscript_acme_gate2_lc_confirmed_id', customsFormat: 'custscript_acme_gate2_customs_format' };
    const RECEIVABLE = ['inTransit', 'toBeShipped', 'partiallyReceived'];

    const beforeLoad = (ctx) => {
        try {
            if (ctx.type !== ctx.UserEventType.VIEW) return;
            const rec = ctx.newRecord;
            if (!RECEIVABLE.includes(String(rec.getValue('shipmentstatus') || ''))) return;
            const f = rules.shipmentFacts(rec.id);
            const fmt = runtime.getCurrentScript().getParameter({ name: P.customsFormat });
            const problems = rules.shipmentProblems(f, {
                confirmedId: runtime.getCurrentScript().getParameter({ name: P.confirmedId }),
                customsFormat: fmt === null || fmt === undefined ? rules.DEFAULT_CUSTOMS_FORMAT : String(fmt)
            });
            if (!problems.length) return;

            const b = ctx.form.getButton('receive');
            if (b) b.isDisabled = true;
            const msg = ctx.form.addField({ id: 'custpage_acme_gate_msg', type: serverWidget.FieldType.INLINEHTML, label: ' ' });
            msg.defaultValue = '<div style="background:#fde8e8;border:1px solid #d33;color:#900;padding:8px 12px">'
                + '<b>Receiving blocked:</b> ' + problems.map((p) => p.msg).join(' · ')
                + '<br><small>The same rules are enforced when the Item Receipt is saved, including from the Receive Inbound Shipment job.</small></div>';
            msg.updateLayoutType({ layoutType: serverWidget.FieldLayoutType.OUTSIDEABOVE });
        } catch (e) {
            log.error('acme_inbship_gate_ue beforeLoad', e.message);
        }
    };

    return { beforeLoad };
});
