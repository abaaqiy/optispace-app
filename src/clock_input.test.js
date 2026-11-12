import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';
import { transformWithOxc } from 'vite';

test('AM/PM input keeps incomplete edits, submits canonical times and follows resets', async t => {
  const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost/' });
  const previous = Object.fromEntries(['window', 'document', 'IS_REACT_ACT_ENVIRONMENT'].map(key => [key, globalThis[key]]));
  globalThis.window = dom.window; globalThis.document = dom.window.document; globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const React = await import('react');
  const { createRoot } = await import('react-dom/client');
  const source = readFileSync(new URL('./components/ClockInput.jsx', import.meta.url), 'utf8');
  const { code } = await transformWithOxc(source, 'ClockInput.jsx', { jsx: { runtime: 'automatic' } });
  const compiled = code.replace('"react"', JSON.stringify(import.meta.resolve('react')))
    .replace('"react/jsx-runtime"', JSON.stringify(import.meta.resolve('react/jsx-runtime')))
    .replace('"../clock"', JSON.stringify(new URL('./clock.js', import.meta.url).href));
  const ClockInput = (await import('data:text/javascript,' + encodeURIComponent(compiled))).default;
  const root = createRoot(document.getElementById('root'));
  t.after(async () => {
    await React.act(() => root.unmount()); dom.window.close();
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete globalThis[key]; else globalThis[key] = value;
    }
  });
  let setClock, latest;
  function Form() {
    const [clock, set] = React.useState('14:30'); setClock = set; latest = clock;
    return React.createElement('form', null, React.createElement(ClockInput, { required: true, value: clock, onChange: set }));
  }
  await React.act(() => root.render(React.createElement(Form)));
  const input = document.querySelector('input');
  const type = async text => React.act(() => {
    Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set.call(input, text);
    input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  });
  assert.equal(input.value, '2:30 PM');
  await type('12:');
  assert.equal(input.value, '12:'); assert.equal(latest, ''); assert.equal(input.checkValidity(), false);
  await type('12:05 AM');
  assert.equal(latest, '00:05'); assert.equal(input.checkValidity(), true);
  await type('12:05 PM'); assert.equal(latest, '12:05');
  await type('13:05 PM'); assert.equal(latest, ''); assert.equal(input.checkValidity(), false);
  await React.act(() => setClock('09:00'));
  assert.equal(input.value, '9:00 AM'); assert.equal(input.checkValidity(), true);
});
