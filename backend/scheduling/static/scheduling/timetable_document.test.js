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
    'document-level-profiles': options.levelProfiles || [],
    'document-source-heading': options.heading || '',
    'document-references': options.references || { courses: [], rooms: [{ value: 'step-a', label: 'STEP A', keys: [] }] },
    'document-pages': [{ url: '/source', width: 200, height: 300 }],
    'document-pending': pending, 'document-creation-choices': creation, 'document-editor-state': options.editorState || {},
  })) {
    const script = document.createElement('script'); script.id = id; script.type = 'application/json';
    script.textContent = JSON.stringify(data); document.body.append(script);
  }
  document.getElementById('document-department').value = options.department ?? 'Public Law';
  document.getElementById('level-view').dataset.saved = options.partOptions?.level_view || 'all';
  window.eval(read('./clock.js'));
  window.eval(read('./course_suggestions.js'));
  window.eval(read('./part_selection.js'));
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

test('Validate waits for autosave and sends selected scope plus all draft rows for preservation', { timeout: 5000 }, async t => {
  let finishFirst, finishSubmit;
  const firstResponse = new Promise(resolve => { finishFirst = resolve; });
  const submitted = new Promise(resolve => { finishSubmit = resolve; });
  const requests = [], submissions = [];
  const rows = [3, 4].map(part => ({ ...row('CSC201'), course: 'CSC201',
    class_group_kind: 'part', class_group: String(part), reviewed: true, day: part === 3 ? 'Monday' : 'Tuesday' }));
  const e = editor(t, rows, undefined, { references: {
    courses: [{ value: 'CSC201', label: 'CSC201', keys: [] }], rooms: [{ value: 'step-a', label: 'STEP A', keys: [] }],
  }, fetch: async (_, init) => {
    requests.push(new URLSearchParams(init.body.toString()));
    return requests.length === 1 ? firstResponse : { ok: true, json: async () => ({ token: 'latest-token' }) };
  } });
  const form = e.document.getElementById('document-review');
  form.querySelector('[name="document_token"]').value = 'original-token';
  e.window.HTMLFormElement.prototype.submit = function () {
    submissions.push(new e.window.FormData(this)); finishSubmit();
  };
  e.change(e.document.getElementById('level-view'), '3');
  const version = e.document.getElementById('source-version');
  version.value = 'First draft'; version.dispatchEvent(new e.window.Event('input', { bubbles: true }));
  const firstSave = e.saver.flush();
  version.value = 'Revised draft'; version.dispatchEvent(new e.window.Event('input', { bubbles: true }));
  const submitter = [...form.querySelectorAll('button')].find(button => button.textContent === 'Validate reviewed entries');
  form.dispatchEvent(new e.window.SubmitEvent('submit', { cancelable: true, submitter }));
  assert.equal(submissions.length, 0);
  finishFirst({ ok: true, json: async () => ({ token: 'autosaved-token' }) });
  await firstSave; await submitted;
  assert.equal(requests.length, 2);
  assert.equal(requests[1].get('document_token'), 'autosaved-token');
  assert.equal(submissions.length, 1);
  const data = submissions[0];
  assert.equal(data.get('document_token'), 'latest-token');
  assert.deepEqual(data.getAll('action'), ['review']);
  assert.equal(data.get('source_version'), 'Revised draft');
  assert.equal(data.get('level_view'), '3');
  assert.deepEqual(JSON.parse(data.get('rows')).map(row => row.class_group), ['3', '4']);
  assert.equal(e.saver.dirty(), false);
});

test('import scope text follows Part selection and resets coverage confirmation without removing other levels', t => {
  const rows = [1, 2].map(part => ({ ...row('CSC201'), course: 'CSC201',
    class_group_kind: 'part', class_group: String(part), reviewed: part === 1, day: part === 1 ? 'Monday' : 'Tuesday' }));
  const e = editor(t, rows, undefined, { references: {
    courses: [{ value: 'CSC201', label: 'CSC201', keys: [] }], rooms: [{ value: 'step-a', label: 'STEP A', keys: [] }],
  } });
  const coverage = e.document.getElementById('coverage-checked');
  e.change(coverage, true);
  e.change(e.document.getElementById('level-view'), '1');
  assert.equal(coverage.checked, false);
  assert.match(e.document.getElementById('part-status').textContent, /Validation imports Part 1 \(100 level\) only/);
  assert.match(e.document.getElementById('import-scope-status').textContent, /1 other entries stay in this draft/);
  assert.match(e.document.getElementById('coverage-label').textContent, /Part 1 \(100 level\)/);
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 1);
  assert.deepEqual(e.payload().rows.map(row => row.reviewed), [true, false]);
  e.change(coverage, true);
  e.change(e.document.getElementById('document-department'), 'Chemistry');
  assert.equal(coverage.checked, false, 'Changing departmental classification needs a fresh coverage check');
  e.change(e.document.getElementById('level-view'), 'all');
  assert.match(e.document.getElementById('import-scope-status').textContent, /All extracted entries · 2 weekly entries/);
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 2);
  assert.equal(e.payload().rows.length, 2);
});

test('a genuine draft conflict lets an administrator preserve unsaved edits in a separate draft', { timeout: 5000 }, async t => {
  const e = editor(t, [row()], undefined, { fetch: async () => ({ ok: false, status: 409,
    json: async () => ({ error: 'Newer saved changes exist', latest_token: 'latest-saved-token' }) }) });
  const courseTitle = e.field(e.mapping('PUL301').querySelector('.record-editor'), 'Course title');
  courseTitle.value = 'Keep this unsaved title';
  courseTitle.dispatchEvent(new e.window.Event('input', { bubbles: true }));
  await Promise.resolve(); await e.saver.flush();
  const recovery = e.document.getElementById('draft-conflict-recovery');
  assert.equal(recovery.hidden, false);
  assert.match(e.document.getElementById('latest-saved-draft').href, /review=latest-saved-token/);
  assert.equal(await e.saver.beforeSubmit(), false, 'Normal save/validate cannot overwrite a newer draft');
  const form = e.document.getElementById('document-review');
  form.querySelector('[name="document_token"]').value = 'stale-token';
  let finishSubmit;
  const done = new Promise(resolve => { finishSubmit = resolve; });
  const submissions = [];
  e.window.HTMLFormElement.prototype.submit = function () {
    submissions.push(new e.window.FormData(this)); finishSubmit();
  };
  const submitter = recovery.querySelector('button');
  form.dispatchEvent(new e.window.SubmitEvent('submit', { cancelable: true, submitter }));
  await done;
  const data = submissions[0];
  assert.deepEqual(data.getAll('action'), ['recover']);
  assert.equal(data.get('document_token'), 'stale-token');
  assert.match(data.get('editor_state'), /Keep this unsaved title/);
  assert.equal(JSON.parse(data.get('rows')).length, 1);
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
  const e = editor(t, [{ ...row(), room: '' }], undefined, { references: { courses: [], rooms: [] } });
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
    references: { courses: [], rooms: [] },
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
    references: { courses: [], rooms: [] },
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
    references: { courses: [], rooms: [] },
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
  const resumed = editor(t, saved.rows, saved.pending, { editorState: saved.editorState, references: { courses: [], rooms: [] } });
  assert.equal(resumed.field(resumed.document.querySelector('#proposed-records .record-editor'), 'Building').value, key);
});

test('repeated legacy building details become one reusable choice while conflicting campus areas need correction', t => {
  const rooms = ['STEP A', 'STEP B'].map((name, index) => ({ key: `draft-room-${index ? '87654321' : '12345678'}`,
    name, building: 'new', building_name: 'Computer Building Complex', campus_zone: 'Faculty of Computing Science and Engineering',
    room_type: 'Classroom', capacity: '70', size_category: 'large', facilities: [] }));
  const e = editor(t, rooms.map(room => ({ ...row(), room: room.key, room_text: room.name })), { courses: [], rooms }, {
    references: { courses: [], rooms: [] },
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

test('room and course matching search inside their dropdowns and enable the apply action', t => {
  const references = { rooms: [{ value: 'ch102', name: 'CH 102', label: 'CH 102 — Faculty of Science', keys: ['ch102'] },
    { value: 'step-a', name: 'STEP A', label: 'STEP A — Computing', keys: ['stepa'] }],
    courses: [{ value: 'CSC102', label: 'CSC102 — Introduction to Computing', keys: ['csc102'] },
      { value: 'CHM102', label: 'CHM102 — Chemistry', keys: ['chm102'] }] };
  const e = editor(t, [{ ...row('CSC107'), room: '', room_text: 'CH 107' }], undefined, { realWidgets: true, references });
  const $ = e.window.django.jQuery;
  assert.equal(e.document.querySelectorAll('#reference-mappings input[type="search"]').length, 0);
  for (const [text, kind, term, expected] of [['CH 107', 'room', 'ch102', 'ch102'], ['CSC107', 'course', 'computing', 'CSC102']]) {
    const mapping = e.mapping(text);
    const select = mapping.querySelector(`select[aria-label="Map ${kind} ${text}"]`);
    assert.ok($(select).data('select2'));
    const apply = [...mapping.querySelectorAll('button')].find(button => button.textContent === 'Use for all matching unresolved rows');
    assert.equal(apply.disabled, true);
    $(select).select2('open');
    const search = e.document.querySelector('.select2-container--open .select2-search__field');
    $(search).val(term).trigger('input');
    const matches = [...e.document.querySelectorAll('.select2-results__option')].filter(option => option.getAttribute('aria-selected') !== null);
    assert.equal(matches.length, 1, 'Typing inside the dropdown filters its choices');
    $(matches[0]).trigger('mouseup');
    assert.equal(select.value, expected);
    assert.equal(apply.disabled, false, 'Select2 selection enables the existing bulk mapping action');
    e.button(mapping, 'Use for all matching unresolved rows');
    assert.equal(e.payload().rows[0][kind], expected);
  }
  assert.equal(e.payload().rows[0].start_time, '08:00');
});

test('a saved room and prepared course are reused instead of creating duplicate proposals', t => {
  const courses = [{ key: 'draft-course-12345678', code: 'CSC102', title: 'Introduction', department: 'Computing' }];
  const e = editor(t, [{ ...row('CSC107'), room: '', room_text: 'CH 107' }, { ...row('CSC102'), course: courses[0].key }], { courses, rooms: [] }, {
    references: { courses: [], rooms: [{ value: 'ch102', name: 'CH 102', label: 'CH 102 — Science', keys: ['ch102'] }] },
    creation: { room_names: [{ name: 'Chemistry Lecture Theatre 102 (CH 102)', aliases: ['CH102', 'CH 102'] }] },
  });
  const room = e.mapping('CH 107').querySelector('.record-editor');
  e.change(e.field(room, 'Room name'), 'Chemistry Lecture Theatre 102 (CH 102)');
  e.button(room, 'Use new record for matching entries');
  assert.equal(e.payload().pending.rooms.length, 0, 'Saved room reuse needs no new capacity or building');
  assert.equal(e.payload().rows[0].room, 'ch102');
  const course = e.mapping('CSC107').querySelector('.record-editor');
  e.change(e.field(course, 'Course code'), 'csc 102');
  e.button(course, 'Use new record for matching entries');
  assert.equal(e.payload().pending.courses.length, 1);
  assert.equal(e.payload().rows[0].course, courses[0].key);
});

test('duplicate room proposals reopen as one choice with earlier details retained and are autosaved without new edits', async t => {
  const requests = [];
  const rooms = [60, 45].map((capacity, index) => ({ key: `draft-room-${index ? '87654321' : '12345678'}`,
    name: index ? 'ch102' : 'CH 102', building: '7', room_type: 'Classroom', capacity: String(capacity), size_category: 'small', facilities: [] }));
  const rows = rooms.map(room => ({ ...row(), room: room.key, room_text: room.name, reviewed: true }));
  const references = { courses: [], rooms: [{ value: 'ch102', name: 'CH 102', label: 'CH 102 — Science', keys: ['ch102'] }] };
  const e = editor(t, rows, { courses: [], rooms }, { references,
    fetch: async (url, init) => {
      requests.push(new URLSearchParams(init.body.toString()));
      return { ok: true, json: async () => ({ token: 'deduplicated-token' }) };
    },
    creation: { room_names: [{ name: 'Chemistry Lecture Theatre 102 (CH 102)', aliases: ['CH102', 'CH 102'] }] },
  });
  await Promise.resolve(); await e.saver.flush();
  assert.equal(requests.length, 1, 'Repairs save even if the administrator only reopens the draft');
  const sent = requests[0];
  const updatedRows = JSON.parse(sent.get('rows'));
  assert.ok(updatedRows.every(row => row.room === 'ch102' && !row.reviewed));
  assert.ok(updatedRows.every(row => row.start_time === '08:00' && row.day === 'Monday'));
  const updatedPending = JSON.parse(sent.get('pending'));
  assert.deepEqual(updatedPending.rooms.map(room => room.capacity), ['60', '45']);
  assert.ok(updatedPending.rooms.every(room => room.duplicate_of === 'ch102'));
  assert.match(e.document.querySelector('.duplicate-proposals').textContent, /60/);
  assert.match(e.document.querySelector('.duplicate-proposals').textContent, /45/);
  assert.equal(e.document.querySelectorAll('#proposed-records .record-editor').length, 0);
  const resumed = editor(t, updatedRows, updatedPending, { references, editorState: JSON.parse(sent.get('editor_state')) });
  const roomOptions = resumed.document.querySelector('select[aria-label="room, row 1"]');
  assert.equal([...roomOptions.options].filter(option => /CH 102/.test(option.textContent)).length, 1);
});

test('repeated prepared course codes share one proposal and remap saved mapping choices', t => {
  const courses = [false, true].map((second, index) => ({ key: `draft-course-${index ? '87654321' : '12345678'}`,
    code: second ? 'csc 102' : 'CSC102', title: second ? 'Earlier alternate title' : 'Introduction', department: 'Computing' }));
  const e = editor(t, [{ ...row(), course: courses[1].key, reviewed: true }, row('CSC107')], { courses, rooms: [] }, {
    editorState: { 'mapping:course:csc107:choice': courses[1].key },
  });
  const saved = e.payload();
  assert.equal(saved.rows[0].course, courses[0].key);
  assert.equal(saved.rows[0].reviewed, false);
  const choice = e.mapping('CSC107').querySelector('select[aria-label="Map course CSC107"]');
  assert.equal(choice.value, courses[0].key);
  assert.equal([...choice.options].filter(option => option.value.startsWith('draft-course')).length, 1);
  assert.match(e.document.querySelector('.duplicate-proposals').textContent, /Earlier alternate title/);
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

const curriculumProfiles = [{ id: 'programme-a', programme: 'Programme A', source_id: 'source-a', entries: [
  { code: 'CSC201', level: 3, page: 27, heading: 'PART III' },
  { code: 'MAC201', level: 4, page: 28, heading: 'PART IV' },
  { code: 'BIO101', level: 1, page: 26, heading: 'PART I' },
  { code: 'BIO101', level: 2, page: 27, heading: 'PART II' },
] }, { id: 'programme-b', programme: 'Programme B', source_id: 'source-b', entries: [
  { code: 'CSC201', level: 4, page: 45, heading: 'PART IV' },
] }];
const courseRefs = { courses: [ { value: 'CSC201', label: 'CSC201 — Computing', keys: [] },
  { value: 'MAC201', label: 'MAC201 — Management', keys: [] } ],
  rooms: [{ value: 'step-a', label: 'STEP A', keys: [] }, { value: 'step-b', label: 'STEP B', keys: [] }] };
const curriculumChoices = { course_sources: {
  'source-a': { edition: '2023', source_title: 'Programme A handbook', source_url: '/handbook-a/' },
  'source-b': { edition: '2024', source_title: 'Programme B handbook', source_url: '/handbook-b/' }
} };

test('selecting a Part filters courses, venues, weekly cards, shared headings, day groups and extracted entries', t => {
  const rows = [{ ...row('CSC201'), editor_id: 'part-three', course: 'CSC201', room: '', day_group: 'mon', time_group: 'morning',
    day_checked: false, time_checked: false },
  { ...row('MAC201'), editor_id: 'part-four', course: 'MAC201', room: '', room_text: 'STEP B', day: 'Tuesday',
    day_group: 'tue', time_group: 'afternoon', start_time: '14:00', end_time: '15:00' }];
  const e = editor(t, rows, undefined, { department: 'Programme A', levelProfiles: curriculumProfiles, creation: curriculumChoices, references: courseRefs });
  const level = e.document.getElementById('level-view');
  e.change(level, '3');
  assert.ok(e.mapping('STEP A')); assert.equal(e.mapping('STEP B'), undefined);
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 1);
  assert.match(e.document.querySelector('.weekly-card').textContent, /CSC201/);
  assert.equal(e.document.querySelectorAll('.heading-mapping').length, 2);
  assert.match(e.document.getElementById('heading-mappings').textContent, /2 entries|1 entries/);
  e.change(e.document.getElementById('review-filter'), 'all');
  e.document.getElementById('review-filter').dispatchEvent(new e.window.Event('input', { bubbles: true }));
  const table = e.document.querySelector('#document-table tbody');
  assert.equal(table.children.length, 1);
  assert.deepEqual([...table.querySelectorAll('select[aria-label^="course,"]')].map(el => el.value), ['CSC201']);
  assert.ok(table.querySelector('.part-evidence a[href="/handbook-a/#page=27"]'));
  e.change(level, '4');
  assert.ok(e.mapping('STEP B')); assert.equal(e.mapping('STEP A'), undefined);
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 1);
  assert.deepEqual([...table.querySelectorAll('select[aria-label^="course,"]')].map(el => el.value), ['MAC201']);
  assert.equal(e.payload().rows.length, 2, 'Filtering preserves the full extracted timetable');
  e.change(level, 'all');
  assert.ok(e.mapping('STEP A')); assert.ok(e.mapping('STEP B'));
  assert.equal(table.children.length, 2);
  const ready = editor(t, [{ ...row('CSC201'), course: 'CSC201' }, { ...row('MAC201'), course: 'MAC201', day:'Tuesday' }], undefined,
    { department: 'Programme A', levelProfiles: curriculumProfiles, references: courseRefs, partOptions: {level_view:'3'} });
  assert.match(ready.document.getElementById('ready-groups').textContent, /Monday/);
  assert.doesNotMatch(ready.document.getElementById('ready-groups').textContent, /Tuesday/);
});

test('department matching assigns Parts automatically and updates when the department is edited', t => {
  const e = editor(t, [row('CSC201'), row('BIO101'), row('ICH308')], undefined, { department: '', levelProfiles: curriculumProfiles });
  const department = e.document.getElementById('document-department');
  const level = e.document.getElementById('level-view');
  const partLabel = part => [...level.options].find(option => option.value === part).textContent;
  assert.equal(e.document.getElementById('level-profile'), null);
  assert.equal(e.document.getElementById('level-profile-confirmed'), null);
  assert.match(e.document.getElementById('part-department-status').textContent, /Enter the department above/);
  e.change(level, '3');
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 0);
  department.value = 'Programme A';
  department.dispatchEvent(new e.window.Event('input', { bubbles: true }));
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 1);
  assert.match(partLabel('3'), /1 entries$/);
  assert.match(e.document.getElementById('part-department-status').textContent, /matched automatically for Programme A/);
  e.change(level, 'unassigned');
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 2);
  e.change(department, 'Programme B');
  assert.equal(level.value, 'unassigned');
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 2);
  e.change(level, '4');
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 1, 'Department-specific evidence replaces the previous match');
  assert.match(partLabel('4'), /1 entries$/);
  e.change(department, 'Unknown department');
  assert.match(e.document.getElementById('part-department-status').textContent, /No applicable Part catalogue/);
  e.change(level, 'all');
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 3);
  assert.deepEqual(e.payload().rows.map(row => row.course_text), ['CSC201', 'BIO101', 'ICH308']);
});

test('automatic matching preserves image and manual Parts, corrections and completed review', t => {
  const rows = [
    { ...row('ICH308'), class_group_kind: 'part', class_group: 'III', reviewed: true },
    { ...row('MAC201'), level_override: [4], level_override_code: 'MAC201', day: 'Tuesday', reviewed: true },
    row('CSC201'),
    { ...row('CSC201'), skip: true },
  ];
  const e = editor(t, rows, undefined, { department: 'Programme A', levelProfiles: curriculumProfiles,
    partOptions: { level_view: '3' } });
  const level = e.document.getElementById('level-view');
  const partLabel = part => [...level.options].find(option => option.value === part).textContent;
  assert.match(partLabel('all'), /3 entries$/);
  assert.match(partLabel('3'), /2 entries$/);
  assert.match(partLabel('4'), /1 entries$/);
  assert.match(partLabel('2'), /0 entries$/);
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 2);
  assert.match(e.document.querySelector('.weekly-card').textContent, /ICH308/);
  e.change(level, '4');
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 1);
  assert.match(e.document.querySelector('.weekly-card').textContent, /MAC201/);
  e.change(e.document.getElementById('document-department'), 'Unknown department');
  assert.match(partLabel('3'), /1 entries$/);
  assert.match(partLabel('4'), /1 entries$/);
  assert.deepEqual(e.payload().rows.map(row => [row.day, row.reviewed, !!row.skip]),
    rows.map(row => [row.day, row.reviewed, !!row.skip]));
});

test('bulk review and shared-heading corrections only change the selected Part', t => {
  const rows = [3, 4].map((part, index) => ({ ...row(index ? 'MAC201' : 'CSC201'), course: index ? 'MAC201' : 'CSC201',
    class_group_kind: 'part', class_group: String(part), day_group:'shared-day', day_text:'MONDAY', day_checked:false }));
  const e = editor(t, rows, undefined, { references:courseRefs });
  e.change(e.document.getElementById('level-view'), '3');
  const heading = e.document.querySelector('.heading-mapping');
  e.change(heading.querySelector('select'), 'Wednesday');
  e.button(heading, 'Confirm heading for these entries');
  const afterHeading = e.payload().rows;
  assert.deepEqual(afterHeading.map(row => row.day), ['Wednesday', 'Monday']);
  e.change(e.document.getElementById('weekly-checked'), true);
  e.button(e.document, 'Confirm clear entries together');
  assert.deepEqual(e.payload().rows.map(row => row.reviewed), [true, false]);
  e.change(e.document.getElementById('level-view'), '4');
  assert.match(e.document.getElementById('ready-groups').textContent, /No clear unreviewed groups/);
  e.change(e.document.getElementById('level-view'), '3');
  assert.equal(e.payload().rows[0].reviewed, true, 'Switching views preserves completed review');
});

test('source-card navigation targets the correct row after filtering and pagination', t => {
  const rows = Array.from({length:70}, (_, index) => ({ ...row('CSC201'), editor_id:`source-${index}`, course:'CSC201',
    class_group_kind:'part', class_group: index % 2 ? 'III' : 'IV' }));
  const e = editor(t, rows, undefined, { references:courseRefs });
  e.change(e.document.getElementById('level-view'), '3');
  const cards = [...e.document.querySelectorAll('.weekly-card')];
  assert.equal(cards.length, 35);
  cards[30].click();
  const table = e.document.querySelector('#document-table tbody');
  assert.match(e.document.getElementById('review-page-status').textContent, /26–35 of 35/);
  assert.match(table.children[5].textContent, /Row 62/);
  assert.deepEqual(e.payload().rows.map(row => row.editor_id), rows.map(row => row.editor_id));
});

test('overlap checks include other Parts while keeping the preview layout and existing warning behavior', t => {
  const rows = [3, 4].map(part => ({ ...row('CSC201'), course:'CSC201', class_group_kind:'part', class_group:String(part) }));
  const e = editor(t, rows, undefined, { references:courseRefs });
  e.change(e.document.getElementById('level-view'), '3');
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 1);
  assert.match(e.document.querySelector('.weekly-card').textContent, /Overlap — check/);
  assert.ok(e.document.querySelector('.weekly-grid'));
  e.change(e.document.getElementById('review-filter'), 'all');
  e.document.getElementById('review-filter').dispatchEvent(new e.window.Event('input', { bubbles: true }));
  const reviewed = [...e.document.querySelectorAll('#document-table input[type=checkbox]')]
    .find(el => el.parentElement.textContent.trim() === 'Reviewed');
  e.change(reviewed, true);
  assert.match(e.document.querySelector('.weekly-card').textContent, /Overlap — check/);
});

test('Part choice, unfinished assignment and full image edits autosave and reopen without resetting review', async t => {
  const requests = [];
  const e = editor(t, [{ ...row('ICH308'), editor_id:'unknown-1', reviewed:false },
    { ...row('MAC201'), editor_id:'part-four', class_group_kind:'part', class_group:'IV', reviewed:true }], undefined, {
      fetch: async (_, init) => { requests.push(new URLSearchParams(init.body.toString())); return {ok:true, json:async () => ({token:'saved-part-view'})}; }
    });
  e.change(e.document.getElementById('level-view'), 'unassigned');
  e.change(e.document.getElementById('review-filter'), 'all');
  const evidence = e.document.querySelector('.part-evidence');
  e.change([...evidence.querySelectorAll('label')].find(el => el.textContent === ' Part 3').querySelector('input'), true);
  await Promise.resolve(); await e.saver.flush();
  const sent = requests.at(-1);
  assert.equal(sent.get('level_view'), 'unassigned');
  assert.equal(JSON.parse(sent.get('rows')).length, 2);
  assert.equal(JSON.parse(sent.get('rows'))[1].reviewed, true);
  const saved = editor(t, JSON.parse(sent.get('rows')), JSON.parse(sent.get('pending')), {
    editorState:JSON.parse(sent.get('editor_state')), partOptions:{level_view:sent.get('level_view')}
  });
  assert.equal(saved.document.getElementById('level-view').value, 'unassigned');
  const restored = saved.document.querySelector('.part-evidence');
  assert.equal([...restored.querySelectorAll('label')].find(el => el.textContent === ' Part 3').querySelector('input').checked, true);
  saved.button(restored, 'Use checked Parts for this entry');
  assert.deepEqual(saved.payload().rows[0].level_override, [3]);
  assert.equal(saved.document.querySelectorAll('.weekly-card').length, 0);
  saved.change(saved.document.getElementById('level-view'), '3');
  assert.equal(saved.document.querySelectorAll('.weekly-card').length, 1);
});

test('manual Part assignment applies once to repeated code and does not guess its numeric level', t => {
  const e = editor(t, [{...row('ICH308'), editor_id:'ich-one'}, {...row('ICH308'), editor_id:'ich-two', day:'Tuesday'}]);
  e.change(e.document.getElementById('level-view'), 'unassigned');
  const evidence = e.document.querySelector('.part-evidence');
  e.change([...evidence.querySelectorAll('label')].find(el => el.textContent === ' Part 4').querySelector('input'), true);
  e.button(evidence, 'Use checked Parts for all 2 entries of ICH308');
  assert.deepEqual(e.payload().rows.map(row => row.level_override), [[4], [4]]);
  e.change(e.document.getElementById('level-view'), '4');
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 2);
  e.change(e.document.getElementById('review-filter'), 'all');
  const first = e.document.querySelector('#document-table tbody tr');
  e.change(first.querySelector('select[aria-label="course, row 1"]'), '');
  assert.equal(e.payload().rows[0].level_override_code, 'ICH308');
});

test('a combined Chemistry timetable uses both curricula without guessing conflicting Parts', t => {
  const profiles = JSON.parse(read('../../data/course_levels.json'));
  const sources = Object.fromEntries(JSON.parse(read('../../data/handbook_sources.json')).map(source => [source.id, source]));
  const e = editor(t, [row('CSC201'), row('CHM304'), row('MAC201'), row('ICH308'), row('ICH202')], undefined,
    { department: 'Chemistry', levelProfiles: profiles, creation: { course_sources: sources } });
  assert.match(e.document.getElementById('part-department-status').textContent, /BSc Chemistry; BSc Industrial Chemistry/);
  e.change(e.document.getElementById('level-view'), '3');
  assert.ok(e.mapping('CSC201'));
  assert.equal(e.mapping('CHM304'), undefined, 'CHM304 has differing curriculum Parts in the shared handbook');
  assert.equal(e.mapping('MAC201'), undefined); assert.equal(e.mapping('ICH308'), undefined);
  e.change(e.document.getElementById('level-view'), '2');
  assert.ok(e.mapping('ICH202'), 'Industrial Chemistry curriculum courses are included');
  e.change(e.document.getElementById('level-view'), 'unassigned');
  assert.ok(e.mapping('CHM304')); assert.ok(e.mapping('MAC201')); assert.ok(e.mapping('ICH308'));
  const evidence = e.document.querySelector('.part-evidence').textContent;
  assert.match(evidence, /BSc Chemistry.*Part 3/);
  assert.match(evidence, /BSc Industrial Chemistry.*Part 4/);
  e.change(e.document.getElementById('document-department'), 'Department of Chemistry and Industrial Chemistry');
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 3);
  e.change(e.document.getElementById('level-view'), 'all');
  assert.equal(e.document.querySelectorAll('.weekly-card').length, 5);
  assert.equal(e.payload().rows.length, 5);
});

test('department recognition works across the supplied catalogue and preserves curriculum boundaries', t => {
  const profiles = JSON.parse(read('../../data/course_levels.json'));
  const sources = Object.fromEntries(JSON.parse(read('../../data/handbook_sources.json')).map(source => [source.id, source]));
  const e = editor(t, [], undefined, { levelProfiles: profiles, creation: { course_sources: sources } });
  const ids = department => [...e.window.OptispacePartSelection.detect(department, profiles, sources).profiles].map(profile => profile.id);
  const departments = new Map();
  for (const profile of profiles) {
    const department = sources[profile.source_id].department;
    if (!department) continue;
    if (!departments.has(department)) departments.set(department, []);
    departments.get(department).push(profile.id);
  }
  for (const [department, expected] of departments) {
    assert.deepEqual(ids(`Department of ${department.toUpperCase().replace(/ and /gi, ' & ')} (OAU)`), expected);
  }
  assert.deepEqual(ids('Chemistry'), ['chemistry-2023', 'industrial-chemistry-2023']);
  assert.deepEqual(ids('Chemistry / Industrial Chemistry'), ['chemistry-2023', 'industrial-chemistry-2023']);
  assert.deepEqual(ids('Biochemistry and Molecular Biology'), ['biochemistry-2017']);
  assert.deepEqual(ids('Law'), ['law-llb']);
  assert.deepEqual(ids('Software Engineering'), ['software-engineering']);
  assert.deepEqual(ids('Architecture'), [], 'Course-title coverage alone is not verified Part evidence');
  assert.deepEqual(ids('English'), []);
  assert.deepEqual(ids('Chemistry and Unknown department'), [], 'Do not partially match an unknown joint heading');
});

test('automatic matching cannot apply historical B.Pharm Parts to a PharmD or unidentified Pharmacy timetable', t => {
  const profiles = JSON.parse(read('../../data/course_levels.json'));
  const sources = Object.fromEntries(JSON.parse(read('../../data/handbook_sources.json')).map(source => [source.id, source]));
  const e = editor(t, [], undefined, { levelProfiles: profiles, creation: { course_sources: sources } });
  const detect = heading => e.window.OptispacePartSelection.detect('Pharmacy', profiles, sources, heading);
  assert.equal(detect('').profiles.length, 0);
  assert.equal(detect('Doctor of Pharmacy (PharmD)').profiles.length, 0);
  assert.equal(detect('B.Pharm revised to PharmD').profiles.length, 0);
  assert.equal(detect('B.Pharm lecture timetable').profiles[0].id, 'pharmacy-bpharm-2019');
  assert.match(e.window.OptispacePartSelection.detect('Pharmacy', profiles, sources).restricted[0].notes, /does not apply to PharmD/);
});

test('department-based Part view autosaves and resumes without retired profile controls', async t => {
  const requests = [];
  const e = editor(t, [row('CSC201'), row('MAC201')], undefined, { department: 'Programme A', levelProfiles: curriculumProfiles,
    fetch: async (_, init) => { requests.push(new URLSearchParams(init.body.toString())); return { ok: true, json: async () => ({ token: 'department-draft' }) }; }
  });
  e.change(e.document.getElementById('level-view'), '3');
  e.change(e.document.getElementById('document-department'), 'Programme B');
  e.change(e.document.getElementById('level-view'), '4');
  await Promise.resolve(); await e.saver.flush();
  const sent = requests.at(-1);
  assert.equal(sent.get('department'), 'Programme B');
  assert.equal(sent.get('level_view'), '4');
  assert.equal(sent.has('level_profile'), false);
  assert.equal(sent.has('level_profile_confirmed'), false);
  const restored = editor(t, JSON.parse(sent.get('rows')), JSON.parse(sent.get('pending')), {
    department: sent.get('department'), levelProfiles: curriculumProfiles,
    editorState: JSON.parse(sent.get('editor_state')), partOptions: { level_view: sent.get('level_view') },
  });
  assert.equal(restored.document.querySelectorAll('.weekly-card').length, 1);
  assert.match(restored.document.querySelector('.weekly-card').textContent, /CSC201/);
  assert.equal(restored.payload().rows.length, 2);
  restored.change(restored.document.getElementById('level-view'), 'all');
  assert.equal(restored.document.querySelectorAll('.weekly-card').length, 2);
});

test('a missing entry added in the selected Part stays there when its first course is chosen', t => {
  const e = editor(t, [], undefined, { references:courseRefs });
  e.change(e.document.getElementById('level-view'), '3');
  e.button(e.document, 'Add missing entry');
  const course = e.document.querySelector('select[aria-label="course, row 1"]');
  assert.ok(course);
  e.change(course, 'CSC201');
  assert.equal(e.document.querySelector('#document-table tbody').children.length, 1);
  assert.equal(e.payload().rows[0].level_override_code, 'CSC201');
  const updated = e.document.querySelector('select[aria-label="course, row 1"]');
  e.change(updated, 'MAC201');
  assert.equal(e.document.querySelector('#document-table tbody').children.length, 0, 'A subsequent course-code change needs a new Part assignment');
  e.change(e.document.getElementById('level-view'), 'unassigned');
  assert.equal(e.document.querySelector('#document-table tbody').children.length, 1);
});
