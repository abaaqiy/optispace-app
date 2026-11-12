"""Display local wall-clock times without changing timezone or storage values."""
from datetime import datetime
import re


def clock_label(value, *, seconds=False):
    label = f"{value.hour % 12 or 12}:{value.minute:02d}"
    if seconds or value.second or value.microsecond:
        label += f":{value.second:02d}"
        if value.microsecond:
            label += f".{value.microsecond:06d}"
    return f"{label} {'PM' if value.hour >= 12 else 'AM'}"


def parse_clock(value):
    """Accept explicit AM/PM plus existing unambiguous 24-hour CSV values."""
    if re.fullmatch(r"(?:0?[1-9]|1[0-2]):[0-5]\d(?::[0-5]\d(?:\.\d{1,6})?)?\s*[AP]M", value, re.I):
        value = re.sub(r'\s*([AP]M)$', r' \1', value.upper())
        pattern = '%I:%M:%S.%f %p' if '.' in value else '%I:%M:%S %p' if value.count(':') == 2 else '%I:%M %p'
        return datetime.strptime(value, pattern).time()
    if re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", value):
        return datetime.strptime(value, '%H:%M:%S' if value.count(':') == 2 else '%H:%M').time()
    raise ValueError('Use a time such as 2:30 PM (or an existing 24-hour HH:MM value).')
