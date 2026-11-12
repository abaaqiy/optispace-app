import assert from 'node:assert/strict';
import test from 'node:test';
import { formatClock, parseClock, lagosTimestamp } from './clock.js';

test('AM/PM conversion preserves noon midnight and every minute of the day', () => {
  for (let hour = 0; hour < 24; hour++) for (let minute = 0; minute < 60; minute++) {
    const value = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
    assert.equal(parseClock(formatClock(value)), value);
  }
  assert.equal(formatClock('00:00'), '12:00 AM');
  assert.equal(formatClock('12:00'), '12:00 PM');
  assert.equal(formatClock('14:30'), '2:30 PM');
  for (const value of ['13:00 PM', '00:00 AM', '1:60 AM', '2:30', '14:00', '12:00 XM']) assert.equal(parseClock(value), '');
  assert.equal(parseClock(' 2:30pm '), '14:30');
});

test('display uses Lagos independently of supplied UTC offset', () => {
  assert.match(lagosTimestamp('2030-01-01T13:30:00Z'), /2:30 PM/);
  assert.match(lagosTimestamp('2030-01-01T23:00:00Z'), /Jan 2, 2030.*12:00 AM/);
});
