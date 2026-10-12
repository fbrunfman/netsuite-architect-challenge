// Minimal CSV reader for the synthetic data in ../data (no quoted fields, UTF-8, comma separated).
const fs = require('fs');
const path = require('path');

const readCsv = (file) => {
  const text = fs.readFileSync(path.join(__dirname, '../../data', file), 'utf8').replace(/^﻿/, '');
  const [header, ...rows] = text.split(/\r?\n/).filter((l) => l.trim() !== '');
  const cols = header.split(',');
  return rows.map((r) => { const v = r.split(','); return Object.fromEntries(cols.map((c, i) => [c, v[i] ?? ''])); });
};

module.exports = { readCsv };
