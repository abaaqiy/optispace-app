import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
const template = read('../../templates/scheduling/admin/timetable_document.html')
  .replace(/{%[\s\S]*?%}/g, '').replace(/{{[\s\S]*?}}/g, '');
const row = (code = 'PUL301') => ({ course_text: code, room_text: 'STEP A', course: '', room: 'step-a',
  day: 'Monday', start_time: '08:00', end_time: '09:00', page: 1, box: [20, 30, 100, 80], reviewed: false });

// Exercise the production controller against its real template. Select2 itself
// is Django's vendored widget; this harness supplies only its change-event hook.
function editor(t, rows = [row()], pending = { courses: [], rooms: [] }) {
  const dom = new JSDOM(template, { url: 'http://localhost/', runScripts: 'outside-only' });
  t.after(() => dom.window.close());
  const { window } = dom;
  const document = window.document;
  window.django = { jQuery: el => ({ on: (name, callback) => el.addEventListener(name, callback) }) };
  window.HTMLElement.prototype.scrollIntoView = () => {};
  const creation = { can_add_course: true, can_add_room: true, can_add_building: true,
    course_catalogue: [], course_sources: {}, buildings: [], facilities: [],
    faculties: ['Faculty of Computing Science and Engineering'],
    room_names: [{ name: 'STEP A', aliases: [] }], room_types: ['Classroom'],
    building_names: ['Computer Building Complex', 'Hezekiah Oluwasanmi Library (HOL)'] };
  for (const [id, data] of Object.entries({
    'document-rows': rows,
    'document-references': { courses: [], rooms: [{ value: 'step-a', label: 'STEP A', keys: [] }] },
    'document-pages': [{ url: '/source', width: 200, height: 300 }],
    'document-pending': pending, 'document-creation-choices': creation,
  })) {
    const script = document.createElement('script'); script.id = id; script.type = 'application/json';
    script.textContent = JSON.stringify(data); document.body.append(script);
  }
  document.getElementById('document-department').value = 'Public Law';
  window.eval(read('./clock.js'));
  window.eval(read('./course_suggestions.js'));
  window.eval(read('./timetable_document.js'));
  function button(root, text) {
    const found = [...root.querySelectorAll('button')].find(el => el.textContent === text);
    assert.ok(found, `Button exists: ${text}`); found.click();
  }
  function field(root, label) {
    const found = [...root.querySelectorAll('label')].find(el => el.textContent === label);
    assert.ok(found, `Field exists: ${label}`);
    return found.htmlFor ? document.getElementById(found.htmlFor) : found.querySelector('input');
  }
  function change(el, value) {
    if (el.type === 'checkbox') el.checked = value; else el.value = value;
    el.dispatchEvent(new window.Event('change', { bubbles: true }));
  }
  function payload() {
    const form = document.getElementById('document-review');
    form.dispatchEvent(new window.Event('submit', { cancelable: true }));
    return { rows: JSON.parse(document.getElementById('review-rows').value),
      pending: JSON.parse(document.getElementById('pending-records').value) };
  }
  const mapping = code => [...document.querySelectorAll('.reference-mapping')]
    .find(el => el.querySelector('strong')?.textContent.includes(`“${code}”`));
  return { document, window, button, field, change, payload, mapping };
}

test('unknown title needs explicit confirmation and survives saving and resuming', t => {
  const e = editor(t);
  const form = e.mapping('PUL301').querySelector('.record-editor');
  e.button(form, 'Use new record for matching entries');
  assert.equal(e.payload().pending.courses.length, 0);
  const check = form.querySelector('input[type=checkbox]');
  e.change(check, true);
  assert.equal(e.field(form, 'Course title').disabled, true);
  e.button(form, 'Use new record for matching entries');
  const saved = e.payload();
  assert.equal(saved.pending.courses[0].title, '');
  assert.equal(saved.pending.courses[0].title_pending, true);
  assert.equal(saved.rows[0].course, saved.pending.courses[0].key);
  assert.match(e.document.getElementById('proposed-records').textContent, /Title awaiting confirmation/);
  const resumed = editor(t, saved.rows, saved.pending);
  const proposed = resumed.document.querySelector('#proposed-records .record-editor');
  assert.equal(proposed.querySelector('input[type=checkbox]').checked, true);
  assert.equal(resumed.field(proposed, 'Course title').disabled, true);
});

test('one OCR correction preserves other entries, timing, venue and original reading', t => {
  const e = editor(t, [row('CSC107'), { ...row('CSC107'), day: 'Tuesday', start_time: '10:00', end_time: '11:00' }]);
  const group = e.mapping('CSC107');
  const location = group.querySelector('.mapping-location');
  e.field(location, 'Correct course reading in row 1').value = 'CSC102';
  e.button(location, 'Apply corrected reading');
  const corrected = e.payload().rows;
  assert.equal(corrected[0].course_text, 'CSC102');
  assert.equal(corrected[0].original_course_text, 'CSC107');
  assert.equal(corrected[0].reviewed, false);
  assert.equal(corrected[0].room, 'step-a');
  assert.equal(corrected[0].start_time, '08:00');
  assert.equal(corrected[1].course_text, 'CSC107');
  assert.equal(corrected[1].start_time, '10:00');
  assert.ok(e.mapping('CSC102'));
});

test('skipping a mistaken reading removes its proposal until restored', t => {
  const e = editor(t);
  const form = e.mapping('PUL301').querySelector('.record-editor');
  e.change(form.querySelector('input[type=checkbox]'), true);
  e.button(form, 'Use new record for matching entries');
  e.button(e.document.querySelector('#proposed-records'), 'Skip this entry');
  assert.equal(e.payload().rows[0].skip, true);
  assert.equal(e.document.querySelector('#proposed-records').children.length, 0);
  const filter = e.document.getElementById('review-filter'); filter.value = 'skipped';
  filter.dispatchEvent(new e.window.Event('input'));
  const skip = [...e.document.querySelectorAll('#document-table label')].find(el => el.textContent.includes('Skip row')).querySelector('input');
  e.change(skip, false);
  assert.equal(e.payload().rows[0].skip, false);
  assert.match(e.document.querySelector('#proposed-records').textContent, /PUL301/);
});

test('new building uses searchable catalogue and supports Others without free-typing listed names', t => {
  const e = editor(t, [{ ...row(), room: '' }]);
  const form = e.mapping('STEP A').querySelector('.record-editor');
  e.change(e.field(form, 'Building'), 'new');
  const building = e.field(form, 'New building name');
  assert.ok(building.classList.contains('room-catalog-select'));
  assert.equal([...building.options].at(-1).value, '__other__');
  e.change(building, 'Computer Building Complex');
  e.change(e.field(form, 'New building campus area'), 'Faculty of Computing Science and Engineering');
  e.change(e.field(form, 'Room type'), 'Classroom');
  e.field(form, 'Capacity').value = '80';
  e.change(e.field(form, 'Size category'), 'large');
  e.button(form, 'Use new record for matching entries');
  const saved = e.payload();
  assert.equal(saved.pending.rooms[0].building_name, 'Computer Building Complex');
  assert.equal(saved.pending.rooms[0].name, 'STEP A');
  const proposed = e.document.querySelector('#proposed-records .record-editor');
  e.change(e.field(proposed, 'New building name'), '__other__');
  e.field(proposed, 'Custom new building name').value = 'Verified teaching block';
  e.button(proposed, 'Update proposed record');
  assert.equal(e.payload().pending.rooms[0].building_name, 'Verified teaching block');
});

test('image times show AM/PM while corrections retain canonical values and order', t => {
  const e = editor(t, [{ ...row(), start_time: '12:00', end_time: '14:30' }]);
  assert.match(e.document.querySelector('#weekly-preview').textContent, /12:00 PM–2:30 PM/);
  const input = e.document.querySelector('[aria-label="Start time, row 1 (AM/PM)"]');
  assert.equal(input.value, '12:00 PM');
  input.value = '1:15 PM'; input.dispatchEvent(new e.window.Event('input'));
  assert.equal(e.payload().rows[0].start_time, '13:15');
  assert.equal(e.payload().rows[0].end_time, '14:30');
  input.value = '1:15'; input.dispatchEvent(new e.window.Event('input'));
  assert.equal(e.payload().rows[0].start_time, '');
  assert.equal(input.checkValidity(), false);
});

test('shared image time headings convert noon correctly for every affected entry', t => {
  const e = editor(t, [{ ...row(), time_group: 'time-one', time_text: '12-1', start_time: '12:00', end_time: '13:00' }]);
  const heading = e.document.querySelector('.heading-mapping');
  const inputs = heading.querySelectorAll('input');
  assert.equal(inputs[0].value, '12:00 PM');
  inputs[0].value = '12:30 PM'; inputs[1].value = '1:30 PM';
  e.button(heading, 'Confirm heading for these entries');
  assert.equal(e.payload().rows[0].start_time, '12:30');
  assert.equal(e.payload().rows[0].end_time, '13:30');
  assert.equal(e.payload().rows[0].time_checked, true);
});
