(() => {
  const data = document.getElementById('manual-course-catalogue');
  const code = document.getElementById('id_code');
  const title = document.getElementById('id_title');
  const department = document.getElementById('id_department');
  const pending = document.getElementById('id_title_pending');
  if (!data || !code || !title || !department || !pending) return;
  const { course_catalogue: catalogue, course_sources: sources } = JSON.parse(data.textContent);
  const root = document.getElementById('manual-course-matches');
  const { codeKey, lookup, renderCandidates } = window.OptispaceCourseSuggestions;
  let selectedCode = codeKey(code.value);
  function message(text) {
    const p = document.createElement('p'); p.textContent = text; root.append(p);
  }
  function show() {
    root.replaceChildren();
    const key = codeKey(code.value);
    if (!key) { message('Enter the complete course code, for example CHM102.'); return; }
    if (selectedCode && key !== selectedCode && title.value) message('The code changed. Check the existing title before saving this course.');
    const matches = lookup(key, catalogue, sources);
    if (!matches.length) {
      message('No verified title for this exact code in the current catalogue. Enter a known title, or leave it blank and tick Title awaiting confirmation after verifying the code. A missing suggestion does not make the course invalid.');
      return;
    }
    renderCandidates(root, matches, title.value, item => {
      title.value = item.title;
      if (item.department) department.value = item.department;
      pending.checked = false;
      selectedCode = key;
      show();
    });
  }
  code.addEventListener('input', show);
  title.addEventListener('input', show);
  show();
})();
