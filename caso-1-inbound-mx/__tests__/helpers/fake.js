const UserEventType = { CREATE: 'create', EDIT: 'edit', VIEW: 'view' };

// lines[i].inventorydetail = [{ receiptinventorynumber: 'LOT', quantity: n }, ...] simulates the
// inventory detail subrecord of a lot-numbered item. Lines without it behave like non-lot items.
const fakeSubrecord = (assignments = []) => ({
  getLineCount: ({ sublistId }) => (sublistId === 'inventoryassignment' ? assignments.length : 0),
  getSublistValue: ({ sublistId, line, fieldId }) => (sublistId === 'inventoryassignment' ? assignments[line]?.[fieldId] ?? null : null),
});

const fakeRecord = ({ id = null, body = {}, lines = [] } = {}) => ({
  id,
  getValue: (f) => body[typeof f === 'string' ? f : f.fieldId] ?? null,
  getLineCount: ({ sublistId }) => (sublistId === 'item' ? lines.length : 0),
  getSublistValue: ({ sublistId, line, fieldId }) => (sublistId === 'item' ? lines[line]?.[fieldId] ?? null : null),
  hasSublistSubrecord: ({ sublistId, fieldId, line }) => sublistId === 'item' && fieldId === 'inventorydetail' && Array.isArray(lines[line]?.inventorydetail),
  getSublistSubrecord: ({ sublistId, fieldId, line }) =>
    (sublistId === 'item' && fieldId === 'inventorydetail' && Array.isArray(lines[line]?.inventorydetail)) ? fakeSubrecord(lines[line].inventorydetail) : null,
});

const fakeForm = () => {
  const buttons = { receive: { isDisabled: false } };
  const fields = [];
  return {
    buttons, fields,
    getButton: (id) => buttons[id] || null,
    removeButton: (id) => { delete buttons[id]; },
    addField: (f) => { const fld = { ...f, defaultValue: '', updateLayoutType: () => {} }; fields.push(fld); return fld; },
  };
};

const ctx = (newRecord, type = UserEventType.CREATE, form) => ({ newRecord, type, form, UserEventType });

module.exports = { fakeRecord, fakeForm, fakeSubrecord, ctx };
