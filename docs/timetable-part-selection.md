# Part selection added to the 312fbd1 image review

This local feature adds a department/Part view directly to commit `312fbd1` on
`feature/part-selection`. The original commit is preserved on `compare/312fbd1`;
`a48306b` is preserved on `feature/backend`, and `c105c40` on
`feature/level-review`. This branch adds the selector to the existing sections.

## Administrator workflow

1. Upload the full lecture timetable image or reopen an existing saved draft.
   Extraction runs for the whole image as before.
2. In **1. Confirm shared details**, check the **Department** field, suggested
   from the image heading where possible. Matching handbook evidence is used
   automatically; there is no programme selector or applicability checkbox.
   Department names match regardless of case, `Department of`, or `&` versus
   `and`. Combined headings such as `Chemistry / Industrial Chemistry` are
   recognised when all their named components are known. Partial names and course
   digits are not used to guess a department or Part.
3. Choose **Level / Part**. Part 1–6 and **Unassigned / uncertain** are available;
   **All extracted entries** restores the complete review view. Each option shows
   its retained-entry count. The page also shows overall review progress.
4. Review each Part using the existing sections. Switching Parts keeps all rows,
   prepared records, corrections, skipped entries, unfinished fields and review
   ticks in the full draft. Autosave and the Save draft button work as before.
5. Check the selected Part against the image for omissions and correct its
   weekdays/time headings, then use **Validate reviewed entries → Confirm and
   import**. Only the selected Part's retained rows and required new records are
   validated and imported. Unreviewed rows and incomplete proposals from other
   Parts do not block this batch. Every retained row in the selection must still
   be reviewed, including those hidden by pagination or search.
   **All extracted entries** validates and imports every remaining retained row;
   **Unassigned / uncertain** validates and imports the retained unassigned rows.
6. After a Part is imported, the page returns to the same saved draft with the
   other entries, their corrections, unfinished editor fields and original image
   intact. Imported rows are removed from the remaining review and listed in its
   import history. Shared courses, rooms and buildings created by that batch
   become saved choices in the remaining Parts. A shared class assigned to several
   Parts is imported once and removed from each remaining view. Partial import
   saves the remaining draft for another 24 hours and clears its coverage check;
   the view returns to **All extracted entries** so the remaining work is visible.
   Choose another Part to continue. The draft closes after its final batch.
7. Saving and validation still protect edits from competing tabs.
   Save/Validate waits for background saving and submits the latest draft token.
   If an autosave response was lost but the submitted edits exactly match the
   saved draft, validation can continue. Different edits from a stale tab remain
   blocked to prevent overwriting someone else's review.
   Retired programme and confirmation fields do not count as changed edits when
   comparing an older draft. A genuine conflict shows **Save my edits as a new
   draft**, which preserves the source and every submitted correction in a private
   copy while leaving the newer original draft unchanged. **Open the latest saved
   draft in another tab** is also available for comparison.

## What selecting Chemistry Part III displays

| Existing section | Display after choosing Part III |
| --- | --- |
| Confirm shared details | The existing faculty, department, semester and source details, with automatically matched departmental evidence and Part III. |
| Resolve missing courses and venues once | Unresolved Part III courses and the venues actually attached to those courses, including shared teaching spaces. Proposed records/buildings linked to this Part are shown; saved choices remain reusable. |
| Compare the weekly preview with the image | Part III course/venue/day/time cards in the existing weekly grid. Clicking one opens its source cell and correct editor page. Overlap warnings still check all retained Parts. |
| Check shared headings once | Weekday/time headings used by Part III entries. A heading correction affects this Part's entries, preserving other Parts' individual values. |
| Review clear entries by day | Eligible Part III entries grouped under their weekdays. The review action affects this Part only. |
| Review extracted entries | Part III rows with their original source positions, choices and times. Search, day/page filters and pagination operate within the selected Part. |
| Source image | The complete original image, with existing zoom and source-cell highlighting. |
| Your saved image drafts | The complete draft, including its current Part view and all edits, with the existing 24-hour expiry after each save. |
| Final validation/import | Only the selected Part and its required records, using the original duplicate, permission and saved timetable/reservation overlap checks. Other Parts remain in the draft. All extracted entries includes every remaining level. |

With a Part selected, mapping/correction actions in section 2 affect its visible
entries. The course/room/building catalogue remains shared across the draft; once
prepared, a record can be reused in another Part without entering its fields again.
Editing a shared prepared record updates that record wherever it is referenced,
clearing affected review ticks as in the original editor.

## Evidence and uncertain assignments

- An explicitly detected PART column supplies the timetable's Part evidence.
  Arbitrary CLASS/group labels are not automatically treated as Parts. Old drafts
  lacking explicit Part metadata can use the handbook or a manual assignment.
- The Department field automatically selects the available reviewed curriculum
  tables. Exact course codes associated with one Part across those tables appear
  in that Part. Course digits are never used as a shortcut. Each row's evidence
  still identifies its programme and handbook page for checking.
- The supplied Chemistry timetable includes both CHM and ICH courses. A
  `Chemistry` or combined `Chemistry / Industrial Chemistry` department matches
  both profiles from the shared handbook. Where those profiles disagree, such as
  CHM304 (Chemistry Part III; Industrial Chemistry Part IV) and MAC201 (Parts IV
  and II respectively), the entry stays Unassigned. Their presence in one
  timetable alone does not establish which cohort attends a particular session.
- If there is no matching Part catalogue, all extracted rows remain accessible.
  Explicit image Part headings and manual assignments continue to work; there is
  no fallback to an unrelated department's handbook.
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
  changing that code stops using the old assignment. Editing the Department field
  recalculates counts and all review sections immediately, clearing unfinished
  Part checkbox choices while preserving saved assignments and class review ticks.
- A jointly attended entry may appear in several Part views but remains a single
  extracted row. The original import planner continues to reject duplicate rows
  and overlapping saved classes/reservations within the imported batch.

## Independent import batches

The server recomputes Part membership from the same departmental evidence,
explicit image headings and saved manual assignments used by the editor. The
preview signs the selected Part and its row indices along with the existing
draft/version/fingerprint. Changing the saved selection or edits invalidates the
preview; confirmation cannot widen the batch using posted rows or indices.
Successful imports and preservation of the remaining draft commit together in
one transaction. The original image remains available until all retained entries
are imported, or the remaining draft expires.

For example, after reviewing only Chemistry Part 1, **Validate reviewed entries**
previews that Part's weekly slots expanded through the saved semester dates.
**Confirm and import** saves those classes. Parts 2–4 and uncertain entries keep
their edits and remain unimported. Selecting **All extracted entries** later
requires those remaining entries to be reviewed before their own import.

## Handbook coverage and maintenance

The initial catalogue reuses the reviewed evidence from `c105c40`: **19 programme
profiles from 17 supplied handbook sources**, with 1,518 evidence entries. It is
partial and separate from the broader course-title catalogue. Historical B.Pharm
is automatically used only when the department/image heading identifies B.Pharm
and does not identify PharmD. An unspecified Pharmacy or a PharmD timetable keeps
image/manual Part assignment available instead. No accuracy percentage or
complete OAU curriculum coverage is claimed.

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
department edits, combined department names, historical programme restrictions,
permission checks, agreement between browser and server classification, selected
Part validation/import, shared-record reuse, remaining draft preservation,
replayed/stale previews and full-image validation/import in All mode. Retired
programme/confirmation fields in older drafts are ignored and removed on their
next save. All work is local; pushing or deploying this branch is a separate action.
