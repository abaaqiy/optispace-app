# Part selection added to the 312fbd1 image review

This local feature adds a programme/Part view directly to commit `312fbd1` on
`feature/part-selection`. The original commit is preserved on `compare/312fbd1`;
`a48306b` is preserved on `feature/backend`, and `c105c40` on
`feature/level-review`. This branch adds the selector to the existing sections.

## Administrator workflow

1. Upload the full lecture timetable image or reopen an existing saved draft.
   Extraction runs for the whole image as before.
2. In **1. Confirm shared details**, select **Programme and handbook**. Use the
   edition for the department/programme and cohort on this timetable, then confirm
   the applicability checkbox. For example, Chemistry and Industrial Chemistry
   have separate curriculum profiles even though they are in the same department.
3. Choose **Level / Part**. Part 1–6 and **Unassigned / uncertain** are available;
   **All extracted entries** restores the complete review view. Each option shows
   its retained-entry count. The page also shows overall review progress.
4. Review each Part using the existing sections. Switching Parts keeps all rows,
   prepared records, corrections, skipped entries, unfinished fields and review
   ticks in the full draft. Autosave and the Save draft button work as before.
5. Finish the Parts and Unassigned entries, check the full source for omissions,
   then use the existing **Validate reviewed entries → Confirm and import** steps.
   Validation still requires every retained row to be reviewed, including hidden
   Parts. Import still saves the full retained timetable in one transaction.

## What selecting Chemistry Part III displays

| Existing section | Display after choosing Part III |
| --- | --- |
| Confirm shared details | The existing faculty, department, semester and source details, with the selected programme/handbook and Part III. |
| Resolve missing courses and venues once | Unresolved Part III courses and the venues actually attached to those courses, including shared teaching spaces. Proposed records/buildings linked to this Part are shown; saved choices remain reusable. |
| Compare the weekly preview with the image | Part III course/venue/day/time cards in the existing weekly grid. Clicking one opens its source cell and correct editor page. Overlap warnings still check all retained Parts. |
| Check shared headings once | Weekday/time headings used by Part III entries. A heading correction affects this Part's entries, preserving other Parts' individual values. |
| Review clear entries by day | Eligible Part III entries grouped under their weekdays. The review action affects this Part only. |
| Review extracted entries | Part III rows with their original source positions, choices and times. Search, day/page filters and pagination operate within the selected Part. |
| Source image | The complete original image, with existing zoom and source-cell highlighting. |
| Your saved image drafts | The complete draft, including its current Part view and all edits, with the existing 24-hour expiry after each save. |
| Final validation/import | The complete retained timetable, using the original duplicate, permissions and overlap checks. |

With a Part selected, mapping/correction actions in section 2 affect its visible
entries. The course/room/building catalogue remains shared across the draft; once
prepared, a record can be reused in another Part without entering its fields again.
Editing a shared prepared record updates that record wherever it is referenced,
clearing affected review ticks as in the original editor.

## Evidence and uncertain assignments

- An explicitly detected PART column supplies the timetable's Part evidence.
  Arbitrary CLASS/group labels are not automatically treated as Parts. Old drafts
  lacking explicit Part metadata can use the handbook or a manual assignment.
- After the administrator confirms an applicable handbook, exact course codes
  are checked in that programme's reviewed curriculum tables. A code associated
  with one Part is shown in that Part. Course digits are never used as a shortcut.
- A code listed in several curriculum Parts remains Unassigned until the actual
  attending Part(s) are confirmed. This can arise from electives, direct-entry
  requirements or jointly taught classes; it does not prove all cohorts attend
  the same session. An explicit image Part heading takes priority.
- Unknown or uncertain OCR course codes remain Unassigned. The feature does not
  generate courses or venues from handbook lists. Selecting a Part preserves the
  course/venue/day/time associations in the extracted rows.
- **Check / correct Part** in an extracted row shows its evidence and physical PDF
  page links. Assign one or several Parts manually when necessary. If every
  occurrence of a course belongs to the same cohorts, apply that assignment once
  to all its entries. Leaving all Parts unchecked keeps it Unassigned.
- Unfinished Part checkboxes autosave but are not applied until the administrator
  chooses the assignment button. A manual assignment belongs to the exact code;
  changing that code stops using the old assignment. Switching the handbook
  clears unfinished Part checkbox choices, while preserving class review ticks.
- A jointly attended entry may appear in several Part views but remains a single
  extracted row. The original import planner continues to reject duplicate rows
  and overlapping saved classes/reservations.

## Handbook coverage and maintenance

The initial catalogue reuses the reviewed evidence from `c105c40`: **19 programme
profiles from 17 supplied handbook sources**, with 1,518 evidence entries. It is
partial and separate from the broader course-title catalogue. Historical B.Pharm
is explicitly not verified for PharmD. No accuracy percentage or complete OAU
curriculum coverage is claimed.

`backend/scheduling/data/level_curricula.json` pins programme curriculum page spans
and column layouts to sources/checksums in `handbook_sources.json`.
`course_levels.json` stores exact course-code/Part/page/heading evidence. Handbooks
are served through the existing protected local course-handbook URL. Review new
programme page ranges and rebuild when supplied handbooks expand the coverage:

```sh
DATABASE_URL='postgresql://optispace_local@127.0.0.1:55439/optispace_document_dev?sslmode=disable' \
DJANGO_DEBUG=true venv/bin/python backend/manage.py build_level_catalogue \
  --directory /home/user/Downloads/handbooks
```

The command checks the pinned handbook editions and uses `pdftotext -layout` to
read explicit curriculum headings. Prerequisite columns and unrelated prose are
excluded. It writes the catalogue only after all manifest profiles succeed; it
does not write database records. A file added to the folder needs a reviewed
manifest entry before its Part evidence becomes available.

## Scope and verification

This addition uses the existing draft JSON and needs no migration. The original
image planner, CSV import/export, draft storage/expiry, models, timetable rules,
manual administration and OCR extraction logic remain in use. Extraction adds
only explicit Part/group metadata needed for the selector.

Tests check the original 18 review-editor cases and new section filtering,
programme evidence, unknown/multiple Parts, pagination/source navigation,
manual choices, shared headings, Part-specific bulk actions, draft reopening,
permission checks and full-image validation/import. All work is local; pushing
or deploying this branch is a separate action.
