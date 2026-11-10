import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const context = { window: {} };
vm.runInNewContext(readFileSync(new URL('./course_suggestions.js', import.meta.url), 'utf8'), context);
const { lookup } = context.window.OptispaceCourseSuggestions;
const catalogue = JSON.parse(readFileSync(new URL('../../data/course_titles.json', import.meta.url), 'utf8'));
const handbookCourses = JSON.parse(readFileSync(new URL('../../data/handbook_courses.json', import.meta.url), 'utf8'));
const sources = Object.fromEntries(JSON.parse(readFileSync(new URL('../../data/handbook_sources.json', import.meta.url), 'utf8')).map(source => [source.id, source]));
const fullCatalogue = [...catalogue, ...handbookCourses];

test('exact matches work across departments with spacing and case differences', () => {
  assert.equal(lookup('pcg 202', catalogue)[0].title, 'Unorganized Drugs');
  assert.equal(lookup('ACC 101', catalogue)[0].department, 'Accounting');
});
test('unknown and OCR-confused codes never receive guessed titles', () => {
  for (const code of ['PCG2O2', 'PCG202/301', '202', 'ZZZ999', 'PCG-202']) assert.equal(lookup(code, catalogue).length, 0);
});
test('conflicting programmes or titles remain separate candidates', () => {
  const records = [{ code: 'ABC101', title: 'Old curriculum' }, { code: 'ABC101', title: 'New curriculum' }];
  assert.equal(lookup('abc 101', records).length, 2);
});
test('every suggestion has official OAU source and curriculum metadata', () => {
  for (const item of catalogue) {
    assert.match(new URL(item.source_url).hostname, /(^|\.)oauife\.edu\.ng$/);
    assert.ok(item.title && item.department && item.faculty && item.edition && item.verified_on);
  }
  assert.match(lookup('PCG202', catalogue)[0].edition, /NOT verified for PharmD/);
});

test('supplied handbooks support exact titles across faculties and the new Software Engineering file', () => {
  for (const [code, title] of [
    ['CHM102', 'Introductory Chemistry II'], ['ICH204', 'Chemistry of Plastics and Elastomers'],
    ['CVE401', 'Technical Report Writing'], ['ASE310', 'Religious Studies Teaching Methods'],
    ['CSE324', 'Software Testing'], ['MRH201', 'Introduction to Medical Rehabilitation'],
    ['PUL101', 'Legal Methods 1'],
  ]) assert.ok(lookup(code, fullCatalogue, sources).some(item => item.title === title));
  assert.equal(lookup('CHM1O2', fullCatalogue, sources).length, 0);
});

test('historical Law compilation is labelled and the FUTA Physics source is excluded', () => {
  const law = lookup('PUL101', fullCatalogue, sources)[0];
  assert.match(law.edition, /2016\/2017.*student-committee/);
  assert.match(law.notes, /Law Students/);
  assert.ok(!Object.values(sources).some(source => source.filename.includes('604515704')));
});

test('curriculum conflicts are preserved and duplicate evidence is grouped', () => {
  assert.ok(lookup('CSC102', fullCatalogue, sources).length >= 3);
  const clinical = lookup('CLI601', fullCatalogue, sources);
  assert.ok(clinical.some(item => item.title === 'Surgery and Surgical Specialities'));
  assert.ok(clinical.some(item => item.title === 'Community Health and Rural Posting'));
  assert.ok(clinical.every(item => item.department === ''));
  const records = [
    { code: 'ABC101', title: 'Test title', source_id: 'one', page: 1 },
    { code: 'ABC101', title: 'Test title', source_id: 'two', page: 8 },
  ];
  const matching = lookup('ABC101', records, { one: { programme: 'A' }, two: { programme: 'A' } });
  assert.equal(matching.length, 1);
  assert.equal(matching[0].evidence.length, 2);
  assert.equal(lookup('ABC101', records, { one: { programme: 'A' }, two: { programme: 'B' } }).length, 2);
});

test('every handbook entry refers to an identified source and valid physical page', () => {
  for (const item of handbookCourses) {
    const source = sources[item.source_id];
    assert.ok(source && source.edition && source.programme && source.faculty && source.sha256);
    assert.ok(Number.isInteger(item.page) && item.page >= 1 && item.page <= source.pages);
    assert.match(item.code, /^[A-Z]{2,5}\d{3}$/);
    assert.ok(item.title.length >= 4 && item.title.length <= 200);
    if (source.faculty === 'Faculty of Pharmacy') assert.match(source.edition, /NOT verified for PharmD/);
  }
});
