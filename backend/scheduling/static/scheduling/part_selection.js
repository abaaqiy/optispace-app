/* Match departmental handbooks automatically; never guess Parts from course digits. */
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

  function departmentKey(value) {
    return String(value || '').normalize('NFKC').toLowerCase()
      .replace(/\([^)]*\)/g, '').replace(/&/g, ' and ')
      .replace(/[^a-z0-9]+/g, ' ').trim()
      .replace(/^(?:(?:the )?(?:department|dept|faculty|school)(?: of)?\s+)+/, '')
      .replace(/^(?:b sc|bsc|b eng|beng|b a|ba|ll b|llb)\s+/, '')
      .replace(/\s+/g, ' ').trim();
  }

  function detect(department, profiles, sources = {}, heading = '') {
    const key = departmentKey(department);
    const names = profile => [...new Set([profile.programme, sources[profile.source_id]?.department,
      ...(profile.department_aliases || [])].map(departmentKey).filter(Boolean))];
    let found = key ? profiles.filter(profile => names(profile).includes(key)) : [];
    if (!found.length && key) {
      // Match a combined departmental heading only when every named component
      // is recognised. Avoid substring matches such as Chemistry in Biochemistry.
      const components = String(department).split(/\s*(?:\/|&|,|\band\b)\s*/i).map(departmentKey).filter(Boolean);
      const groups = components.map(component => profiles.filter(profile => names(profile).includes(component)));
      if (components.length > 1 && groups.every(group => group.length)) found = [...new Set(groups.flat())];
    }
    const context = `${department} ${heading}`.toLowerCase().replace(/[^a-z0-9]/g, '');
    const allowed = profile => !(profile.excluded_programmes || []).some(term => context.includes(term))
      && (!profile.required_programmes?.length || profile.required_programmes.some(term => context.includes(term)));
    return { profiles: found.filter(allowed), restricted: found.filter(profile => !allowed(profile)) };
  }

  function classify(row, profiles, pending) {
    const current = code(row, pending);
    const evidence = profiles.flatMap(profile => profile.entries.filter(item => item.code === current)
      .map(entry => ({ ...entry, source_id: profile.source_id, programme: profile.programme })));
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

  return { code, classify, matches, detect, departmentKey };
})();
