import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function setup(send = async () => ({ token: 'next' })) {
  let value = '', sequence = 0;
  const timers = new Map(), calls = [], warnings = [], accepted = [];
  const window = {};
  vm.runInNewContext(readFileSync(new URL('./draft_autosave.js', import.meta.url), 'utf8'), { window, Date, JSON, Math });
  const save = window.OptispaceDraftAutosave({ snapshot: () => ({ value }),
    send: state => { calls.push(state); return send(state); },
    warn: text => warnings.push(text), accept: result => accepted.push(result),
    timers: { setTimeout(fn, delay) { timers.set(++sequence, { fn, delay }); return sequence; },
      clearTimeout(key) { timers.delete(key); } },
  });
  return { save, calls, warnings, accepted, timers, edit(text) { value = text; save.changed(); } };
}
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };

test('rapid edits collapse to the latest value and successful saves remain silent', async () => {
  const e = setup();
  e.edit('C'); e.edit('CS'); e.edit('CSC102');
  assert.equal(e.timers.size, 1);
  assert.equal(e.calls.length, 0);
  await e.save.flush();
  assert.deepEqual(e.calls, [{ value: 'CSC102' }]);
  assert.deepEqual(e.warnings, ['']);
  assert.equal(e.save.dirty(), false);
  e.edit('CSC102');
  assert.equal(e.timers.size, 0);
});

test('typing during an in-flight save queues a second save without overwriting live input', async () => {
  const gate = deferred();
  const e = setup(() => e.calls.length === 1 ? gate.promise : Promise.resolve({ token: 'third' }));
  e.edit('first'); const first = e.save.flush();
  e.edit('latest'); e.save.flush();
  assert.equal(e.calls.length, 1);
  gate.resolve({ token: 'second' }); await first;
  assert.equal(e.save.dirty(), true);
  await e.save.flush();
  assert.deepEqual(e.calls.map(item => item.value), ['first', 'latest']);
  assert.equal(e.save.dirty(), false);
});

test('lost responses retry the original request before sending newer edits', async () => {
  let fail = true;
  const e = setup(async () => { if (fail) { fail = false; throw new Error('Offline; will retry'); } return { token: 'saved' }; });
  e.edit('first'); await e.save.flush();
  assert.equal(e.save.dirty(), true);
  assert.equal(e.timers.size, 1);
  e.edit('second'); await e.save.flush(); await e.save.flush();
  assert.deepEqual(e.calls.map(item => item.value), ['first', 'first', 'second']);
  assert.equal(e.save.dirty(), false);
  assert.equal(e.warnings.at(-1), '');
});

test('conflicting tabs stop retries and prevent manual overwrite', async () => {
  const e = setup(async () => { throw Object.assign(new Error('Draft changed in another tab'), { permanent: true }); });
  e.edit('stale'); await e.save.flush();
  assert.equal(await e.save.beforeSubmit(), false);
  e.edit('still stale'); await e.save.flush();
  assert.equal(e.calls.length, 1);
  assert.equal(e.timers.size, 0);
  assert.match(e.warnings[0], /another tab/);
});

test('manual submission waits for current autosave and cancels queued background writes', async () => {
  const gate = deferred(); const e = setup(() => gate.promise);
  e.edit('first'); e.save.flush(); e.edit('latest');
  let finished = false;
  const submit = e.save.beforeSubmit().then(result => { finished = result; });
  await Promise.resolve(); assert.equal(finished, false);
  gate.resolve({ token: 'newest-token' }); await submit;
  assert.equal(finished, true);
  assert.equal(e.calls.length, 1);
  assert.equal(e.timers.size, 0);
  assert.equal(e.accepted[0].token, 'newest-token');
});

test('failed save cannot be silently bypassed by manual submission', async () => {
  const e = setup(async () => { throw new Error('Disconnected'); });
  e.edit('latest'); await e.save.flush();
  assert.equal(await e.save.beforeSubmit(), false);
  assert.equal(e.calls.length, 2);
  assert.equal(e.save.dirty(), true);
});
