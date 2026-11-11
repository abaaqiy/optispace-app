import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync, readdirSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
const template = read('../../templates/scheduling/admin/timetable_document.html')
  .replace(/{%[\s\S]*?%}/g, '').replace(/{{[\s\S]*?}}/g, '');
const row = (code = 'PUL301') => ({ course_text: code, room_text: 'STEP A', course: '', room: 'step-a',
  day: 'Monday', start_time: '08:00', end_time: '09:00', page: 1, box: [20, 30, 100, 80], reviewed: false });

// Most cases use a minimal change-event hook; the dropdown integration test
// loads the actual jQuery/Select2 and catalogue controller bundled with Django.
function editor(t, rows = [row()], pending = { courses: [], rooms: [] }, options = {}) {
  const dom = new JSDOM(template, { url: 'http://localhost/', runScripts: 'outside-only' });
  t.after(() => dom.window.close());
  const { window } = dom;
  const document = window.document;
  window.django = { jQuery: el => ({ on: (name, callback) => el.addEventListener(name, callback) }) };
  if (options.realWidgets) {
    const library = readdirSync(new URL('../../../../venv/lib/', import.meta.url)).find(name => name.startsWith('python'));
    const admin = new URL(`../../../../venv/lib/${library}/site-packages/django/contrib/admin/static/admin/js/`, import.meta.url);
    for (const path of ['vendor/jquery/jquery.js', 'vendor/select2/select2.full.js', 'jquery.init.js']) {
      window.eval(readFileSync(new URL(path, admin), 'utf8'));
    }
    window.eval(read('../../../rooms/static/rooms/catalog.js'));
  }
  window.HTMLElement.prototype.scrollIntoView = () => {};
  const creation = { can_add_course: true, can_add_room: true, can_add_building: true,
    course_catalogue: [], course_sources: {}, buildings: [], facilities: [],
    faculties: ['Faculty of Computing Science and Engineering'],
    room_names: [{ name: 'STEP A', aliases: [] }], room_types: ['Classroom'],
    building_names: ['Computer Building Complex', 'Hezekiah Oluwasanmi Library (HOL)'] };
  Object.assign(creation, options.creation || {});
  for (const [id, data] of Object.entries({
    'document-rows': rows,
    'document-references': { courses: [], rooms: [{ value: 'step-a', label: 'STEP A', keys: [] }] },
    'document-pages': [{ url: '/source', width: 200, height: 300 }],
    'document-pending': pending, 'document-creation-choices': creation, 'document-editor-state': options.editorState || {},
  })) {
    const script = document.createElement('script'); script.id = id; script.type = 'application/json';
    script.textContent = JSON.stringify(data); document.body.append(script);
  }
  document.getElementById('document-department').value = 'Public Law';
  window.eval(read('./clock.js'));
  window.eval(read('./course_suggestions.js'));
  let saver;
  if (options.fetch) {
    window.fetch = options.fetch;
    window.AbortSignal = AbortSignal;
    document.getElementById('document-review').dataset.autosaveUrl = '/autosave/';
    const csrf = document.createElement('input'); csrf.name = 'csrfmiddlewaretoken'; csrf.value = 'test-csrf';
    document.getElementById('document-review').append(csrf);
    window.eval(read('./draft_autosave.js'));
    const factory = window.OptispaceDraftAutosave;
    window.OptispaceDraftAutosave = options => { saver = factory(options); return saver; };
  }
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
      pending: JSON.parse(document.getElementById('pending-records').value),
      editorState: JSON.parse(document.getElementById('editor-state').value) };
  }
  const mapping = code => [...document.querySelectorAll('.reference-mapping')]
    .find(el => el.querySelector('strong')?.textContent.includes(`“${code}”`));
  return { document, window, button, field, change, payload, mapping, saver };
}

test('background save captures partially typed forms, selections and rows without importing records', async t => {
  const requests = [];
  const e = editor(t, [row()], undefined, { fetch: async (url, init) => {
    requests.push({ url, data: new URLSearchParams(init.body.toString()) });
    return { ok: true, json: async () => ({ token: 'fresh-token' }) };
  } });
  const course = e.mapping('PUL301').querySelector('.record-editor');
  const title = e.field(course, 'Course title'); title.value = 'Partially entered law title';
  title.dispatchEvent(new e.window.Event('input', { bubbles: true }));
  e.document.getElementById('source-version').value = 'Revised';
  e.document.getElementById('source-version').dispatchEvent(new e.window.Event('input', { bubbles: true }));
  e.change(e.document.getElementById('coverage-checked'), true);
  await Promise.resolve(); await e.saver.flush();
  assert.equal(requests.length, 1);
  const sent = requests[0].data;
  assert.equal(sent.get('source_version'), 'Revised');
  assert.equal(sent.get('coverage_checked'), 'yes');
  assert.deepEqual(JSON.parse(sent.get('pending')), { courses: [], rooms: [], buildings: [] });
  assert.match(sent.get('editor_state'), /Partially entered law title/);
  assert.equal(sent.has('image'), false);
  assert.equal(e.document.getElementById('draft-save-error').hidden, true);
  assert.equal(e.document.querySelector('#document-review [name="document_token"]').value, 'fresh-token');
  const resumed = editor(t, JSON.parse(sent.get('rows')), JSON.parse(sent.get('pending')), { editorState: JSON.parse(sent.get('editor_state')) });
  assert.equal(resumed.field(resumed.mapping('PUL301').querySelector('.record-editor'), 'Course title').value, title.value);
  const filter = e.document.getElementById('review-search'); filter.value = 'PUL301';
  filter.dispatchEvent(new e.window.Event('input', { bubbles: true }));
  await Promise.resolve(); await e.saver.flush();
  assert.equal(requests.length, 1, 'Search-only actions do not trigger writes');
});

test('unfinished room selectors and custom names are restored without applying the proposal', t => {
  const e = editor(t, [{ ...row(), room: '' }]);
  const room = e.mapping('STEP A').querySelector('.record-editor');
  e.change(e.field(room, 'Building'), 'new');
  e.change(e.field(room, 'New building name'), '__other__');
  const custom = e.field(room, 'Custom new building name'); custom.value = 'New teaching block';
  custom.dispatchEvent(new e.window.Event('input', { bubbles: true }));
  const saved = e.payload();
  assert.equal(saved.pending.rooms.length, 0);
  const resumed = editor(t, saved.rows, saved.pending, { editorState: saved.editorState });
  const restored = resumed.mapping('STEP A').querySelector('.record-editor');
  assert.equal(resumed.field(restored, 'Building').value, 'new');
  assert.equal(resumed.field(restored, 'New building name').value, '__other__');
  assert.equal(resumed.field(restored, 'Custom new building name').value, 'New teaching block');
});

test('partially typed times survive a save and heading confirmation replaces their raw input', t => {
  const e = editor(t, [{ ...row(), time_group: 'time-1', time_text: '8–9', time_checked: false }]);
  const time = e.document.querySelector('input[aria-label="Start time, row 1 (AM/PM)"]');
  time.value = '2:'; time.dispatchEvent(new e.window.Event('input', { bubbles: true }));
  const saved = e.payload();
  assert.equal(saved.rows[0].start_time, '');
  assert.equal(saved.rows[0].start_time_input, '2:');
  const resumed = editor(t, saved.rows, saved.pending, { editorState: saved.editorState });
  assert.equal(resumed.document.querySelector('input[aria-label="Start time, row 1 (AM/PM)"]').value, '2:');
  const heading = resumed.document.querySelector('#heading-mappings .heading-mapping');
  const start = heading.querySelector('input'); start.value = '2:00 PM';
  start.dispatchEvent(new resumed.window.Event('input', { bubbles: true }));
  const end = heading.querySelectorAll('input')[1]; end.value = '3:00 PM';
  end.dispatchEvent(new resumed.window.Event('input', { bubbles: true }));
  resumed.button(heading, 'Confirm corrected heading');
  const corrected = resumed.payload();
  assert.equal(corrected.rows[0].start_time, '14:00');
  assert.equal(corrected.rows[0].start_time_input, undefined);
  assert.equal(resumed.document.querySelector('input[aria-label="Start time, row 1 (AM/PM)"]').value, '2:00 PM');
});

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

test('selecting a saved semester shows its shared dates and invalidates the old preview', t => {
  const e = editor(t);
  assert.equal(e.document.querySelector('input[name="first_date"]'), null);
  assert.equal(e.document.querySelector('input[name="last_date"]'), null);
  const select = e.document.getElementById('teaching-semester');
  const option = e.document.createElement('option');
  option.value = '12'; option.textContent = '2029/2030 — Rain';
  option.dataset.period = '7 Jan 2030 – 21 Jan 2030'; option.dataset.breaks = '2030-01-14';
  select.append(option);
  const preview = e.document.getElementById('document-final-preview');
  preview.hidden = false;
  e.change(select, '12');
  assert.match(e.document.getElementById('semester-dates-summary').textContent, /7 Jan 2030 – 21 Jan 2030/);
  assert.match(e.document.getElementById('semester-dates-summary').textContent, /2030-01-14/);
  assert.equal(preview.hidden, true);
  const form = new e.window.FormData(e.document.getElementById('document-review'));
  assert.equal(form.get('teaching_semester'), '12');
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
  assert.equal(saved.pending.buildings[0].name, 'Computer Building Complex');
  assert.equal(saved.pending.rooms[0].building, saved.pending.buildings[0].key);
  assert.equal(saved.pending.rooms[0].building_name, undefined);
  assert.equal(saved.pending.rooms[0].name, 'STEP A');
  const proposed = e.document.querySelector('#prepared-buildings .record-editor');
  e.change(e.field(proposed, 'Building name'), '__other__');
  e.field(proposed, 'Custom building name').value = 'Verified teaching block';
  e.button(proposed, 'Update prepared building');
  const updated = e.payload();
  assert.equal(updated.pending.buildings[0].name, 'Verified teaching block');
  assert.equal(updated.pending.rooms[0].building, saved.pending.buildings[0].key);
  assert.match(e.field(e.document.querySelector('#proposed-records .record-editor'), 'Building').selectedOptions[0].textContent, /Verified teaching block/);
});

test('a building prepared in one unfinished room is immediately reusable and autosaved with other unfinished rooms', async t => {
  const requests = [];
  const e = editor(t, [{ ...row(), room: '' }, { ...row(), room_text: 'STEP B', room: '', day: 'Tuesday' }], undefined, {
    fetch: async (url, init) => {
      requests.push(new URLSearchParams(init.body.toString()));
      return { ok: true, json: async () => ({ token: 'building-draft-token' }) };
    },
    creation: { room_names: [{ name: 'STEP A', aliases: [] }, { name: 'STEP B', aliases: [] }] },
  });
  const a = e.mapping('STEP A').querySelector('.record-editor');
  const b = e.mapping('STEP B').querySelector('.record-editor');
  e.change(e.field(b, 'Room type'), 'Classroom');
  e.change(e.field(b, 'Capacity'), '45');
  e.change(e.field(b, 'Size category'), 'small');
  e.change(e.field(a, 'Building'), 'new');
  e.change(e.field(a, 'New building name'), 'Computer Building Complex');
  e.change(e.field(a, 'New building campus area'), 'Faculty of Computing Science and Engineering');
  e.button(a, 'Prepare building and reuse it');
  const building = { key: e.field(a, 'Building').value };
  assert.match(building.key, /^draft-building-/);
  const bBuilding = e.field(b, 'Building');
  assert.ok(bBuilding.classList.contains('room-catalog-select'));
  assert.ok([...bBuilding.options].some(option => option.value === building.key));
  assert.equal(e.field(a, 'Building').value, building.key);
  e.change(bBuilding, building.key);
  assert.match(b.textContent, /Campus area: Faculty of Computing Science and Engineering/);
  assert.equal(e.field(b, 'New building campus area').parentElement.hidden, true);
  assert.equal(e.field(b, 'Capacity').value, '45', 'Refreshing choices preserves other unfinished fields');
  await Promise.resolve(); await e.saver.flush();
  assert.equal(requests.length, 1);
  const sent = requests[0];
  const persisted = JSON.parse(sent.get('pending'));
  assert.equal(persisted.buildings.length, 1);
  assert.equal(persisted.rooms.length, 0);
  const resumed = editor(t, JSON.parse(sent.get('rows')), persisted, {
    editorState: JSON.parse(sent.get('editor_state')),
    creation: { room_names: [{ name: 'STEP A', aliases: [] }, { name: 'STEP B', aliases: [] }] },
  });
  const restoredA = resumed.mapping('STEP A').querySelector('.record-editor');
  assert.equal(resumed.field(restoredA, 'Building').value, building.key);
  resumed.change(resumed.field(restoredA, 'Room type'), 'Classroom');
  resumed.change(resumed.field(restoredA, 'Capacity'), '80');
  resumed.change(resumed.field(restoredA, 'Size category'), 'large');
  resumed.button(restoredA, 'Use new record for matching entries');
  const restoredB = resumed.mapping('STEP B').querySelector('.record-editor');
  assert.equal(resumed.field(restoredB, 'Building').value, building.key);
  assert.equal(resumed.field(restoredB, 'Capacity').value, '45');
  resumed.button(restoredB, 'Use new record for matching entries');
  const saved = resumed.payload();
  assert.equal(saved.pending.buildings.length, 1);
  assert.equal(saved.pending.rooms.length, 2);
  assert.ok(saved.pending.rooms.every(room => room.building === building.key));
});

test('shared building edits update both rooms and removing the first room keeps the second room linked', t => {
  const key = 'draft-building-12345678';
  const rooms = ['STEP A', 'STEP B'].map((name, index) => ({ key: `draft-room-${index ? '87654321' : '12345678'}`,
    name, building: key, room_type: 'Classroom', capacity: '70', size_category: 'large', facilities: [] }));
  const pending = { courses: [], rooms, buildings: [{ key, name: 'Computer Building Complex', campus_zone: 'Faculty of Computing Science and Engineering' }] };
  const e = editor(t, rooms.map(room => ({ ...row(), room: room.key, room_text: room.name, reviewed: true })), pending, {
    creation: { faculties: ['Faculty of Computing Science and Engineering', 'Faculty of Science'] },
  });
  const building = e.document.querySelector('#prepared-buildings .record-editor');
  e.change(e.field(building, 'Building name'), '__other__');
  e.change(e.field(building, 'Custom building name'), 'Verified teaching block');
  e.change(e.field(building, 'Campus area'), 'Faculty of Science');
  e.button(building, 'Update prepared building');
  assert.ok(e.payload().rows.every(row => !row.reviewed), 'Location edits require a fresh review');
  for (const room of e.document.querySelectorAll('#proposed-records .record-editor')) {
    assert.equal(e.field(room, 'Building').value, key);
    assert.match(e.field(room, 'Building').selectedOptions[0].textContent, /Verified teaching block — Faculty of Science/);
    assert.match(room.textContent, /Campus area: Faculty of Science/);
  }
  e.button(e.document.querySelector('#proposed-records > details'), 'Remove proposed record');
  const saved = e.payload();
  assert.equal(saved.pending.rooms.length, 1);
  assert.equal(saved.pending.rooms[0].name, 'STEP B');
  assert.equal(saved.pending.rooms[0].building, key);
  assert.equal(saved.pending.buildings.length, 1);
  const resumed = editor(t, saved.rows, saved.pending, { editorState: saved.editorState });
  assert.equal(resumed.field(resumed.document.querySelector('#proposed-records .record-editor'), 'Building').value, key);
});

test('repeated legacy building details become one reusable choice while conflicting campus areas need correction', t => {
  const rooms = ['STEP A', 'STEP B'].map((name, index) => ({ key: `draft-room-${index ? '87654321' : '12345678'}`,
    name, building: 'new', building_name: 'Computer Building Complex', campus_zone: 'Faculty of Computing Science and Engineering',
    room_type: 'Classroom', capacity: '70', size_category: 'large', facilities: [] }));
  const e = editor(t, rooms.map(room => ({ ...row(), room: room.key, room_text: room.name })), { courses: [], rooms }, {
    creation: { faculties: ['Faculty of Computing Science and Engineering', 'Faculty of Science'] },
  });
  const upgraded = e.payload();
  assert.equal(upgraded.pending.buildings.length, 1);
  assert.ok(upgraded.pending.rooms.every(room => room.building === upgraded.pending.buildings[0].key));
  const b = e.document.querySelectorAll('#proposed-records .record-editor')[1];
  e.change(e.field(b, 'Building'), 'new');
  e.change(e.field(b, 'New building name'), 'Computer Building Complex');
  e.change(e.field(b, 'New building campus area'), 'Faculty of Science');
  e.button(b, 'Prepare building and reuse it');
  assert.match(b.querySelector('[role=alert]').textContent, /already prepared/);
  assert.equal(e.payload().pending.buildings.length, 1);
  assert.equal(e.payload().pending.buildings[0].campus_zone, 'Faculty of Computing Science and Engineering');
  e.change(e.field(b, 'New building campus area'), 'Faculty of Computing Science and Engineering');
  e.button(b, 'Prepare building and reuse it');
  assert.equal(e.field(b, 'Building').value, upgraded.pending.buildings[0].key);
  assert.equal(e.payload().pending.buildings.length, 1);
});

test('real searchable widgets show shared buildings immediately and preserve other room fields', t => {
  const e = editor(t, [{ ...row(), room: '' }, { ...row(), room_text: 'STEP B', room: '' }], undefined, { realWidgets: true });
  const $ = e.window.django.jQuery;
  const a = e.mapping('STEP A').querySelector('.record-editor');
  const b = e.mapping('STEP B').querySelector('.record-editor');
  const aBuilding = e.field(a, 'Building');
  const bBuilding = e.field(b, 'Building');
  assert.ok($(bBuilding).data('select2'));
  $(aBuilding).val('new').trigger('change');
  $(e.field(a, 'New building name')).val('Computer Building Complex').trigger('change');
  e.change(e.field(a, 'New building campus area'), 'Faculty of Computing Science and Engineering');
  e.change(e.field(b, 'Capacity'), '45');
  e.button(a, 'Prepare building and reuse it');
  const key = aBuilding.value;
  $(bBuilding).select2('open');
  const search = e.document.querySelector('.select2-container--open .select2-search__field');
  $(search).val('computer').trigger('input');
  const result = [...e.document.querySelectorAll('.select2-results__option')].find(option => option.textContent.includes('Prepared: Computer Building Complex'));
  assert.ok(result, 'The open searchable dropdown includes the prepared building');
  $(result).trigger('mouseup');
  assert.equal(bBuilding.value, key);
  assert.equal(e.field(b, 'Capacity').value, '45');
  assert.equal(e.field(b, 'New building campus area').parentElement.hidden, true);
  assert.match($(bBuilding).next('.select2').text(), /Computer Building Complex/);
  const prepared = e.document.querySelector('#prepared-buildings .record-editor');
  $(e.field(prepared, 'Building name')).val('__other__').trigger('change');
  e.change(e.field(prepared, 'Custom building name'), 'Verified academic block');
  e.button(prepared, 'Update prepared building');
  assert.equal(bBuilding.value, key);
  assert.match($(bBuilding).next('.select2').text(), /Verified academic block/);
  assert.equal(e.payload().pending.buildings.length, 1);
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
