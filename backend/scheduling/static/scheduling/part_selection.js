/* Part membership uses exact programme evidence, never course-number guesses. */
window.OptispacePartSelection = (() => {
  const parts = { I: 1, II: 2, III: 3, IV: 4, '1V': 4, V: 5, VI: 6,
    ONE: 1, TWO: 2, THREE: 3, FOUR: 4, FIVE: 5, SIX: 6 };

  function code(row, pending) {
    const proposal = pending.courses?.find(item => item.key === row.course);
    return String(proposal ? proposal.code : row.course || row.course_text || '')
      .replace(/\s+/g, '').toUpperCase();
  }

  function explicitParts(row) {
    if (row.class_group_kind !== 'part') return [];
    const tokens = String(row.class_group || '').toUpperCase()
      .replace(/\b(?:PARTS?|LEVELS?)\b/g, '').trim().split(/\s*(?:\/|&|,|\+|\bAND\b)\s*/);
    const result = tokens.map(token => parts[token] || (/^[1-6]$/.test(token) ? Number(token) : 0));
    return result.includes(0) ? [] : [...new Set(result)].sort();
  }

  function classify(row, options, pending, profiles) {
    const current = code(row, pending);
    const profile = options.level_profile_confirmed === 'yes'
      ? profiles.find(item => item.id === options.level_profile) : null;
    const evidence = profile?.entries.filter(item => item.code === current) || [];
    const handbookParts = [...new Set(evidence.map(item => item.level))].sort();
    if (Array.isArray(row.level_override) && row.level_override_code === current) {
      return { parts: [...row.level_override].sort(), kind: 'manual', evidence };
    }
    const headingParts = explicitParts(row);
    if (headingParts.length) return { parts: headingParts, kind: 'heading', evidence,
      conflict: !!handbookParts.length && JSON.stringify(handbookParts) !== JSON.stringify(headingParts) };
    // A curriculum listing in several Parts does not prove a shared teaching session.
    return { parts: handbookParts.length === 1 ? handbookParts : [], evidence,
      kind: handbookParts.length === 1 ? 'handbook' : handbookParts.length ? 'uncertain' : 'unknown' };
  }

  function matches(info, view) {
    return !view || view === 'all' || (view === 'unassigned' ? !info.parts.length : info.parts.includes(Number(view)));
  }

  return { code, classify, matches };
})();
