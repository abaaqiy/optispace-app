import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const context = { window: {} };
runInNewContext(readFileSync(new URL('./ocr_reference_groups.js', import.meta.url), 'utf8'), context);
const { build } = context.window.OptispaceOcrGroups;
const rooms = [{ name: '1,000-Seater Lecture Theatre (1000 SLT)', aliases: ['1000SLT', '1000 SLT'] }];
const roomRow = (text, extra = {}) => ({ room_text: text, room: '', day: 'Monday', start_time: '08:00', end_time: '09:00', ...extra });
const courseRow = (text, extra = {}) => ({ course_text: text, course: '', ...extra });
const groupRooms = (rows, catalogue = rooms, references = []) => build({ kind: 'room', rows, catalogue, references });
const groupCourses = (rows, catalogue = [], references = []) => build({ kind: 'course', rows, catalogue, references });

test('OCR substitutions, transposed letters and a missing letter group around one documented room', () => {
  const rows = ['1000IST', '1000Sit', '1000Sit', '1000Sit', '1000 LT', '1000SLT'].map(text => roomRow(text));
  const before = JSON.stringify(rows);
  const result = groupRooms(rows);
  assert.equal(result.groups.length, 1);
  assert.equal(result.groups[0].rows.length, 6);
  assert.equal(result.groups[0].target.label, rooms[0].name);
  assert.equal(result.groups[0].suggested, true);
  assert.equal(result.groups[0].readings.length, 4);
  assert.equal(JSON.stringify(rows), before, 'Suggestion never rewrites source text or maps a room');
});

test('several departments reuse a sourced course prefix without merging different numbers', () => {
  for (const [prefix, misread] of [['CHM', 'CM'], ['CSC', 'CS'], ['LGS', 'LOS']]) {
    const codes = [`${prefix}202`, `${prefix}302`];
    const result = groupCourses([courseRow(codes[0]), courseRow(`${misread}202`), courseRow(codes[1])], codes.map(code => ({ code })));
    assert.equal(result.groups.length, 2);
    const group = result.groups.find(group => group.rows.length === 2);
    assert.ok(group, `${prefix} groups its OCR variation`);
    assert.equal(group.target.id, codes[0]);
    assert.equal(group.rows[1].course_text, `${misread}202`);
  }
});

test('letter/digit confusions in course numbers suggest a code but literal different numbers stay separate', () => {
  const result = groupCourses(['ICH3O8', '1CH308', 'ICH308', 'ICH306'].map(code => courseRow(code)),
    [{ code: 'ICH308' }, { code: 'ICH306' }]);
  assert.equal(result.groups.length, 2);
  assert.equal(result.groups.find(group => group.target?.id === 'ICH308').rows.length, 3);
  assert.equal(result.groups.find(group => group.target?.id === 'ICH306').rows.length, 1);
});

test('room numbers and building/venue letter suffixes retain distinct identities', () => {
  const catalogue = ['CH102', 'CH202', 'BOOA', 'BOOB', 'STEP A', 'STEP B', 'ADMIN EXT A', 'ADMIN EXT D']
    .map(name => ({ name, aliases: [] }));
  const result = groupRooms(catalogue.map(item => roomRow(item.name)), catalogue);
  assert.equal(result.groups.length, catalogue.length);
  assert.ok(result.groups.every(group => group.rows.length === 1));
  const ambiguous = groupRooms([roomRow('CH 1O2'), roomRow('BOOC')], catalogue);
  assert.equal(ambiguous.groups[0].target.id, 'CH102');
  assert.equal(ambiguous.groups[1].target, null, 'An unknown lecture theatre letter is not forced onto A/B');
});

test('similar valid course prefixes in the catalogue are never combined', () => {
  const result = groupCourses(['PHA201', 'PHC201', 'PHA2O1', 'PHC2O1', 'PHB201'].map(code => courseRow(code)),
    [{ code: 'PHA201' }, { code: 'PHC201' }]);
  assert.equal(result.groups.length, 3);
  assert.equal(result.groups.find(group => group.target?.id === 'PHA201').rows.length, 2);
  assert.equal(result.groups.find(group => group.target?.id === 'PHC201').rows.length, 2);
  assert.equal(result.groups.find(group => group.text === 'PHB201').rows.length, 1);
});

test('ambiguous matches and severely damaged readings remain independent', () => {
  const result = groupRooms([roomRow('AOCD'), roomRow('CH102'), roomRow('CH202'), roomRow('C')],
    ['AQCD', 'ADCD', 'CH102', 'CH202'].map(name => ({ name, aliases: [] })));
  assert.equal(result.groups.length, 4);
  assert.equal(result.groups.find(group => group.text === 'AOCD').target, null);
  assert.equal(result.groups.find(group => group.text === 'C').target, null);
});

test('one fuzzy reading never joins distinct exact catalogue entries through a similarity chain', () => {
  const result = groupRooms(['AQCD', 'ADCD', 'AOCD'].map(text => roomRow(text)),
    ['AQCD', 'ADCD'].map(name => ({ name, aliases: [] })));
  assert.equal(result.groups.length, 3);
  assert.equal(result.groups.find(group => group.text === 'AQCD').rows.length, 1);
  assert.equal(result.groups.find(group => group.text === 'ADCD').rows.length, 1);
  const repeated = groupRooms(['AQCD', 'AQCD', 'AQCD', 'AOCD'].map(text => roomRow(text)),
    ['AQCD', 'ADCD'].map(name => ({ name, aliases: [] })));
  assert.equal(repeated.groups.length, 2);
  assert.equal(repeated.groups.find(group => group.text === 'AOCD').target, null,
    'Repeated OCR readings cannot override conflicting catalogue matches');
});

test('blank readings are collected without inventing one shared identity', () => {
  const first = roomRow(''), second = roomRow(''), skipped = roomRow('', { skip: true });
  const result = groupRooms([first, second, skipped]);
  assert.equal(result.groups.length, 0);
  assert.equal(result.missing.length, 2);
  assert.equal(result.missing[0], first);
  assert.equal(result.missing[1], second);
});

test('saved/prepared records suggest one choice while already mapped/skipped rows are excluded', () => {
  const ref = { value: 'draft-room-12345678', name: rooms[0].name, identity: rooms[0].name,
    label: `New: ${rooms[0].name}`, keys: ['1000SLT'] };
  const result = groupRooms([roomRow('1000SIT'), roomRow('1000IST'), roomRow('1000SLT', { room: ref.value }), roomRow('1000SIT', { skip: true })], rooms, [ref]);
  assert.equal(result.groups.length, 1);
  assert.equal(result.groups[0].rows.length, 2);
  assert.equal(result.groups[0].target.value, ref.value);
});

test('administrator separation and checked readings survive regrouping', () => {
  const result = groupRooms([roomRow('1000SIT'), roomRow('1000IST', { room_group_separate: true }),
    roomRow('1000LT', { room_reading_checked: true })]);
  assert.equal(result.groups.length, 3);
  assert.equal(result.groups.find(group => group.text === '1000IST').separated, true);
  assert.equal(result.groups.find(group => group.text === '1000LT').target, null);
});

test('unfinished mapping/creation edits keep their existing reading independent', () => {
  const result = build({ kind: 'room', references: [], catalogue: rooms,
    rows: [roomRow('1000IST'), roomRow('1000SIT')], isEditing: text => text === '1000SIT' });
  assert.equal(result.groups.length, 2);
  assert.equal(result.groups.find(group => group.text === '1000SIT').editing, true);
});

test('unknown repeated venues can anchor a shape-confused spelling without a catalogue', () => {
  const result = groupRooms(['MQLT', 'MQLT', 'MQLT', 'MOLT'].map(text => roomRow(text)), []);
  assert.equal(result.groups.length, 1);
  assert.equal(result.groups[0].target.source, 'reading');
  assert.equal(result.groups[0].target.label, 'MQLT');
  const unknownCourses = groupCourses(['ICH308', 'ICH308', 'ICH306'].map(text => courseRow(text)));
  assert.equal(unknownCourses.groups.length, 2);
});
