import assert from 'node:assert/strict';
import test from 'node:test';
import { countdownLabel, roomAtElapsedTime } from './availability.js';

const timestamp = clock => `2026-11-10T${clock}+01:00`;
const period = (start, end, status, extra = {}) => ({
  start: timestamp(start), end: timestamp(end), status,
  statusText: status, currentSchedule: null, nextSchedule: null,
  reservedUntil: null, reservedSeconds: null, ...extra,
});
const room = {
  id: 'test-room', name: 'Test room', availabilityAt: timestamp('09:44:59'),
  statusTimeline: [
    period('08:00:00', '09:45:00', 'available'),
    period('09:45:00', '10:00:00', 'reserved', {
      reservedUntil: timestamp('10:00:00'), nextSchedule: '10:00 - CSC 101',
    }),
    period('10:00:00', '12:00:00', 'occupied', { currentSchedule: 'CSC 101' }),
    period('12:00:00', '18:00:00', 'available'),
  ],
};

test('live availability crosses the exact warning, lecture and coverage boundaries', () => {
  assert.equal(roomAtElapsedTime(room).status, 'available');
  const reserved = roomAtElapsedTime(room, 1000);
  assert.equal(reserved.status, 'reserved');
  assert.equal(reserved.reservedSeconds, 900);
  assert.equal(roomAtElapsedTime(room, 900_000).reservedSeconds, 1);
  const started = roomAtElapsedTime(room, 901_000);
  assert.equal(started.status, 'occupied');
  assert.equal(started.currentSchedule, 'CSC 101');
  assert.equal(started.reservedSeconds, null);
  assert.equal(roomAtElapsedTime({ ...room, availabilityAt: timestamp('12:00:00') }).status, 'available');
  const outside = roomAtElapsedTime({ ...room, availabilityAt: timestamp('18:00:00') });
  assert.equal(outside.status, 'unknown');
  assert.equal(outside.currentSchedule, null);
});

test('a selected time stays fixed when no elapsed time is supplied', () => {
  const preview = { ...room, availabilityAt: timestamp('09:50:00') };
  assert.equal(roomAtElapsedTime(preview).reservedSeconds, 600);
  assert.equal(roomAtElapsedTime(preview, 0).reservedSeconds, 600);
  assert.equal(preview.availabilityAt, timestamp('09:50:00'));
});

test('a warning can retain a current lecture and clears it at the next start', () => {
  const backToBack = {
    ...room, availabilityAt: timestamp('09:45:00'),
    statusTimeline: room.statusTimeline.map(slot => slot.status === 'reserved'
      ? { ...slot, currentSchedule: 'Previous lecture' } : slot),
  };
  assert.equal(roomAtElapsedTime(backToBack).currentSchedule, 'Previous lecture');
  assert.equal(roomAtElapsedTime(backToBack, 900_000).currentSchedule, 'CSC 101');
  assert.equal(roomAtElapsedTime(backToBack, 900_000).status, 'occupied');
});

test('no timetable stays Unknown and supplied offsets determine time', () => {
  assert.equal(roomAtElapsedTime({ ...room, statusTimeline: [] }).status, 'unknown');
  const utc = { ...room, availabilityAt: '2026-11-10T08:45:00Z' };
  assert.equal(roomAtElapsedTime(utc).reservedSeconds, 900);
  assert.equal(roomAtElapsedTime(room, -1000).status, 'available');
});

test('countdown never displays zero before the lecture starts', () => {
  assert.equal(roomAtElapsedTime(room, 900_999).reservedSeconds, 1);
  assert.equal(countdownLabel(900), '15:00');
  assert.equal(countdownLabel(61), '01:01');
  assert.equal(countdownLabel(0.1), '00:01');
  assert.equal(countdownLabel(-1), '00:00');
  assert.equal(countdownLabel(null), '00:00');
});
