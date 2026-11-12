"""Read explicit curriculum Part headings within reviewed programme page ranges.

No course-number heuristic. Prerequisite columns and prose mentions are excluded.
Only the manifest's programme pages are indexed; unrelated handbook sections are not.
"""
import re

PARTS = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, '1V': 4, 'V': 5, 'VI': 6,
         'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5, 'SIX': 6}
PART_PATTERN = r'(?:VI|IV|III|II|1V|I|V|ONE|TWO|THREE|FOUR|FIVE|SIX|[1-6])'
HEADING = re.compile(rf'\bPART\s+({PART_PATTERN})\b|\b([1-6])00\s*LEVEL\b', re.I)
CODE = re.compile(r'\b([A-Z]{2,5})\s*(\d{3})(?!\d)')


def heading_level(line):
    line = line.replace('–', '-').replace('—', '-')
    matches = list(HEADING.finditer(line))
    if len(matches) != 1 or len(line.strip()) > 110 or CODE.search(line):
        return None
    # Do not treat prose about admission, previous courses or course content as a heading.
    if re.search(r'\b(admitted|admission|students|candidate|proceed|exempt|covered|minimum)\b', line, re.I):
        return None
    prefix = line[:matches[0].start()].strip(' :.-()0123456789')
    if prefix and not re.fullmatch(r'(?:HARMATTAN|RAIN|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|YEAR|SEMESTER|COURSE|OUTLINE|\s|[-()])*', prefix, re.I):
        return None
    part, digit = matches[0].groups()
    return int(digit) if digit else PARTS.get(part.upper(), int(part) if part.isdigit() else None)


def extract_level_entries(pages, profile):
    entries = {}
    for span in profile['spans']:
        columns = span.get('columns', 1)
        states = [None] * columns
        stopped = [False] * columns
        for number in range(span['first'], span['last'] + 1):
            lines = pages[number - 1].splitlines()
            width = max(map(len, lines), default=0)
            midpoint = width // 2
            for line in lines:
                if span.get('stop') and span['stop'].casefold() in line.casefold():
                    stopped = [True] * columns
                whole_level = heading_level(line) if span.get('shared_heading') else None
                if whole_level:
                    states = [(whole_level, ' '.join(line.split()))] * columns
                    continue
                split = midpoint
                if columns == 2 and span.get('shared_heading'):
                    # Semester tables can change width even within one page.
                    # Cut at the second course column, not through its code or
                    # through the first table's trailing credit-unit values.
                    codes = list(CODE.finditer(line))
                    if len(codes) >= 2 and codes[0].start() < midpoint * .6 and codes[1].start() > midpoint * .8:
                        split = codes[1].start()
                pieces = [line] if columns == 1 else [line[:split], line[split:]]
                for col, piece in enumerate(pieces):
                    if stopped[col] or 'only_column' in span and col != span['only_column']:
                        continue
                    level = heading_level(piece)
                    if level:
                        states[col] = (level, ' '.join(piece.split()))
                        continue
                    if not states[col]:
                        continue
                    matches = list(CODE.finditer(piece))
                    if not matches:
                        continue
                    match = matches[0]
                    before = piece[:match.start()].strip()
                    # Main code column can follow a short grouping label, but not prose.
                    if before and not re.fullmatch(r'(?:[a-z]\)|\*|/|Core[- ]?|General|Studies|courses|compulsory|compulsor|[abc])(?:\s|[-*/])*', before, re.I):
                        continue
                    if match.start() > max(38, len(piece) * 0.4):
                        continue
                    if re.match(r'\s*(?:is\b|&|and\b)', piece[match.end():], re.I):
                        continue
                    code = match[1] + match[2]
                    level, heading = states[col]
                    entries[(code, level, number)] = {'code': code, 'level': level, 'page': number, 'heading': heading}
    return sorted(entries.values(), key=lambda entry: (entry['level'], entry['code'], entry['page']))
