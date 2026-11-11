/* Group probable OCR readings for review. Never change a row or infer its location. */
(() => {
  const token = value => String(value || '').toUpperCase().replace(/[!|]/g, 'I').replace(/[^A-Z0-9]/g, '');
  const digit = value => /^[0-9]$/.test(value);
  const confusions = ['IL1', 'OQD0', 'CGO0', 'S5', 'B83', 'Z2', 'G6', 'RP', 'MN', 'UVY'];
  const confused = (a, b) => confusions.some(group => group.includes(a) && group.includes(b));
  function substitution(a, b) {
    if (a === b) return 0;
    // Two printed numbers are different identities, even when their shapes look similar.
    if (digit(a) && digit(b)) return Infinity;
    if (confused(a, b)) return 0.25;
    return digit(a) || digit(b) ? Infinity : 1;
  }
  function distance(a, b) {
    if (Math.abs(a.length - b.length) > 2) return Infinity;
    const grid = Array.from({ length: a.length + 1 }, () => Array(b.length + 1).fill(Infinity));
    grid[0][0] = 0;
    for (let i = 0; i <= a.length; i++) for (let j = 0; j <= b.length; j++) {
      if (i) grid[i][j] = Math.min(grid[i][j], grid[i - 1][j] + (digit(a[i - 1]) ? Infinity : 0.75));
      if (j) grid[i][j] = Math.min(grid[i][j], grid[i][j - 1] + (digit(b[j - 1]) ? Infinity : 0.75));
      if (i && j) grid[i][j] = Math.min(grid[i][j], grid[i - 1][j - 1] + substitution(a[i - 1], b[j - 1]));
      // Adjacent letters may be reversed: 1000IST / 1000SLT. Never reverse digits.
      if (i > 1 && j > 1 && ![a[i - 2], a[i - 1], b[j - 2], b[j - 1]].some(digit)) {
        const left = substitution(a[i - 2], b[j - 1]), right = substitution(a[i - 1], b[j - 2]);
        if (left <= 0.25 && right <= 0.25) grid[i][j] = Math.min(grid[i][j], grid[i - 2][j - 2] + 0.6 + left + right);
      }
    }
    return grid[a.length][b.length];
  }
  function courseParts(value) {
    if (value.length < 5 || value.length > 8) return null;
    const prefix = value.slice(0, -3), number = value.slice(-3);
    return /^[A-Z0-9]{2,5}$/.test(prefix) && /^[0-9OQDILSZBG]{3}$/.test(number) ? { prefix, number } : null;
  }
  const qualifier = value => String(value || '').toUpperCase().match(/[\s(-]+([A-Z])\)?\s*$/)?.[1] || '';
  function candidates(kind, references, catalogue, nodes) {
    const known = new Map();
    function add(id, label, names, value = '') {
      const item = known.get(id) || { id, label, names: new Map(), value, source: 'catalogue' };
      if (value) { item.value = value; item.label = label; item.source = 'saved'; }
      for (const name of names) if (token(name)) item.names.set(token(name), String(name));
      known.set(id, item);
    }
    if (kind === 'course') {
      for (const entry of catalogue) if (/^[A-Z]{2,5}\d{3}$/.test(token(entry.code))) {
        const code = token(entry.code); add(code, code, [code]);
      }
    } else {
      for (const entry of catalogue) add(token(entry.name), entry.name, [entry.name, ...(entry.aliases || [])]);
    }
    for (const ref of references) {
      const name = kind === 'course' ? ref.value : ref.name || ref.label.split(' — ')[0];
      const id = ref.identity ? token(ref.identity) : token(name);
      add(id, ref.label, [name, ref.value, ...(ref.keys || [])], ref.value);
    }
    const observed = nodes.filter(node => kind === 'course' ? /^[A-Z]{2,5}\d{3}$/.test(node.key)
      : node.key.length >= 4 && /[A-Z]/.test(node.key) && (node.rows.length > 1 || /^[A-Z]{1,5}\d{3}$/.test(node.key)))
      .map(node => ({ id: `reading:${node.key}`, label: node.text, names: new Map([[node.key, node.text]]), source: 'reading', value: '', count: node.rows.length }));
    return { known: [...known.values()], observed };
  }
  function build({ kind, rows, references, catalogue, isEditing = () => false }) {
    const valid = new Set(references.map(item => item.value));
    const nodes = new Map(), missing = [];
    const separatedKeys = new Set(rows.filter(row => !row.skip && row[kind + '_group_separate']).map(row => token(row[kind + '_text'])));
    for (const row of rows) {
      if (row.skip || valid.has(row[kind])) continue;
      const text = row[kind + '_text'] || '', key = token(text);
      if (!key) { missing.push(row); continue; }
      const separated = separatedKeys.has(key);
      const nodeKey = separated ? `separate:${key}` : key;
      if (!nodes.has(nodeKey)) nodes.set(nodeKey, { key, id: nodeKey, text, rows: [], readings: new Map(), checked: false, separated, editing: false });
      const node = nodes.get(nodeKey); node.rows.push(row);
      if (!node.readings.has(text)) node.readings.set(text, { text, rows: [] });
      node.readings.get(text).rows.push(row);
      node.checked ||= !!row[kind + '_reading_checked'];
      node.editing ||= isEditing(text);
    }
    const { known, observed } = candidates(kind, references, catalogue, [...nodes.values()]);
    const prefixes = new Set(known.flatMap(item => [...item.names.keys()].filter(name => /^[A-Z]{2,5}\d{3}$/.test(name))
      .map(name => courseParts(name)?.prefix)).filter(Boolean));
    const prefixCounts = new Map();
    if (kind === 'course') for (const row of rows) {
      if (row.skip) continue;
      const part = courseParts(token(row.course_text));
      if (part) prefixCounts.set(part.prefix, (prefixCounts.get(part.prefix) || 0) + 1);
    }
    // A room family ending in A/B/C must retain that identifying letter, even without spaces.
    const roomFamilies = new Set();
    if (kind === 'room') {
      const endings = new Map();
      for (const item of known) for (const key of item.names.keys()) if (key.length >= 4 && /[A-Z]$/.test(key)) {
        const stem = key.slice(0, -1);
        if (!endings.has(stem)) endings.set(stem, new Set());
        endings.get(stem).add(key.slice(-1));
      }
      for (const [stem, letters] of endings) if (letters.size > 1) roomFamilies.add(stem);
    }
    function score(node, item) {
      let best = null;
      for (const [key, text] of item.names) {
        if (node.key.length < 4 || key.length < 4) continue;
        let cost;
        if (kind === 'course') {
          const a = courseParts(node.key), b = courseParts(key);
          if (!a || !b || !/^[A-Z]{2,5}\d{3}$/.test(key)) continue;
          if (a.prefix !== b.prefix && prefixes.has(a.prefix)) continue;
          const numberCost = [...a.number].reduce((sum, char, index) => sum + substitution(char, b.number[index]), 0);
          if (!Number.isFinite(numberCost)) continue;
          const prefixCost = distance(a.prefix, b.prefix);
          // A whole changed prefix needs corroborating occurrences in this image.
          if (prefixCost >= 1 && (prefixCounts.get(b.prefix) || 0) < 2) continue;
          cost = numberCost + prefixCost;
        } else {
          const a = qualifier(node.text), b = qualifier(text);
          if (a && b && a !== b) continue;
          if (roomFamilies.has(key.slice(0, -1)) && /[A-Z]$/.test(node.key) && node.key.slice(-1) !== key.slice(-1)) continue;
          if (/[A-Z]$/.test(node.key) && /[A-Z]$/.test(key) && substitution(node.key.slice(-1), key.slice(-1)) >= 1) continue;
          cost = distance(node.key, key);
        }
        const limit = item.source === 'reading' ? 0.85 : kind === 'course' ? 1 : 1.15;
        if (cost > limit || cost / Math.max(node.key.length, key.length) > 0.22) continue;
        if (!best || cost < best.cost) best = { ...item, text, cost };
      }
      return best;
    }
    function choose(node, list) {
      const matches = list.map(item => score(node, item)).filter(Boolean).sort((a, b) => a.cost - b.cost);
      // Similar alternatives remain separate. Never use a fuzzy chain to combine identities.
      const ambiguous = matches.length > 1 && matches[1].cost - matches[0].cost < 0.35;
      return { match: matches.length && !ambiguous ? matches[0] : null, ambiguous };
    }
    const groups = new Map();
    for (const node of nodes.values()) {
      let target = null;
      const separated = node.separated;
      if (!separated && !node.checked && !node.editing) {
        const exact = known.filter(item => item.names.has(node.key));
        if (exact.length === 1) target = { ...exact[0], text: exact[0].names.get(node.key), cost: 0 };
        else if (!exact.length) {
          const knownMatch = choose(node, known);
          target = knownMatch.match;
          if (!target && !knownMatch.ambiguous) {
            // Unknown but well-formed course codes are distinct until an authoritative match exists.
            const own = observed.find(item => item.names.has(node.key));
            const stronger = observed.filter(item => !item.names.has(node.key) && ![...nodes.values()].some(other =>
              other.key === [...item.names.keys()][0] && (other.separated || other.checked || other.editing))
              && (kind === 'course' ? !/^[A-Z]{2,5}\d{3}$/.test(node.key) : item.count > node.rows.length));
            target = choose(node, stronger).match || (own ? { ...own, text: node.text, cost: 0 } : null);
          }
        }
      }
      const id = separated || node.checked || node.editing ? `pinned:${node.id}` : target?.id || `reading:${node.key}`;
      if (!groups.has(id)) groups.set(id, { text: node.text, rows: [], readings: [], target, suggested: false, separated, editing: node.editing });
      const group = groups.get(id);
      group.rows.push(...node.rows); group.readings.push(...node.readings.values());
      group.suggested ||= !!target?.cost;
      if (target && (!group.target || target.cost < group.target.cost)) group.target = target;
    }
    return { groups: [...groups.values()], readingCount: nodes.size, missing };
  }
  window.OptispaceOcrGroups = { build, token };
})();
