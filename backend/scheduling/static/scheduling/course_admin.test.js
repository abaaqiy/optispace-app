import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
function editor(t, { code = '', title = '', pending = false } = {}) {
  const dom = new JSDOM('<input id="id_code"><input id="id_title"><input id="id_department"><input id="id_title_pending" type="checkbox"><div id="manual-course-matches"></div>', { url: 'http://localhost/', runScripts: 'outside-only' });
  t.after(() => dom.window.close());
  const { window } = dom, document = window.document;
  document.getElementById('id_code').value = code;
  document.getElementById('id_title').value = title;
  document.getElementById('id_title_pending').checked = pending;
  const payload = document.createElement('script'); payload.id = 'manual-course-catalogue'; payload.type = 'application/json';
  payload.textContent = JSON.stringify({ course_catalogue: JSON.parse(read('../../data/handbook_courses.json')), course_sources: Object.fromEntries(
    JSON.parse(read('../../data/handbook_sources.json')).map(source => [source.id, { ...source, source_title: source.filename, source_url: '/source/' + source.id }])
  ) }); document.body.append(payload);
  window.eval(read('./course_suggestions.js')); window.eval(read('./course_admin.js'));
  return { window, document, input: (id, value) => {
    const el = document.getElementById(id); el.value = value; el.dispatchEvent(new window.Event('input')); return el;
  } };
}

test('manual form offers exact title with source confirmation and clears pending only on selection', t => {
  const e = editor(t, { code: 'chm 102', pending: true });
  const candidate = [...e.document.querySelectorAll('#manual-course-matches > div')].find(el => el.textContent.includes('Introductory Chemistry II'));
  assert.ok(candidate);
  assert.match(candidate.querySelector('a').href, /\/source\/hb-.*#page=/);
  const button = candidate.querySelector('button');
  assert.equal(button.disabled, true);
  assert.equal(e.document.getElementById('id_title').value, '');
  const confirm = candidate.querySelector('input'); confirm.checked = true; confirm.dispatchEvent(new e.window.Event('change'));
  button.click();
  assert.equal(e.document.getElementById('id_title').value, 'Introductory Chemistry II');
  assert.equal(e.document.getElementById('id_department').value, 'Chemistry');
  assert.equal(e.document.getElementById('id_title_pending').checked, false);
});

test('editing codes and missing suggestions never replace a manually entered title', t => {
  const e = editor(t, { code: 'PUL101', title: 'Previously verified title' });
  assert.equal(e.document.getElementById('id_title').value, 'Previously verified title');
  assert.match(e.document.querySelector('#manual-course-matches').textContent, /Replace title with this suggestion/);
  e.input('id_code', 'ICH406');
  assert.match(e.document.querySelector('#manual-course-matches').textContent, /No verified title/);
  assert.equal(e.document.getElementById('id_title').value, 'Previously verified title');
  e.input('id_code', 'CSC102');
  assert.match(e.document.querySelector('#manual-course-matches').textContent, /Different titles or programmes/);
  assert.match(e.document.querySelector('#manual-course-matches').textContent, /code changed/);
  assert.equal(e.document.getElementById('id_title').value, 'Previously verified title');
});
