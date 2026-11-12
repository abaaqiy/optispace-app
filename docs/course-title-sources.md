# OAU course-title suggestions

This feature supports **all OAU faculties**, but source coverage is incomplete.
The catalogue now covers **2,499 distinct codes**, with 2,925 source records:
2,836 records from 46 supplied handbook/course documents, plus the earlier 89
web-source records. Coverage spans 14 faculties, including the newly supplied
Software Engineering and historical Law files. This is neither a complete course inventory nor a
measured 90% accuracy claim. See [the supplied-file inventory](handbook-inventory.md)
for editions, counts, omissions and known conflicts.

`backend/scheduling/data/course_titles.json` contains short factual title records,
department/faculty, edition notes, verification date, original source URLs and PDF
page numbers (physical PDF pages). It contains no full handbook copies.

The local lookup accepts exact course codes, ignoring whitespace and case only.
It does not repair OCR substitutions or infer course titles. Multiple matches
remain separate candidates. Admins check programme/session applicability before
using a suggestion; they can edit it and retain their own title. Already saved
courses can be reused. Source availability is not required during an import;
there are no external AI calls, API keys, fees or uploaded timetable transmissions.

The same suggestions are available in **Courses → Add course**, **Edit course**,
and the related-course popup in the timetable form. Enter a complete code; the
suggestions panel shows exact matches, handbook pages, programmes and editions.
Confirm applicability, then choose **Use this title** (or **Replace title with
this suggestion**). This fills the title and any known department, and clears
the pending-title checkbox. It does not save the form or overwrite a title while
typing. A missing title can still be explicitly marked awaiting confirmation.

## Sources inspected on 9 November 2026

| Source | Included coverage | Limitations |
| --- | --- | --- |
| [Accounting course content](https://accounting.oauife.edu.ng/course-content/) | 38 ACC codes from CCMAS/OAU tables | Effective session unstated. Cross-department electives excluded; do not assign their departments from this page. ACC codes repeat consistently in the semester tables. |
| [English handbook, May 2025 revision](https://english.oauife.edu.ng/wp-content/uploads/2025/07/DEPARTMENTAL-HANDABOOK-ENGLISH-NEWLY-ADJUSTED-MAY-2025.docx) | 21 EGL codes under Description of Courses | Omit EGL101/102/203/204/205/301/406 where alternate lists use different titles. Trailing title colons removed; titles otherwise preserved. Effective session must be checked. |
| [Economics handbook](https://ecn.oauife.edu.ng/wp-content/uploads/2019/10/Department-of-Economics-Handbook.pdf) | 17 ECN codes; physical PDF pages 22, 23 and 25 | Historical: cover says 2017, staff lists 2018/2019. Several other codes have internally conflicting titles; do not silently correct them. Current curriculum unconfirmed. |
| [Pharmacognosy handbook/course descriptions](https://pharmacognosy.oauife.edu.ng/wp-content/uploads/2021/01/Faculty-Hand-book-Courses-07-12-2020.pdf) | 13 explicit PCG codes, physical PDF pages 1–5 | Historical file dated 07-12-2020; **not verified for PharmD**. Page 1 writes only “201” for its first code: excluded because the prefix is missing. Includes explicit postgraduate PCG601–607, not an inference that every class is undergraduate. |

The PDFs were checked in text and rendered pages. English titles were inspected
in the DOCX XML paragraphs, and Accounting titles in the published HTML tables.
Source SHA-256 checksums for reproducibility:

- Pharmacognosy PDF: `8b364f2c9c87344c2b87e7300f53fe85be29dd2e192889c4e5ff8a4891bca5a2`
- Economics PDF: `29d8a773a8fcafd4f7e4ad725bdf2b91af260060ddd9c2899f816adfab8635ba`
- Accounting HTML snapshot: `01e98f6c0deff62d61828b7b441bcbe92ecbc7bb2e6f53122a26b2d27ab3d413`
- English DOCX: `d2aa8396e66e9f725528295e87b009529eca9c40206bd5293829d3dcaf3ac716`

Earlier official links checked: Chemistry's previously linked 2023 handbook was
unavailable; Pharmaceutical Chemistry's 2019 faculty handbook returns 404;
Anatomy's download points to `#`; Computing's old host did not resolve; Electrical
Engineering's handbook endpoint returned no usable text. These failures do not
establish that handbooks or courses do not exist. The current PharmD handbook
has not been verified. The user has since supplied local Chemistry 2023 and
Pharmacy 2019–2021 copies. The latter is explicitly B.Pharm, not PharmD.

## Local handbook references

`handbook_sources.json` stores file basenames, exact ZIP member names, SHA-256,
edition/programme notes and source IDs. `handbook_courses.json` stores the short
course titles and physical PDF page numbers. It contains no full handbook text.
Shared metadata is sent once per document. Repeated identical titles for the same
department/programme are grouped into one suggestion with multiple references.
Conflicting titles or programmes remain separate; admins explicitly select one.

The development launcher sets `OPTISPACE_HANDBOOK_DIR` to
`$HOME/Downloads/handbooks` unless overridden. Handbook links require a staff
session with timetable-import permission, or course-add/change permission through
the manual Course form's separate reference endpoint. They work only with `DEBUG=True` and
a configured directory. The endpoint checks the manifest, directory containment,
file size and exact PDF checksum; it reads allowlisted ZIP members without
extracting them. Files are private and not cached publicly. A missing or replaced
edition returns 404 instead of presenting an unrelated source.

This does **not** restore PDF timetable uploads: timetable import remains images
and CSV. PDF files here are reference handbooks only. No external paid service,
API key, AI request or production database write is involved.

## Extending coverage

For any OAU department, verify the complete course code and title against an
official handbook/course list. Record its programme, edition/session (or explicit
unknown/historical note), URL and page/section. Check repeated lists for conflicts;
omit unresolved pairs or store distinct candidates with explanatory edition notes.
Review the resulting JSON diff and run the course-suggestion and import tests.
Never add a plausible title from model memory or imply a source is current merely
because it is still online. The date of retrieval is not the curriculum date.

Adding a file to the folder does not publish its titles automatically. Review its
OAU provenance, programme and edition, extract explicit pairs, inspect wrapped
headings and conflicting tables, then add the manifest and curated entries.
Exclude national sample curricula or sources of uncertain institutional origin.
Run the catalogue tests after updating counts and the inventory. Replacing an
existing file requires a new reviewed checksum and corresponding page references.
No database migration or bulk creation of Course records is necessary.

The existing Course model still stores one title per unique course code. Alternative
handbook titles are suggestion evidence, not parallel Course records. An existing
Course is reused; choosing a suggestion never silently renames that saved record.
