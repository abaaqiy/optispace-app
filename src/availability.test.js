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
  id: 'test-room', name: 'Test room', availabilityAt: timestamp('09:59:59'),
  statusTimeline: [
    period('00:00:00', '08:00:00', 'available'),
    period('08:00:00', '10:00:00', 'occupied', { currentSchedule: 'CSC 101' }),
    period('10:00:00', '12:00:00', 'reserved', {
      currentSchedule: 'Approved reservation', reservedUntil: timestamp('12:00:00'),
    }),
    period('12:00:00', '13:00:00', 'occupied', { currentSchedule: 'CSC 201' }),
    period('13:00:00', '23:59:59', 'available'),
  ],
};

test('a class stays occupied until an adjacent approved booking begins', () => {
  assert.equal(roomAtElapsedTime({ ...room, availabilityAt: timestamp('09:45:00') }).status, 'occupied');
  assert.equal(roomAtElapsedTime(room).status, 'occupied');
  assert.equal(roomAtElapsedTime(room, 999).currentSchedule, 'CSC 101');
  const started = roomAtElapsedTime(room, 1000);
  assert.equal(started.status, 'reserved');
  assert.equal(started.currentSchedule, 'Approved reservation');
  assert.equal(started.reservedSeconds, 7200);
});

test('reservation countdown ends at its booked end and the next class becomes occupied', () => {
  assert.equal(roomAtElapsedTime(room, 7_200_999).reservedSeconds, 1);
  const ended = roomAtElapsedTime(room, 7_201_000);
  assert.equal(ended.status, 'occupied');
  assert.equal(ended.currentSchedule, 'CSC 201');
  assert.equal(ended.reservedSeconds, null);
  assert.equal(ended.reservedUntil, null);
  assert.equal(roomAtElapsedTime({ ...room, availabilityAt: timestamp('13:00:00') }).status, 'available');
});

test('an approved booking has no early warning and releases to a free gap', () => {
  const gap = {
    ...room,
    statusTimeline: [
      period('00:00:00', '10:00:00', 'available'),
      room.statusTimeline[2],
      period('12:00:00', '23:59:59', 'available'),
    ],
  };
  assert.equal(roomAtElapsedTime({ ...gap, availabilityAt: timestamp('09:45:00') }).status, 'available');
  assert.equal(roomAtElapsedTime(gap, 1000).status, 'reserved');
  assert.equal(roomAtElapsedTime(gap, 7_201_000).status, 'available');
});

test('a selected time remains fixed while live time counts down', () => {
  const preview = { ...room, availabilityAt: timestamp('10:30:00') };
  assert.equal(roomAtElapsedTime(preview).reservedSeconds, 5400);
  assert.equal(roomAtElapsedTime(preview, 0).reservedSeconds, 5400);
  assert.equal(roomAtElapsedTime(preview, 1000).reservedSeconds, 5399);
  assert.equal(preview.availabilityAt, timestamp('10:30:00'));
});

test('back-to-back approved bookings reset the timer at the next start', () => {
  const adjacent = {
    ...room,
    statusTimeline: [room.statusTimeline[2], period('12:00:00', '13:00:00', 'reserved', {
      currentSchedule: 'Approved reservation', reservedUntil: timestamp('13:00:00'),
    })],
  };
  assert.equal(roomAtElapsedTime(adjacent, 7_200_999).reservedSeconds, 1);
  assert.equal(roomAtElapsedTime(adjacent, 7_201_000).status, 'reserved');
  assert.equal(roomAtElapsedTime(adjacent, 7_201_000).reservedSeconds, 3600);
});

test('without a school timetable, only the booked interval is Reserved', () => {
  const noTimetable = {
    ...room,
    statusTimeline: [period('00:00:00', '10:00:00', 'unknown'), room.statusTimeline[2], period('12:00:00', '23:59:59', 'unknown')],
  };
  assert.equal(roomAtElapsedTime(noTimetable).status, 'unknown');
  assert.equal(roomAtElapsedTime(noTimetable, 1000).status, 'reserved');
  assert.equal(roomAtElapsedTime(noTimetable, 7_201_000).status, 'unknown');
  const beyondTimeline = roomAtElapsedTime({ ...room, availabilityAt: '2026-11-11T00:00:00+01:00' });
  assert.equal(beyondTimeline.status, 'unknown');
  assert.equal(beyondTimeline.currentSchedule, null);
  assert.equal(beyondTimeline.reservedSeconds, null);
});

test('updated cancellation data clears the old reserved status and countdown', () => {
  const cancelled = {
    ...room, status: 'reserved', reservedUntil: timestamp('12:00:00'), reservedSeconds: 5000,
    availabilityAt: timestamp('10:30:00'),
    statusTimeline: [period('00:00:00', '23:59:59', 'available')],
  };
  assert.equal(roomAtElapsedTime(cancelled).status, 'available');
  assert.equal(roomAtElapsedTime(cancelled).reservedSeconds, null);
  assert.equal(roomAtElapsedTime(cancelled).reservedUntil, null);
});

test('supplied server offsets determine time independently of device timezone', () => {
  const utc = { ...room, availabilityAt: '2026-11-10T09:00:00Z' };
  assert.equal(roomAtElapsedTime(utc).reservedSeconds, 7200);
  assert.equal(roomAtElapsedTime(room, -1000).status, 'occupied');
  assert.equal(roomAtElapsedTime({ ...room, statusTimeline: [] }).status, 'unknown');
});

test('remaining time formats multi-hour bookings and rounds the last second up', () => {
  assert.equal(countdownLabel(7200), '02:00:00');
  assert.equal(countdownLabel(3661), '01:01:01');
  assert.equal(countdownLabel(3599), '59:59');
  assert.equal(countdownLabel(61), '01:01');
  assert.equal(countdownLabel(0.1), '00:01');
  assert.equal(countdownLabel(-1), '00:00');
  assert.equal(countdownLabel(null), '00:00');
});
