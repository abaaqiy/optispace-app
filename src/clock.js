import '../backend/scheduling/static/scheduling/clock.js';

export const { format: formatClock, parse: parseClock } = globalThis.OptispaceClock;

export function lagosTimestamp(value, { date = true, seconds = false } = {}) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'Africa/Lagos', hour: 'numeric', minute: '2-digit', hour12: true,
    ...(seconds ? { second: '2-digit' } : {}),
    ...(date ? { year: 'numeric', month: 'short', day: 'numeric' } : {}),
  }).format(new Date(value));
}
