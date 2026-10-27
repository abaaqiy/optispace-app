// Advance through classes and bookings using elapsed time, not the device's timezone.
export function roomAtElapsedTime(room, elapsedMs = 0) {
  const at = Date.parse(room.availabilityAt) + Math.max(0, elapsedMs);
  if (!Number.isFinite(at)) return room;
  const period = room.statusTimeline?.find(slot => Date.parse(slot.start) <= at && at < Date.parse(slot.end));
  if (!period) return {
    ...room, availabilityAt: new Date(at).toISOString(), status: 'unknown',
    statusText: room.statusTimeline?.length ? 'Waiting for the timetable for this date' : room.statusText,
    reservedUntil: null, reservedSeconds: null, currentSchedule: null, nextSchedule: null,
  };
  return {
    ...room, ...period, availabilityAt: new Date(at).toISOString(),
    reservedSeconds: period.status === 'reserved' && period.reservedUntil ? Math.max(0, Math.ceil((Date.parse(period.reservedUntil) - at) / 1000)) : null,
  };
}

export function countdownLabel(seconds) {
  const whole = Math.max(0, Math.ceil(seconds || 0));
  const pad = value => String(value).padStart(2, '0');
  const minutes = `${pad(Math.floor(whole / 60) % 60)}:${pad(whole % 60)}`;
  return whole >= 3600 ? `${pad(Math.floor(whole / 3600))}:${minutes}` : minutes;
}
