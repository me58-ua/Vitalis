import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
import ts from 'typescript';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'test-results', 'agenda');
await mkdir(output, { recursive: true });
const source = await readFile(path.join(root, 'src/utils/agenda.ts'), 'utf8');
await writeFile(path.join(output, 'agenda.mjs'), ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText);
const { addDays, mondayOf, madridDay, validCalendarDay, blocksForDay, clipInterval } = await import(pathToFileURL(path.join(output, 'agenda.mjs')).href);

test('vacations span full Madrid days and exclude the midnight end boundary', () => {
  const block = { start_time: '2030-07-01T22:00:00Z', end_time: '2030-07-05T22:00:00Z' };
  assert.equal(clipInterval(block, '2030-07-01'), null);
  assert.deepEqual(clipInterval(block, '2030-07-02'), { start: 0, end: 1440 });
  assert.deepEqual(clipInterval(block, '2030-07-05'), { start: 0, end: 1440 });
  assert.equal(clipInterval(block, '2030-07-06'), null);
  assert.deepEqual(clipInterval({ start_time: '2030-07-02T08:00:00Z', end_time: '2030-07-02T10:30:00Z' }, '2030-07-02'), { start: 600, end: 750 });
});

test('calendar weeks stay on Monday across DST and year boundaries', () => {
  assert.equal(mondayOf('2026-03-29'), '2026-03-23');
  assert.equal(addDays('2026-03-23', 7), '2026-03-30');
  assert.equal(addDays('2026-10-19', 7), '2026-10-26');
  assert.equal(mondayOf('2027-01-01'), '2026-12-28');
  assert.equal(addDays('2026-12-28', 7), '2027-01-04');
  assert.equal(madridDay('2026-11-03T23:30:00Z'), '2026-11-04');
  assert.equal(madridDay('2026-07-03T22:30:00Z'), '2026-07-04');
  assert.equal(validCalendarDay('2026-02-30'), false);
  assert.equal(validCalendarDay('2026-02-28'), true);
});

const appointment = (id, start_time, end_time, status = 'confirmed') => ({ id, start_time, end_time, status, patient_id: 'fixture-patient', patient_name: 'Paciente de prueba', patient_username: 'fixture', type: 'video', appointment_reason: null, cancellation_reason: null });

test('overnight appointments are clipped to the correct Madrid dates', () => {
  const item = appointment('overnight', '2026-11-03T22:30:00Z', '2026-11-04T00:00:00Z');
  assert.deepEqual(blocksForDay([item], '2026-11-03').map(b => [b.start, b.end]), [[1410, 1440]]);
  assert.deepEqual(blocksForDay([item], '2026-11-04').map(b => [b.start, b.end]), [[0, 60]]);
  assert.deepEqual(blocksForDay([item], '2026-11-05'), []);
  const midnightEnd = appointment('midnight', '2026-11-03T22:00:00Z', '2026-11-03T23:00:00Z');
  assert.deepEqual(blocksForDay([midnightEnd], '2026-11-04'), []);
});

test('overlapping cancelled and active bookings remain individually accessible', () => {
  const rows = [
    appointment('cancelled', '2026-11-03T08:00:00Z', '2026-11-03T09:00:00Z', 'cancelled'),
    appointment('active', '2026-11-03T08:30:00Z', '2026-11-03T09:00:00Z'),
    appointment('adjacent', '2026-11-03T09:00:00Z', '2026-11-03T09:30:00Z'),
  ];
  const blocks = blocksForDay(rows, '2026-11-03');
  assert.deepEqual(blocks.map(b => [b.appointment.id, b.column, b.columns]), [['cancelled', 0, 2], ['active', 1, 2], ['adjacent', 0, 1]]);
  assert.equal(blocks[1].end - blocks[1].start, 30);
});
