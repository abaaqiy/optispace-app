from datetime import time

from django import forms
from django.contrib.admin.widgets import AdminTimeWidget
from django.test import SimpleTestCase
from django.utils import formats

from .clocks import clock_label, parse_clock


class ClockFormatTests(SimpleTestCase):
    def test_noon_midnight_and_seconds_round_trip(self):
        for clock, text in ((time(0), '12:00 AM'), (time(12), '12:00 PM'), (time(14, 30), '2:30 PM'),
                            (time(23, 59, 8), '11:59:08 PM'), (time(0, 0, 1, 123456), '12:00:01.123456 AM')):
            self.assertEqual(clock_label(clock), text)
            self.assertEqual(parse_clock(text), clock)
        self.assertEqual(parse_clock('14:30'), time(14, 30))
        self.assertEqual(parse_clock('2:30pm'), time(14, 30))
        for invalid in ('00:30 PM', '13:00 PM', '2:00', '25:00', '12:60 AM', '1:00 XM'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_clock(invalid)

    def test_admin_display_and_input_use_am_pm_without_changing_values(self):
        self.assertEqual(formats.time_format(time(14, 30)), '2:30 PM')
        self.assertEqual(formats.get_format('TIME_INPUT_FORMATS')[0], '%I:%M:%S %p')
        widget = AdminTimeWidget()
        self.assertIn('02:30:00 PM', widget.render('clock', time(14, 30)))
        field = forms.TimeField(widget=widget)
        for value in ('02:30:00 PM', '2:30 PM', '14:30'):
            self.assertEqual(field.clean(value), time(14, 30))
