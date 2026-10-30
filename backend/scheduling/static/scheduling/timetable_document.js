/* Source data is always rendered as text, never HTML. No external OCR services. */
(() => {
  const upload = document.getElementById('document-upload');
  upload?.addEventListener('submit', () => {
    upload.querySelector('button').disabled = true;
    document.getElementById('extraction-status').textContent = 'Reading the lecture timetable image… This can take a minute.';
  });
  const form = document.getElementById('document-review');
  if (!form) return;
  const rows = JSON.parse(document.getElementById('document-rows').textContent);
  const refs = JSON.parse(document.getElementById('document-references').textContent);
  const pages = JSON.parse(document.getElementById('document-pages').textContent);
  const days = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const tbody = document.querySelector('#document-table tbody');
  const pageSelect = document.getElementById('source-page');
  const image = document.getElementById('source-image');
  const highlight = document.getElementById('source-highlight');
  const mode = document.getElementById('document-mode');
  const filter = document.getElementById('review-filter');
  const search = document.getElementById('review-search');
  const dayFilter = document.getElementById('review-day');
  const sourceFilter = document.getElementById('review-page');
  const batchChecked = document.getElementById('batch-checked');
  const batchButton = document.getElementById('review-batch');
  const valid = Object.fromEntries(['course', 'room'].map(key => [key, new Set(refs[key + 's'].map(item => item.value))]));
  let offset = 0;
  let visible = [];
  let activeBox = null;
  const pageSize = 25;
  const normalise = value => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  function problems(row) {
    const errors = [];
    for (const key of ['course', 'room']) if (!valid[key].has(row[key])) errors.push(`Choose an existing ${key}`);
    if (!/^\d{2}:\d{2}$/.test(row.start_time || '') || !/^\d{2}:\d{2}$/.test(row.end_time || '') || row.start_time >= row.end_time || [row.start_time, row.end_time].some(value => value && (Number(value.slice(0, 2)) > 23 || Number(value.slice(3)) > 59))) errors.push('Correct the start/end times');
    if (mode.value === 'weekly') {
      if (!days.slice(1).includes(row.day)) errors.push('Choose a weekday');
    } else {
      const date = /^\d{4}-\d{2}-\d{2}$/.test(row.date || '') ? new Date(`${row.date}T12:00:00Z`) : null;
      if (!date || Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== row.date) errors.push('Choose a valid date');
      else if (row.day && row.day !== days[(date.getUTCDay() + 6) % 7 + 1]) errors.push('Weekday does not match the date');
    }
    return errors;
  }
  function warnings(row) {
    return [...(row.note ? [row.note] : []), ...(row.confidence != null && Number(row.confidence) < 90 ? ['Uncertain reading; compare with the image'] : []), ...(row.day_group && !row.day_checked ? ['Check the shared weekday heading'] : []), ...(row.time_group && !row.time_checked ? ['Check the shared time heading'] : [])];
  }
  function ready(row) { return !row.skip && !row.reviewed && !problems(row).length && !warnings(row).length; }
  function resetBatch() { batchChecked.checked = false; batchButton.disabled = true; }
  function batchStatus() {
    const eligible = visible.filter(({ row }) => ready(row)).length;
    document.getElementById('batch-status').textContent = `${eligible} visible rows eligible; warnings and missing fields require individual attention.`;
    batchButton.disabled = !batchChecked.checked || !eligible;
  }
  function element(tag, text, parent) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (parent) parent.append(el);
    return el;
  }
  function invalidate() { document.getElementById('document-final-preview')?.setAttribute('hidden', ''); resetBatch(); }
  function status() {
    const kept = rows.filter(r => !r.skip);
    document.getElementById('review-status').textContent = `${kept.filter(r => r.reviewed).length} of ${kept.length} retained rows reviewed; ${kept.filter(r => problems(r).length).length} with missing/invalid fields; ${kept.filter(ready).length} ready for batch review; ${rows.length - kept.length} skipped.`;
    batchStatus();
    readyGroups();
  }
  function headings() {
    const root = document.getElementById('heading-mappings');
    root.replaceChildren();
    for (const kind of ['day', 'time']) {
      const groups = new Map();
      rows.forEach(row => {
        if (row.skip || !row[kind + '_group']) return;
        const key = row[kind + '_group'];
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(row);
      });
      for (const affected of groups.values()) {
        const first = affected[0];
        const section = element('div', undefined, root); section.className = 'heading-mapping';
        const label = kind === 'day' ? 'Weekday' : 'Time';
        element('strong', `${label}: “${first[kind + '_text'] || 'not readable'}” · ${affected.length} entries`, section);
        const show = element('button', 'Show heading', section); show.type = 'button';
        show.addEventListener('click', () => showPage(first.page, first[kind + '_box']));
        const inputs = [];
        if (kind === 'day') {
          const select = element('select', undefined, section); select.setAttribute('aria-label', `Weekday heading ${first.day_group}`);
          days.forEach(day => { const option = element('option', day || 'Choose weekday', select); option.value = day; });
          select.value = first.day || ''; inputs.push(select);
        } else {
          for (const [key, label] of [['start_time', 'Start'], ['end_time', 'End']]) {
            const input = element('input', undefined, section); input.type = 'time'; input.value = first[key] || ''; input.setAttribute('aria-label', `${label} heading ${first.time_group}`); inputs.push(input);
          }
        }
        if (first[kind + '_note']) element('small', first[kind + '_note'], section);
        const sameValues = affected.every(row => kind === 'day' ? row.day === first.day : row.start_time === first.start_time && row.end_time === first.end_time);
        if (!sameValues) element('small', 'Some entries have individual corrections. Confirming here replaces those values for this heading.', section);
        const apply = element('button', affected.every(row => row[kind + '_checked']) ? 'Heading checked' : 'Confirm heading for these entries', section); apply.type = 'button';
        inputs.forEach(input => input.addEventListener('input', () => { apply.textContent = 'Confirm corrected heading'; }));
        apply.addEventListener('click', () => {
          if (kind === 'day' && !days.slice(1).includes(inputs[0].value) || kind === 'time' && (!inputs[0].value || !inputs[1].value || inputs[0].value >= inputs[1].value)) { window.alert('Choose a valid heading before confirming it.'); return; }
          affected.forEach(row => {
            if (row.skip) return;
            const changed = kind === 'day' ? row.day !== inputs[0].value : row.start_time !== inputs[0].value || row.end_time !== inputs[1].value;
            if (kind === 'day') row.day = inputs[0].value;
            else { row.start_time = inputs[0].value; row.end_time = inputs[1].value; }
            row[kind + '_checked'] = true;
            if (changed) row.reviewed = false;
          });
          invalidate(); headings(); render();
        });
      }
    }
    if (!root.children.length) element('p', 'No shared headings need confirmation for these entries.', root);
  }
  function readyGroups() {
    const root = document.getElementById('ready-groups');
    const open = new Set([...root.querySelectorAll('details[open]')].map(el => el.dataset.day));
    root.replaceChildren();
    for (const day of days.slice(1)) {
      const group = rows.map((row, index) => ({ row, index })).filter(({ row }) => row.day === day && ready(row));
      if (!group.length) continue;
      const details = element('details', undefined, root); details.dataset.day = day; details.open = open.has(day);
      element('summary', `${day}: ${group.length} clear entries to check`, details);
      const table = element('table', undefined, details); table.className = 'compact-review';
      const head = element('tr', undefined, element('thead', undefined, table)); ['Time', 'Course', 'Room', 'Source'].forEach(title => element('th', title, head));
      const body = element('tbody', undefined, table);
      group.sort((a, b) => a.row.start_time.localeCompare(b.row.start_time)).forEach(({ row, index }) => {
        const tr = element('tr', undefined, body);
        element('td', `${row.start_time}–${row.end_time}`, tr);
        element('td', row.course, tr);
        element('td', refs.rooms.find(item => item.value === row.room)?.label || row.room, tr);
        const td = element('td', undefined, tr);
        const show = element('button', `Row ${index + 1}`, td); show.type = 'button'; show.addEventListener('click', () => showPage(row.page, row.box));
      });
      const label = element('label', undefined, details); const checked = element('input', undefined, label); checked.type = 'checkbox'; label.append(document.createTextNode(` I compared this ${day} group with the image.`));
      const approve = element('button', `Mark ${day} group reviewed`, details); approve.type = 'button'; approve.disabled = true;
      checked.addEventListener('change', () => { approve.disabled = !checked.checked; });
      approve.addEventListener('click', () => { if (!checked.checked) return; group.forEach(({ row }) => { if (ready(row)) row.reviewed = true; }); invalidate(); render(); });
    }
    if (!root.children.length) element('p', 'No clear unreviewed groups yet. Resolve names and shared headings, or correct the flagged entries below.', root);
  }
  function mappings() {
    const root = document.getElementById('reference-mappings');
    root.replaceChildren();
    let groupCount = 0;
    for (const key of ['course', 'room']) {
      const groups = new Map();
      rows.forEach(row => {
        if (row.skip || valid[key].has(row[key])) return;
        const text = row[key + '_text'] || '';
        const group = normalise(text);
        if (!group) return;
        if (!groups.has(group)) groups.set(group, { text, rows: [] });
        groups.get(group).rows.push(row);
      });
      for (const { text, rows: affected } of groups.values()) {
        groupCount++;
        const section = element('div', undefined, root); section.className = 'reference-mapping';
        element('strong', `${key === 'course' ? 'Course' : 'Room'} “${text}” — ${affected.length} row(s)`, section);
        const query = element('input', undefined, section); query.type = 'search'; query.placeholder = `Search saved ${key}s`; query.setAttribute('aria-label', `Search choices for ${text}`);
        const choice = element('select', undefined, section); choice.setAttribute('aria-label', `Map ${key} ${text}`);
        [{ value: '', label: `Select correct ${key}…` }, ...refs[key + 's']].forEach(item => { const opt = element('option', item.label, choice); opt.value = item.value; });
        query.addEventListener('input', () => { for (const opt of choice.options) opt.hidden = !!opt.value && !opt.text.toLowerCase().includes(query.value.toLowerCase()); });
        const apply = element('button', 'Use for all matching unresolved rows', section); apply.type = 'button'; apply.disabled = true;
        choice.addEventListener('change', () => { apply.disabled = !choice.value; });
        apply.addEventListener('click', () => {
          affected.filter(row => !row.skip && !valid[key].has(row[key])).forEach(row => { row[key] = choice.value; row.reviewed = false; });
          invalidate(); offset = 0; mappings(); render();
        });
      }
    }
    document.getElementById('mapping-status').textContent = groupCount ? `${groupCount} distinct detected names need matching. These choices apply only to this upload.` : 'All detected names with readable text are matched. Check individual rows for fields that were not detected.';
  }
  function showPage(number, box) {
    const page = pages[number - 1];
    if (!page) return;
    pageSelect.value = String(number);
    image.src = page.url;
    activeBox = box || null;
    image.alt = `Uploaded timetable, page ${number}`;
    document.getElementById('source-open').href = page.url;
    highlight.hidden = !box;
    if (box) {
      highlight.style.left = `${box[0] / page.width * 100}%`;
      highlight.style.top = `${box[1] / page.height * 100}%`;
      highlight.style.width = `${(box[2] - box[0]) / page.width * 100}%`;
      highlight.style.height = `${(box[3] - box[1]) / page.height * 100}%`;
    }
    drawCrop();
    if (box) {
      const source = document.querySelector('.document-source');
      const bounds = source.getBoundingClientRect();
      if (bounds.top < 0 || bounds.bottom > window.innerHeight) source.scrollIntoView({ block: 'start' });
    }
  }
  function drawCrop() {
    const canvas = document.getElementById('source-crop');
    canvas.hidden = !activeBox || !image.complete;
    if (canvas.hidden || !image.naturalWidth) return;
    const [left, top, right, bottom] = activeBox;
    const width = Math.max(1, right - left), height = Math.max(1, bottom - top);
    const scale = Math.min(3, 900 / width, 300 / height);
    canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale);
    canvas.getContext('2d').drawImage(image, left, top, width, height, 0, 0, canvas.width, canvas.height);
  }
  image.addEventListener('load', drawCrop);
  document.getElementById('source-zoom').addEventListener('input', event => { document.querySelector('.source-canvas').style.width = `${event.target.value}%`; });
  pages.forEach((_, i) => { const opt = element('option', String(i + 1), pageSelect); opt.value = String(i + 1); });
  pages.forEach((_, i) => { const opt = element('option', String(i + 1), sourceFilter); opt.value = String(i + 1); });
  days.slice(1).forEach(day => { const opt = element('option', day, dayFilter); opt.value = day; });
  pageSelect.addEventListener('change', () => showPage(Number(pageSelect.value)));
  showPage(1);
  function render() {
    resetBatch();
    tbody.replaceChildren();
    const query = search.value.toLowerCase();
    const filtered = rows.map((row, index) => ({ row, index })).filter(({ row }) => {
      if (dayFilter.value && row.day !== dayFilter.value || sourceFilter.value && String(row.page) !== sourceFilter.value) return false;
      if (query && ![row.course, row.room, row.course_text, row.room_text, row.source, row.day, row.date].some(value => String(value || '').toLowerCase().includes(query))) return false;
      if (filter.value === 'skipped') return !!row.skip;
      if (filter.value === 'all') return true;
      if (row.skip) return false;
      if (filter.value === 'reviewed') return !!row.reviewed;
      if (filter.value === 'issues') return !row.reviewed && (problems(row).length || warnings(row).length);
      if (filter.value === 'ready') return ready(row);
      return !row.reviewed || problems(row).length;
    });
    offset = Math.min(offset, Math.max(0, Math.floor((filtered.length - 1) / pageSize) * pageSize));
    visible = filtered.slice(offset, offset + pageSize);
    document.getElementById('review-page-status').textContent = filtered.length ? `${offset + 1}–${Math.min(offset + pageSize, filtered.length)} of ${filtered.length} matching entries` : 'No entries match this view.';
    document.getElementById('review-previous').disabled = offset === 0;
    document.getElementById('review-next').disabled = offset + pageSize >= filtered.length;
    visible.forEach(({row, index}) => {
      const tr = element('tr', undefined, tbody);
      tr.classList.toggle('skipped', !!row.skip);
      const source = element('td', undefined, tr);
      element('strong', `Row ${index + 1}`, source);
      if (row.page) element('small', `Page ${row.page}`, source);
      const raw = element('details', undefined, source);
      element('summary', 'Original text', raw);
      element('small', row.source || 'Manually added entry', raw);
      const validation = element('small', undefined, source); validation.className = 'review-note row-validation';
      const alerts = element('small', undefined, source); alerts.className = 'review-note';
      if (row.confidence != null) element('small', `Recognition score: ${Math.round(Number(row.confidence))}/100`, source);
      const actions = element('div', undefined, source); actions.className = 'row-actions';
      if (row.page) {
        const show = element('button', 'Show source', actions); show.type = 'button';
        show.addEventListener('click', () => showPage(row.page, row.box));
      }
      const duplicate = element('button', 'Duplicate', actions); duplicate.type = 'button';
      duplicate.addEventListener('click', () => {
        if (rows.length >= 300) { window.alert('Review at most 300 rows per document.'); return; }
        rows.splice(index + 1, 0, { ...row, room: '', reviewed: false, skip: false }); invalidate(); mappings(); headings(); render();
      });
      let checked;
      function updateRow() {
        const errors = problems(row);
        const notes = warnings(row);
        alerts.textContent = notes.join('; '); alerts.hidden = !notes.length;
        validation.textContent = errors.join('; ');
        validation.hidden = !errors.length;
        tr.classList.toggle('has-issues', !!errors.length);
        tr.classList.toggle('skipped', !!row.skip);
        if (checked) {
          checked.checked = !!row.reviewed;
          checked.disabled = !!errors.length;
          if (errors.length) checked.title = 'Choose valid course, room, day/date and times first.';
          else checked.removeAttribute('title');
        }
      }
      function edited() { row.reviewed = false; updateRow(); invalidate(); status(); }
      function select(parent, key, choices, label) {
        const input = element('select', undefined, parent); input.setAttribute('aria-label', `${label}, row ${index + 1}`);
        choices.forEach(item => { const opt = element('option', item.label, input); opt.value = item.value; });
        input.value = row[key] || '';
        input.addEventListener('change', () => { row[key] = input.value; if (key === 'day') row.day_checked = true; edited(); if (key === 'course' || key === 'room') mappings(); else if (key === 'day') headings(); });
        return input;
      }
      function reference(key, choices, original) {
        const td = element('td', undefined, tr);
        element('small', `Read: ${original || '(not detected)'}`, td);
        const search = element('input', undefined, td); search.type = 'search'; search.placeholder = `Search ${key}s`;
        search.setAttribute('aria-label', `Search ${key}s, row ${index + 1}`);
        const list = [{ value: '', label: `Select ${key}…` }, ...choices];
        const input = select(td, key, list, key);
        search.addEventListener('input', () => {
          const query = search.value.toLowerCase();
          for (const opt of input.options) opt.hidden = !!opt.value && opt.value !== input.value && !opt.text.toLowerCase().includes(query);
        });
      }
      reference('course', refs.courses, row.course_text);
      reference('room', refs.rooms, row.room_text);
      const when = element('td', undefined, tr);
      select(when, 'day', days.map(day => ({ value: day, label: day || 'Choose weekday…' })), 'Weekday');
      const date = element('input', undefined, when); date.type = 'date'; date.value = row.date || '';
      date.setAttribute('aria-label', `Date, row ${index + 1}`); date.hidden = mode.value === 'weekly';
      date.addEventListener('input', () => { row.date = date.value; edited(); });
      const time = element('td', undefined, tr);
      for (const [key, label] of [['start_time', 'Start'], ['end_time', 'End']]) {
        const wrap = element('label', `${label} `, time); const input = element('input', undefined, wrap);
        input.type = 'time'; input.value = row[key] || ''; input.setAttribute('aria-label', `${label} time, row ${index + 1}`);
        input.addEventListener('input', () => { row[key] = input.value; edited(); });
        input.addEventListener('change', () => { row.time_checked = !problems(row).includes('Correct the start/end times'); updateRow(); headings(); status(); });
      }
      const check = element('td', undefined, tr);
      for (const [key, label] of [['reviewed', 'Reviewed'], ['skip', 'Skip row']]) {
        const wrap = element('label', undefined, check); const input = element('input', undefined, wrap); input.type = 'checkbox'; input.checked = !!row[key];
        wrap.append(document.createTextNode(` ${label}`));
        if (key === 'reviewed') checked = input;
        input.addEventListener('change', () => {
          row[key] = input.checked;
          if (key === 'reviewed' && input.checked) { row.day_checked = true; row.time_checked = true; }
          updateRow(); invalidate(); status();
          if (key === 'skip') mappings();
          headings();
        });
      }
      updateRow();
    });
    status();
  }
  function updateMode() {
    const weekly = mode.value === 'weekly';
    document.getElementById('teaching-dates').hidden = !weekly;
    for (const id of ['first-date', 'last-date']) document.getElementById(id).required = weekly;
  }
  mode.addEventListener('change', () => { rows.forEach(row => { row.reviewed = false; }); updateMode(); render(); invalidate(); });
  form.querySelector('.document-options').addEventListener('input', invalidate);
  document.getElementById('add-review-row').addEventListener('click', () => {
    if (rows.length >= 300) { window.alert('Review at most 300 rows per document.'); return; }
    rows.push({ course: '', room: '', day: '', date: '', start_time: '', end_time: '', reviewed: false, skip: false }); invalidate(); render();
    filter.value = 'all'; search.value = ''; dayFilter.value = ''; sourceFilter.value = ''; offset = Math.floor((rows.length - 1) / pageSize) * pageSize; render();
    tbody.lastElementChild?.scrollIntoView({ block: 'nearest' });
  });
  for (const input of [filter, search, dayFilter, sourceFilter]) input.addEventListener('input', () => { offset = 0; render(); });
  document.getElementById('review-previous').addEventListener('click', () => { offset -= pageSize; render(); });
  document.getElementById('review-next').addEventListener('click', () => { offset += pageSize; render(); });
  batchChecked.addEventListener('change', batchStatus);
  batchButton.addEventListener('click', () => {
    if (!batchChecked.checked) return;
    visible.forEach(({ row }) => { if (ready(row)) row.reviewed = true; });
    invalidate(); render();
  });
  form.addEventListener('submit', event => {
    // Keep exactly one action value; a hidden default and clicked button otherwise duplicate it.
    form.querySelector('input[name="action"]').value = event.submitter?.value || 'review';
    if (event.submitter?.name === 'action') event.submitter.removeAttribute('name');
    document.getElementById('review-rows').value = JSON.stringify(rows);
  });
  updateMode(); mappings(); headings(); render();
})();
