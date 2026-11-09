# OAU teaching and study space catalogue

Updated 9 November 2026. Django admin offers **134 documented room names** and
**14 teaching/study room types**, both as searchable dropdowns followed by **Others**.
Selecting Others reveals a custom room-name or room-type text box.
This focuses Optispace on teaching and study spaces, excluding residential rooms.

**This is an expanded evidence-based catalogue, not a verified complete current OAU
inventory.** Most names are documented in historical university records. Their
presence does not establish present-day access, capacity, facilities or continued
use. Administrators still choose the actual building, capacity and room type.
Selecting a suggestion does not create every catalogue room in the database.

## Using the fields

Search matches words in any order, including department names and documented
abbreviations. Punctuation and spacing are ignored: `ODLT1`, `CH102`, and `LGS SRm2`
find their corresponding choices. Others stays last and remains available during
search. Select it to enter a teaching/study room or type missing from the suggestions.
The custom value is required, trimmed and limited to 200 characters for room names
and 100 for room types. Selecting a listed option uses that option instead of any
text left in the custom box. Without JavaScript the native selects and custom text
boxes still work, with the same server validation. Django's bundled Select2 provides search and follows the admin
light, dark and automatic themes without a CDN or new runtime dependency.

Existing records keep their names, types, IDs, permanent URL codes, building links,
facilities, timetables and reservations. An existing name or type absent from the
new catalogue opens under **Others**, with its current text filled in and editable.
Saving a custom value does not add it to the researched suggestion list.
An administrator can choose a documented name
for an existing room, keeping its permanent URL and linked records. The admin form
rejects duplicate names and documented aliases of already-saved rooms (for example,
`FBLT` and `First Bank Lecture Theatre (FBLT)`). It does not merge existing duplicates.

The building-name dropdown retains its existing Others behaviour. Campus area is
stored on the building and inherited by its rooms; see the [building catalogue](building-catalog.md).

## Evidence and limits

The public PDFs below were downloaded and inspected for this update, including the
venue columns across the entire 55-page 2014 list. The two supplied lecture timetable
images were also inspected. The older Geology and Mathematics evidence is retained
from the previous catalogue research; it could not be rechecked on 9 November
because of an anti-bot page and a certificate error respectively. Other departmental
sites were blocked or unavailable, and the eportal home page did not expose a
complete downloadable room inventory. These access limits do not prove that no
such inventory exists.

| Source ID | Source and date | What it establishes |
| --- | --- | --- |
| SER001 | [OAU Department of English SER001 class allocation](https://eportal.oauife.edu.ng/SER001.pdf), 2021/2022, 2 pages | Named venues used for teaching; broad labels without identifiable rooms are excluded. |
| PUTME2014 | [OAU screening venue list](https://eportal.oauife.edu.ng/2014PUTMEOfficials.pdf), 2014, 55 pages | Historical names/numbers for classrooms, lecture theatres, laboratories, studios, libraries and academic meeting spaces; not a current access or capacity survey. |
| GEOLOGY2022 | [OAU Geology refurbishment report](https://gly.oauife.edu.ng/alumni-refurbish-teaching-laboratories-classrooms-and-fieldwork-bus/), 1 March 2022 | Classrooms F5, F13 and F17; retained evidence from the earlier research. |
| MATHS2024 | [OAU Mathematics seminar announcement](https://science.oauife.edu.ng/peaa-professorial-chair-in-mathematics-seminar-series-2-0/), 25 July 2024 | Mathematics seminar venue MBA 213; retained evidence from the earlier research. |
| LAW_TIMETABLE | User-supplied Law lecture timetable, 2023/2024 Harmattan (`photo_2026-10-26_15-41-40.jpg`) | LAW 207 and AMPHI venue cells. Original photograph is not committed. |
| CHEM_TIMETABLE | User-supplied Chemistry lecture timetable, 2021/2022 Rain (`photo_2026-10-26_15-41-23.jpg`) | CH 220 venue cells. Original photograph is not committed. |

Names are normalised for readability. Source abbreviations and documented equivalent
labels are searchable aliases of one choice, not separate rooms. Combined room
numbers in the source remain combined; no missing numbers are filled in by guesswork.
Names such as 1,000-Seater and 500-Seater are source names, not current verified
capacity values. Staff details from source documents are not copied into this catalogue.

The following are deliberately not expanded into room choices:

- Staff School primary classrooms and venues at the separate Moro campus.
- Hostel bedrooms, staff offices, stores, toilets and other non-study spaces.
- Oduduwa main-bowl seating wings as separate rooms.
- Duplicate EDM Studio II labels and MDL I/II/III listings whose physical identities
  cannot be distinguished safely from the available source.
- A generic HSLT alongside the separately documented HSC A/B/C rooms, or Social
  Sciences theatres I/II alongside A/B without confirming whether these are aliases.
- A separate New Moot Court from the supplied Law image until its relationship to
  the historical Law Lecture Theatre I / Moot and Mock Court is established.

Further faculty inventories or current timetables are needed to close these gaps
and to verify renamed, newly built or decommissioned rooms. There is no claim that
134 is the total number of OAU teaching and study spaces.

## Selectable room names

The table mirrors `backend/rooms/data/teaching_spaces.json`. Page numbers refer to
PDF pages; venue/allocation numbers refer to the source tables.

| # | Room name | Source | Location in source |
| --- | --- | --- | --- |
| 1 | 1,000-Seater Lecture Theatre (1000 SLT) | SER001 | p. 1, allocation 5 |
| 2 | Administration Boardroom 236 | PUTME2014 | p. 4, venue 203 |
| 3 | Administration Room 220/221 | PUTME2014 | p. 4, venue 201 |
| 4 | Administration Room 232/233 | PUTME2014 | p. 4, venue 202 |
| 5 | Agricultural Economics Room 313 | PUTME2014 | p. 11, venue 504 |
| 6 | Agricultural Engineering Annex Lecture Room I (AGE I) | PUTME2014 | p. 38, venue 1301 |
| 7 | Agricultural Engineering Annex Lecture Room II (AGE II) | PUTME2014 | p. 38, venue 1302 |
| 8 | Agriculture Crop Science Laboratory | PUTME2014 | p. 11, venue 506 |
| 9 | Agriculture Lecture Theatre A (AGLT A) | PUTME2014 | p. 10, venue 501 |
| 10 | Agriculture Lecture Theatre B (AGLT B) | PUTME2014 | p. 10, venue 502 |
| 11 | Agriculture Lecture Theatre C (AGLT C) | PUTME2014 | p. 11, venue 503 |
| 12 | Agriculture Soil Science Laboratory | PUTME2014 | p. 11, venue 505 |
| 13 | Ajose Lecture Theatre (AJSLT) | SER001 | p. 1, allocation 7 |
| 14 | Amphitheatre (AMPHI) | LAW_TIMETABLE | Monday 11–12 and Thursday 12–1 SEL 001 venue cells |
| 15 | Architecture Audio-Visual Studio (Former Central Cafeteria) | PUTME2014 | p. 15, venue 701 |
| 16 | Architecture Studio 2 (Former Central Cafeteria) | PUTME2014 | p. 15, venue 702 |
| 17 | Architecture Studio 3 (Former Central Cafeteria) | PUTME2014 | p. 15, venue 703 |
| 18 | Architecture Studio 4 (Former Central Cafeteria) | PUTME2014 | p. 15, venue 704 |
| 19 | Arts Block I Room 402 | PUTME2014 | p. 1, venue 101 |
| 20 | Arts Block I Room 403 | PUTME2014 | p. 1, venue 102 |
| 21 | Arts Block I Room 404 | PUTME2014 | p. 2, venue 103 |
| 22 | Arts Block II Boardroom 402 | PUTME2014 | p. 2, venue 104 |
| 23 | Arts Block II Room 404 | PUTME2014 | p. 2, venue 105 |
| 24 | Auditorium I (AUD I) | SER001 | p. 1, allocation 6 |
| 25 | Auditorium II (AUD II) | SER001 | p. 1, allocation 4 |
| 26 | Biochemistry Seminar Room G.26/29 | PUTME2014 | p. 26, venue 1010 |
| 27 | Biological Sciences Lecture Theatre (BOOA) | PUTME2014 | p. 23, venue 1001 |
| 28 | Biological Sciences Lecture Theatre (BOOB) | PUTME2014 | p. 23, venue 1002 |
| 29 | BOOC Lecture Theatre | SER001 | p. 1, allocation 11 |
| 30 | Botany Seminar Room G.17 | PUTME2014 | p. 26, venue 1011 |
| 31 | Chemical Engineering and Food Technology 500-Seater Auditorium | PUTME2014 | p. 39, venue 1404; historical name, not a current capacity |
| 32 | Chemical Engineering and Food Technology Room I (TCH I) | PUTME2014 | p. 39, venue 1401 |
| 33 | Chemical Engineering and Food Technology Room II (TCH II) | PUTME2014 | p. 39, venue 1402 |
| 34 | Chemical Engineering and Food Technology Room III (TCH III) | PUTME2014 | p. 39, venue 1403 |
| 35 | Chemistry Lecture Theatre 102 (CH 102) | PUTME2014 | p. 29, venue 1106 |
| 36 | Chemistry Lecture Theatre 202 (CH 202) | PUTME2014 | p. 30, venue 1108 |
| 37 | Chemistry Lecture Theatre 203 (CH 203) | PUTME2014 | p. 30, venue 1109 |
| 38 | Chemistry Part I Laboratory | PUTME2014 | p. 29, venue 1103 |
| 39 | Chemistry Part II Laboratory | PUTME2014 | p. 29, venue 1104 |
| 40 | Chemistry Part III Laboratory (Room 2.34) | PUTME2014 | p. 29, venue 1105 |
| 41 | Chemistry Room 220 (CH 220) | CHEM_TIMETABLE | Monday and Wednesday lecture venue cells; user-supplied timetable photograph |
| 42 | Chemistry Seminar Room 110 (CH 110) | PUTME2014 | p. 30, venue 1107 |
| 43 | Civil Engineering Lecture Theatre I (CEG I) | PUTME2014 | p. 41, venue 1501 |
| 44 | Civil Engineering Lecture Theatre II (CEG II) | PUTME2014 | p. 41, venue 1502 |
| 45 | Civil Engineering Seminar / Auditorium Room B203 | PUTME2014 | p. 41, venue 1503 |
| 46 | Civil Engineering Seminar Room C209 | PUTME2014 | p. 42, venue 1508 |
| 47 | Community Health Tutorial Room 1.24 | PUTME2014 | p. 19, venue 807 |
| 48 | Control and Instrumentation Room 203 | PUTME2014 | p. 42, venue 1507 |
| 49 | Dental Lecture Theatre Extension | PUTME2014 | p. 20, venue 810 |
| 50 | EDM Block I Boardroom | PUTME2014 | p. 12, venue 602 |
| 51 | EDM Block I URP Part 4 Studio | PUTME2014 | p. 12, venue 601 |
| 52 | EDM Block II First Floor URP Part 1 Studio | PUTME2014 | p. 13, venue 606 |
| 53 | EDM Block II First Floor URP Part 2 Studio | PUTME2014 | p. 13, venue 605 |
| 54 | EDM Block II First Floor URP Part 3 Studio | PUTME2014 | p. 13, venue 607 |
| 55 | EDM Block II Ground Floor Room 1 | PUTME2014 | p. 13, venue 603 |
| 56 | EDM Block II Ground Floor Room 24 | PUTME2014 | p. 13, venue 604 |
| 57 | Education Room 313/314 | PUTME2014 | p. 5, venue 301 |
| 58 | Education Room 315 | PUTME2014 | p. 5, venue 302 |
| 59 | Education Room 316/317 | PUTME2014 | p. 6, venue 303 |
| 60 | Education SEC Laboratory 324/325 | PUTME2014 | p. 6, venue 304 |
| 61 | Education Students' Library | PUTME2014 | p. 6, venue 305 |
| 62 | ETF Lecture Theatre | SER001 | p. 1, allocation 9 |
| 63 | First Bank Lecture Theatre (FBLT) | SER001 | p. 2, allocation 16 |
| 64 | Geography Teaching Laboratory (Social Sciences Room 207) | PUTME2014 | p. 35, venue 1201 |
| 65 | Geology Classroom F13 | GEOLOGY2022 | Classrooms F5, F13 and F17 |
| 66 | Geology Classroom F17 | GEOLOGY2022 | Classrooms F5, F13 and F17 |
| 67 | Geology Classroom F5 | GEOLOGY2022 | Classrooms F5, F13 and F17 |
| 68 | Health Sciences Lecture Theatre A (HSC A) | PUTME2014 | p. 17, venue 801 |
| 69 | Health Sciences Lecture Theatre B (HSC B) | PUTME2014 | p. 17, venue 802 |
| 70 | Health Sciences Lecture Theatre C (HSC C) | PUTME2014 | p. 18, venue 803 |
| 71 | ICAN Lecture Theatre | SER001 | p. 2, allocation 12 |
| 72 | Law Lecture Theatre I (Moot and Mock Court) | PUTME2014 | p. 9, venue 409 |
| 73 | Law Lecture Theatre II | PUTME2014 | p. 9, venue 410 |
| 74 | Law Room 201 | PUTME2014 | p. 7, venue 401 |
| 75 | Law Room 202 | PUTME2014 | p. 7, venue 402 |
| 76 | Law Room 203 | PUTME2014 | p. 8, venue 403 |
| 77 | Law Room 204 | PUTME2014 | p. 8, venue 404 |
| 78 | Law Room 205 | PUTME2014 | p. 8, venue 405 |
| 79 | Law Room 206 | PUTME2014 | p. 8, venue 406 |
| 80 | Law Room 207 | LAW_TIMETABLE | Monday 12–2, Wednesday 8–9; user-supplied timetable photograph |
| 81 | Law Room 208 | PUTME2014 | p. 8, venue 407 |
| 82 | Law Room 209 | PUTME2014 | p. 8, venue 408 |
| 83 | Local Government Studies Lecture Theatre | PUTME2014 | p. 45, venue 1701 |
| 84 | Local Government Studies Reading Room | PUTME2014 | p. 46, venue 1705 |
| 85 | Local Government Studies Seminar Room II | PUTME2014 | p. 45, venue 1702 |
| 86 | Local Government Studies Seminar Room III | PUTME2014 | p. 46, venue 1703 |
| 87 | Local Government Studies Seminar Room IV | PUTME2014 | p. 46, venue 1704 |
| 88 | Materials Science and Mechanical Testing Laboratory C208 | PUTME2014 | p. 42, venue 1509 |
| 89 | Materials Science X-ray Laboratory C103 | PUTME2014 | p. 42, venue 1506 |
| 90 | Mathematics Library (MBB 216, Yellow House Phase B) | PUTME2014 | p. 32, venue 1124 |
| 91 | Mathematics Seminar Room (MBA 213) | MATHS2024 | Seminar venue |
| 92 | Mechanical Engineering Room 205A | PUTME2014 | p. 42, venue 1504 |
| 93 | Mechanical Engineering Room 205B | PUTME2014 | p. 42, venue 1505 |
| 94 | Medical Illustration Seminar Laboratory | PUTME2014 | p. 20, venue 811 |
| 95 | Microbiology Part III Laboratory (MIC 1.03/1.06) | PUTME2014 | p. 25, venue 1008 |
| 96 | Microbiology Part IV Laboratory (MIC 1.15) | PUTME2014 | p. 26, venue 1009 |
| 97 | Nursing Demonstration Room 1.21 | PUTME2014 | p. 20, venue 809 |
| 98 | Nursing Reading Room 1.30 | PUTME2014 | p. 19, venue 808 |
| 99 | Oduduwa Lecture Theatre I (ODLT I) | SER001 | p. 2, allocation 14 |
| 100 | Oduduwa Lecture Theatre II (ODLT II) | SER001 | p. 2, allocation 13 |
| 101 | Part-Time Nursing Room | PUTME2014 | p. 20, venue 812 |
| 102 | Pharmaceutical Chemistry Laboratory (Room 106) | PUTME2014 | p. 22, venue 905 |
| 103 | Pharmaceutical Chemistry Main Laboratory (Room 111) | PUTME2014 | p. 22, venue 906 |
| 104 | Pharmaceutics Laboratory (Room 103) | PUTME2014 | p. 22, venue 907 |
| 105 | Pharmacognosy Laboratory (Room 210) | PUTME2014 | p. 22, venue 903 |
| 106 | Pharmacology Laboratory (Room 205/206) | PUTME2014 | p. 22, venue 904 |
| 107 | Pharmacy Lecture Theatre (ESLT) | PUTME2014 | p. 21, venue 902 |
| 108 | Pharmacy Lecture Theatre (MQLT) | PUTME2014 | p. 21, venue 901 |
| 109 | Physics Lecture Theatre 102/103 | PUTME2014 | p. 30, venue 1112 |
| 110 | Physics Lecture Theatre 202/203 | PUTME2014 | p. 31, venue 1115 |
| 111 | Physics Part I Laboratory | PUTME2014 | p. 30, venue 1110 (two wings kept together) |
| 112 | Physics Part II Laboratory | PUTME2014 | p. 30, venue 1111 |
| 113 | Physics Room 130 | PUTME2014 | p. 31, venue 1114 |
| 114 | Physics Room 239 | PUTME2014 | p. 30, venue 1113 |
| 115 | Plant Physiology Laboratory G.21/G.23 | PUTME2014 | p. 26, venue 1012 |
| 116 | Postgraduate Lecture Theatre C (PG LT C) | SER001 | p. 2, allocation 15 |
| 117 | Social Sciences Boardroom | PUTME2014 | p. 36, venue 1207 |
| 118 | Social Sciences Lecture Theatre A (SSLT A) | SER001 | p. 2, allocation 18 |
| 119 | Social Sciences Lecture Theatre B (SSLT B) | SER001 | p. 2, allocation 20 |
| 120 | Social Sciences Room 211 | PUTME2014 | p. 35, venue 1203 |
| 121 | Social Sciences Room 233 | PUTME2014 | p. 35, venue 1204 |
| 122 | Urban Design Studio (Social Sciences Room 206) | PUTME2014 | p. 35, venue 1202 |
| 123 | Yellow House Phase B Room MBB 020 | PUTME2014 | p. 31, venue 1118 |
| 124 | Yellow House Phase B Room MBB 021 | PUTME2014 | p. 31, venue 1119 |
| 125 | Yellow House Phase B Room MBB 022 | PUTME2014 | p. 31, venue 1120 |
| 126 | Yellow House Phase B Room MBB 114 | PUTME2014 | p. 31, venue 1121 |
| 127 | Yellow House Phase B Room MBB 115 | PUTME2014 | p. 32, venue 1122 |
| 128 | Yellow House Phase B Room MBB 116 | PUTME2014 | p. 32, venue 1123 |
| 129 | Yellow House Phase B Room MBB 218 | PUTME2014 | p. 32, venue 1125 |
| 130 | Yellow House Phase B Room MBB 219 | PUTME2014 | p. 32, venue 1126 |
| 131 | Yellow House Phase C Seminar Room MBB 212 | PUTME2014 | p. 31, venue 1117 |
| 132 | Zoology General Teaching Laboratory 1.23/1.24 | PUTME2014 | p. 27, venue 1015 |
| 133 | Zoology Part IV Laboratory Z 1.22 | PUTME2014 | p. 27, venue 1014 |
| 134 | Zoology Undergraduate Laboratory Z 1.01 | PUTME2014 | p. 26, venue 1013 (two wings kept together) |

## Selectable room types

These are practical app categories, not a complete official OAU taxonomy. Choose
the function of the actual room; names do not automatically set or constrain types.

| Type | Example or classification guidance |
| --- | --- |
| Lecture Theatre | Oduduwa Lecture Theatre I; CH 102 |
| Classroom | Law Room 207; Geology Classroom F5 |
| Tutorial Room | Community Health Tutorial Room 1.24 |
| Seminar Room | Mathematics Seminar Room MBA 213 |
| Auditorium | Auditorium I; Chemical Engineering and Food Technology auditorium |
| Amphitheatre | AMPHI in the supplied Law timetable |
| Reading Room | Nursing Reading Room 1.30; Local Government Studies Reading Room |
| Library | Education Students' Library; Mathematics Library MBB 216 |
| Computer Laboratory | Retained functional category for computer-based teaching; the sources checked for this expansion do not establish a separately named computer laboratory to add. |
| Laboratory | Chemistry Part I Laboratory; Geography Teaching Laboratory |
| Studio | EDM URP and Architecture teaching studios |
| Demonstration Room | Nursing Demonstration Room 1.21 |
| Moot Court | Law Lecture Theatre I / Moot and Mock Court |
| Meeting Room | Academic boardrooms where authorised teaching/study use is appropriate |

The previous generic Event Hall and Seminar Hall categories are not among the
teaching/study suggestions. Custom types can be entered through Others, and
existing records reopen with their saved type as described above.
A laboratory or academic boardroom being listed does not establish that students
may use it freely: administrators must confirm suitability and access before
adding it to Optispace.

Room type does not determine availability: active classes show Occupied and
approved reservations show Reserved during their intervals for every room type,
including existing types. The established timetable/booking rules are unchanged.

## Maintaining the catalogue

Add verified names, aliases, source IDs and exact source locations to
`backend/rooms/data/teaching_spaces.json`; keep the names sorted and update this
table. Do not infer room numbers from ranges or add unverified aliases. If a name
changes in the catalogue, existing database records are preserved automatically.
No data migration or bulk room creation is part of this update.
