import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import ts from 'typescript';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'test-results', 'prescriptions');
await mkdir(output, { recursive: true });
const source = await readFile(path.join(root, 'src/utils/prescriptions.ts'), 'utf8');
const modulePath = path.join(output, 'prescriptions.mjs');
await writeFile(modulePath, ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText);
const { calendarToday, prescriptionValidity, prescriptionDate } = await import(pathToFileURL(modulePath).href);

test('expiry stays valid through the expiry date and warns within seven calendar days', () => {
  const item = { fecha_emision: '2026-03-01', fecha_caducidad: '2026-03-30' };
  assert.equal(prescriptionValidity(item, '2026-03-22').status, 'valid');
  assert.deepEqual(prescriptionValidity(item, '2026-03-23'), { status: 'soon', label: 'Expira en 7 días' });
  assert.equal(prescriptionValidity(item, '2026-03-29').label, 'Expira en 1 día');
  assert.equal(prescriptionValidity(item, '2026-03-30').label, 'Vence hoy');
  assert.equal(prescriptionValidity(item, '2026-03-31').status, 'expired');
});

test('unknown validity and future issue dates never imply active medication or completed treatment', () => {
  assert.deepEqual(prescriptionValidity({}, '2026-11-13'), { status: 'unknown', label: 'Vigencia no indicada' });
  assert.equal(prescriptionValidity({ fecha_emision: '2026-11-01', fecha_caducidad: null }, '2026-11-13').status, 'unknown');
  assert.equal(prescriptionValidity({ fecha_emision: '2026-11-14', fecha_caducidad: '2026-11-15' }, '2026-11-13').status, 'future');
});

test('dates respect the patient calendar, DST and year rollover without shifting document dates', () => {
  assert.equal(calendarToday(new Date('2026-11-13T23:30:00Z'), 'Europe/Madrid'), '2026-11-14');
  assert.equal(calendarToday(new Date('2026-11-13T23:30:00Z'), 'America/New_York'), '2026-11-13');
  assert.equal(calendarToday(new Date('2026-11-13T23:30:00Z'), 'invalid'), '2026-11-14');
  assert.equal(prescriptionValidity({ fecha_caducidad: '2027-01-01' }, '2026-12-25').label, 'Expira en 7 días');
  assert.match(prescriptionDate('2026-11-13'), /13.*nov.*2026/);
  assert.equal(prescriptionDate(null), 'No indicada');
});
