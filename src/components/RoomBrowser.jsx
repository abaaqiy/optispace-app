import { useEffect, useState } from 'react';
import { getRoomFilterOptions, getRooms } from '../api';
import RoomGrid from './RoomGrid';
import SearchFilters from './SearchFilters';

const emptyFilters = { zone: '', capacity: '', facilities: [], status: '' };

export default function RoomBrowser({ category, onOpenDetails, children }) {
  const [filters, setFilters] = useState(emptyFilters);
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState(null);
  const [options, setOptions] = useState({ zones: [] });
  const requestKey = JSON.stringify({ filters, category, revision });

  useEffect(() => {
    const timer = setInterval(() => setRevision(value => value + 1), 60000);
    const refreshOnFocus = () => setRevision(value => value + 1);
    window.addEventListener('focus', refreshOnFocus);
    return () => {
      clearInterval(timer);
      window.removeEventListener('focus', refreshOnFocus);
    };
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    getRooms({ ...filters, category }, { signal: controller.signal }).then(rooms => {
      if (active) setResult({ key: requestKey, rooms, error: '' });
    }).catch(error => {
      if (active) setResult({ key: requestKey, rooms: [], error: error.message });
    });
    // Refresh options too, so newly added buildings appear without signing in again.
    getRoomFilterOptions({ signal: controller.signal }).then(data => {
      if (active) setOptions(data);
    }).catch(() => {});
    return () => { active = false; controller.abort(); };
  }, [filters, category, requestKey]);

  const loading = result?.key !== requestKey;
  const rooms = loading ? [] : result.rooms;
  const error = loading ? '' : result.error;
  const moment = rooms[0]?.availabilityAt;
  const momentLabel = moment ? new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Lagos', dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(moment)) : (filters.date ? `${filters.date} ${filters.time}` : 'Current time');

  return (
    <section className="space-y-5" aria-busy={loading}>
      <SearchFilters
        onApply={setFilters} onReset={() => setFilters(emptyFilters)}
        zones={options.zones} activeCategory={category || 'all'}
      />
      <div className="flex flex-wrap justify-between items-center gap-3 text-xs text-slate-600">
        <div>
          <p className="font-semibold">Availability: {momentLabel} (Africa/Lagos)</p>
          <p>Based on published timetables. Unscheduled physical use may differ. Updates every minute.</p>
        </div>
        <button onClick={() => setRevision(value => value + 1)} className="px-3 py-2 rounded-lg bg-white border border-slate-300 font-semibold">Refresh rooms</button>
      </div>
      {loading ? (
        <p role="status" className="bg-white p-8 rounded-xl text-center">Loading room availability…</p>
      ) : error ? (
        <div role="alert" className="bg-rose-50 border border-rose-200 p-5 rounded-xl text-rose-800">
          <p>{error}</p>
          <button onClick={() => setRevision(value => value + 1)} className="mt-3 underline font-bold">Retry loading rooms</button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            {[
              ['Matching rooms', rooms.length],
              ['Available', rooms.filter(room => ['available', 'soon'].includes(room.status)).length],
              ['Occupied', rooms.filter(room => room.status === 'occupied').length],
              ['Unknown', rooms.filter(room => room.status === 'unknown').length],
            ].map(([label, count]) => (
              <div key={label} className="bg-white border border-slate-200 rounded-xl p-3">
                <span className="text-slate-500">{label}</span><strong className="block text-xl">{count}</strong>
              </div>
            ))}
          </div>
          {children ? children(rooms) : <RoomGrid rooms={rooms} onOpenDetails={onOpenDetails} canBook={false} />}
        </>
      )}
    </section>
  );
}
