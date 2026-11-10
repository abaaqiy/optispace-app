/* Exact code lookup across all sourced departments; never infer a title from OCR. */
(() => {
  const codeKey = value => String(value || '').toUpperCase().replace(/\s/g, '');
  function lookup(code, catalogue, sources = {}) {
    const key = codeKey(code);
    if (!/^[A-Z]{2,5}\d{3}$/.test(key)) return [];
    const matches = catalogue.filter(entry => codeKey(entry.code) === key)
      .map(entry => ({ ...sources[entry.source_id], ...entry }));
    const groups = new Map();
    matches.forEach(entry => {
      // Group repeated evidence only when title, department AND programme agree.
      const signature = [entry.title, entry.department || '', entry.programme || '']
        .map(value => value.toLocaleLowerCase().replace(/\s+/g, ' ').trim()).join('|');
      if (groups.has(signature)) groups.get(signature).evidence.push(entry);
      else groups.set(signature, { ...entry, evidence: [entry] });
    });
    return Array.from(groups.values());
  }
  const api = { codeKey, lookup };
  if (typeof window !== 'undefined') window.OptispaceCourseSuggestions = api;
})();
