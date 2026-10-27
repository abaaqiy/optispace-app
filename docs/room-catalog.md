# OAU room suggestions in Django admin

Researched 24 October 2026. These are selection suggestions, not newly inserted
database records or a complete current university inventory. Several names come
from historical records. Administrators should confirm the venue they are entering;
capacity, access, facilities and room type are not inferred from the selected name.

The form has one visible **Room name** control: 50 names and **Others — enter a
room name**. Search matches any part of the name or abbreviation while typing.
Others reveals a text box whose value is saved as the name. The URL identifier is
generated automatically and retained when a room is renamed. Existing custom names
open under Others with their text preserved. Duplicate names are rejected without
merging existing records.

## Sources and entries

- **A:** OAU Department of English, [2021/2022 SER 001 teaching allocation](https://eportal.oauife.edu.ng/SER001.pdf).
- **B:** OAU, [2014 Post-UTME venue list](https://eportal.oauife.edu.ng/2014PUTMEOfficials.pdf),
  PDF pages 1–13. Combined room numbers are retained as one venue, not split into
  invented individual rooms.
- **C:** Geology, [classroom refurbishment report](https://gly.oauife.edu.ng/alumni-refurbish-teaching-laboratories-classrooms-and-fieldwork-bus/), 1 March 2022.
- **D:** Faculty of Science, [Mathematics seminar announcement](https://science.oauife.edu.ng/peaa-professorial-chair-in-mathematics-seminar-series-2-0/), 25 July 2024.

| # | Name in the dropdown | Source |
| --- | --- | --- |
| 1 | Oduduwa Lecture Theatre I (ODLT I) | A |
| 2 | Oduduwa Lecture Theatre II (ODLT II) | A |
| 3 | First Bank Lecture Theatre (FBLT) | A |
| 4 | ICAN Lecture Theatre | A |
| 5 | ETF Lecture Theatre | A |
| 6 | BOOC Lecture Theatre | A |
| 7 | Health Sciences Lecture Theatre (HSLT) | A |
| 8 | 1,000-Seater Lecture Theatre (1000 SLT) | A; name, not verified current capacity |
| 9 | Auditorium I (AUD I) | A, B |
| 10 | Auditorium II (AUD II) | A, B |
| 11 | Agriculture Lecture Theatre A (AGLT A) | B |
| 12 | Agriculture Lecture Theatre B (AGLT B) | B |
| 13 | Agriculture Lecture Theatre C (AGLT C) | B |
| 14 | Social Sciences Lecture Theatre A (SSLT A) | A |
| 15 | Social Sciences Lecture Theatre B (SSLT B) | A |
| 16 | Postgraduate Lecture Theatre C (PG LT C) | A |
| 17 | Geology Classroom F5 | C |
| 18 | Geology Classroom F13 | C |
| 19 | Geology Classroom F17 | C |
| 20 | Mathematics Seminar Room (MBA 213) | D |
| 21 | Arts Block I Room 402 | B |
| 22 | Arts Block I Room 403 | B |
| 23 | Arts Block I Room 404 | B |
| 24 | Arts Block II Boardroom 402 | B |
| 25 | Arts Block II Room 404 | B |
| 26 | Administration Room 220/221 | B |
| 27 | Administration Room 232/233 | B |
| 28 | Administration Boardroom 236 | B |
| 29 | Education Room 313/314 | B |
| 30 | Education Room 315 | B |
| 31 | Education Room 316/317 | B |
| 32 | Education SEC Laboratory 324/325 | B |
| 33 | Education Students' Library | B |
| 34 | Law Room 201 | B |
| 35 | Law Room 202 | B |
| 36 | Law Room 203 | B |
| 37 | Law Room 204 | B |
| 38 | Law Room 205 | B |
| 39 | Law Room 206 | B |
| 40 | Law Room 208 | B |
| 41 | Law Room 209 | B |
| 42 | Law Lecture Theatre I (Moot and Mock Court) | B |
| 43 | Law Lecture Theatre II | B |
| 44 | Agricultural Economics Room 313 | B |
| 45 | Agriculture Soil Science Laboratory | B |
| 46 | Agriculture Crop Science Laboratory | B |
| 47 | EDM Block I Boardroom | B |
| 48 | EDM Block I URP Part 4 Studio | B |
| 49 | EDM Block II Ground Floor Room 1 | B |
| 50 | EDM Block II Ground Floor Room 24 | B |

## Types and campus areas

The ten types are Lecture Theatre, Classroom, Seminar Room, Seminar Hall, Event Hall,
Reading Room, Computer Laboratory, Laboratory, Studio and Meeting Room: simple app
categories, not an official OAU classification. Room type does not determine
availability status: approved bookings show Reserved during their interval for
all types, including existing custom types. Active classes show Occupied.

The campus-area list was expanded on 25 October 2026 to the 16 faculties and
colleges requested by the project owner:

- College of Health Sciences
- Faculty of Administration
- Faculty of Agriculture
- Faculty of Arts
- Faculty of Basic Medical Sciences
- Faculty of Clinical Sciences
- Faculty of Computing Science and Engineering
- Faculty of Dentistry
- Faculty of Education
- Faculty of Environmental Design and Management
- Faculty of Law
- Faculty of Pharmacy
- Faculty of Science
- Faculty of Social Sciences
- Faculty of Technology
- Postgraduate College

The Health Sciences college and its three constituent faculties are individually
selectable. Computing uses the single label **Faculty of Computing Science and
Engineering**. These are academic areas for navigating the app, not an official
numbered-zone inventory.

Campus-area selection now lives on **Buildings** only. Each room must belong to a
building and inherits its area; the former room-zone selector and stored override
have been removed. The building form keeps those 16 faculty/college areas and adds
Central Campus, Halls of Residence, and Research and Service Centres as app location
categories. Area search does not allow Others; existing custom areas remain
selectable on their building's edit form. Existing room types remain selectable on
their room's edit form. See [building catalogue and upgrade notes](building-catalog.md).

Options live in `backend/rooms/catalog.py`. Django's bundled Select2 powers search
without a CDN or extra runtime package. Without JavaScript, the native selects and
custom-name input still work and validation stays on the server.
All catalogue search fields follow Django admin's light, dark and automatic themes.
The dropdown panel, search input and options use the admin theme colours;
highlighted options use its contrasting button text and background colours.
