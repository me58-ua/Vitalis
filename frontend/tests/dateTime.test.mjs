import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import ts from 'typescript';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'test-results', 'formats');
await mkdir(output, { recursive: true });
for (const name of ['dateTime', 'workingHours']) {
  const source = await readFile(path.join(root, `src/utils/${name}.ts`), 'utf8');
  await writeFile(path.join(output, `${name}.mjs`), ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText);
}
const { canonicalValue, localizedValue, dateFormat, dateTimeFormat } = await import(pathToFileURL(path.join(output, 'dateTime.mjs')).href);
const { groupWorkingHours } = await import(pathToFileURL(path.join(output, 'workingHours.mjs')).href);

test('Spanish dates round-trip without swapping an ambiguous day and month', () => {
  assert.equal(canonicalValue('05/06/2026', 'date'), '2026-06-05');
  assert.equal(localizedValue('2026-06-05', 'date'), '05/06/2026');
  assert.equal(canonicalValue('29/02/2028', 'date'), '2028-02-29');
  for (const value of ['29/02/2026', '31/04/2026', '06/25/2026', '1/2/2026']) assert.equal(canonicalValue(value, 'date'), '');
});
test('24-hour inputs preserve midnight, reject AM/PM and preserve audit seconds', () => {
  assert.equal(canonicalValue('00:00', 'time'), '00:00');
  assert.equal(canonicalValue('23:59', 'time'), '23:59');
  for (const value of ['24:00', '12:30 PM', '09:60']) assert.equal(canonicalValue(value, 'time'), '');
  assert.equal(canonicalValue('09/11/2026 18:25', 'datetime-local'), '2026-11-09T18:25');
  assert.equal(canonicalValue('09/11/2026 18:25:30', 'datetime-local', true), '2026-11-09T18:25:30');
  assert.equal(localizedValue('2026-11-09T18:25', 'datetime-local', true), '09/11/2026 18:25:00');
});
test('visible dates and instants always use Spanish order and Madrid 24-hour time', () => {
  const value = new Date('2026-11-09T23:05:00Z');
  assert.equal(dateFormat.format(value), '10/11/2026');
  assert.match(dateTimeFormat.format(value), /10\/11\/2026.*00:05/);
  assert.doesNotMatch(dateTimeFormat.format(value), /AM|PM/);
});
test('working hours combine days but preserve different channels, states and consultation lengths', () => {
  const row = (id, day, changes = {}) => ({ id, day_of_week: day, channel: 'consultation', start_time: '09:00:00', end_time: '13:00:00', slot_duration_min: 30, is_active: true, ...changes });
  const groups = groupWorkingHours([row('fri', 4), row('mon', 0), row('tue', 1), row('long', 2, { slot_duration_min: 60 }), row('off', 3, { is_active: false }), row('chat', 0, { channel: 'chat' })]);
  assert.equal(groups.length, 4);
  const combined = groups.find(group => group.rows.length === 3);
  assert.equal(combined.label, 'Lunes, Martes y Viernes');
  assert.deepEqual(combined.rows.map(row => row.day_of_week), [0, 1, 4]);
  assert.equal(groupWorkingHours([row('chat1', 0, { channel: 'chat' }), row('chat2', 2, { channel: 'chat', slot_duration_min: 60 })]).length, 1);
});
