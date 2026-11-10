from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase

from .services.document_extract import parse_table
from .services.image_ocr import Cell, reread_course_codes
from .services.timetable_import import ImportProblem
from .test_document_import import grid


class CourseReaderReviewTests(SimpleTestCase):
    def test_disagreements_flag_any_department_without_replacing_data(self):
        cells = [Cell('PUL301', (0, 0, 100, 40)), Cell('CSC102', (100, 0, 200, 40))]
        words = [
            {'text': 'PUL307', 'x0': 20, 'x1': 80, 'top': 15, 'bottom': 30},
            {'text': 'CSC102', 'x0': 20, 'x1': 80, 'top': 70, 'bottom': 85},
        ]
        with patch('scheduling.services.image_ocr.run_ocr', return_value=words):
            reread_course_codes(cells, np.full((40, 200), 255, dtype=np.uint8))
        self.assertEqual([cell.text for cell in cells], ['PUL301', 'CSC102'])
        self.assertIn('PUL301 / PUL307', cells[0].note)
        self.assertEqual(cells[1].note, '')
        self.assertEqual(cells[0].box, (0, 0, 100, 40))

    def test_optional_reader_timeout_preserves_all_unchecked_cells_with_warning(self):
        cells = [Cell('DSS101', (0, 0, 100, 40)), Cell('PCG202', (100, 0, 200, 40))]
        with patch('scheduling.services.image_ocr.run_ocr', side_effect=ImportProblem('Reading took too long')):
            reread_course_codes(cells, np.full((40, 200), 255, dtype=np.uint8))
        self.assertEqual([cell.text for cell in cells], ['DSS101', 'PCG202'])
        self.assertTrue(all('could not finish' in cell.note for cell in cells))

    def test_disagreement_reaches_review_with_correct_day_time_and_venue(self):
        table = grid(('', 'Monday', '', 'Tuesday', ''), ('TIME', 'COURSE', 'VENUE', 'COURSE', 'VENUE'),
                     ('8-9', 'CSC102', 'STEP A', '', ''))
        table[2][1].note = 'Course-code readers disagree (CSC102 / CSC107).'
        rows, _, _ = parse_table(table)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['course_text'], rows[0]['room_text'], rows[0]['day'], rows[0]['start_time']),
                         ('CSC102', 'STEP A', 'Monday', '08:00'))
        self.assertIn('readers disagree', rows[0]['note'])
