import { useCallback, useEffect, useState } from 'react';
import { getRoomFilterOptions, getRooms } from '../api';
import { roomAtElapsedTime } from '../availability';
import RoomGrid from './RoomGrid';
import RoomDetailsModal from './RoomDetailsModal';
import SearchFilters from './SearchFilters';
import useLiveData from '../useLiveData';

const emptyFilters = { zone: '', capacity: '', facilities: [], status: '' };

export default function RoomBrowser({ category, children }) {
  const [filters, setFilters] = useState(emptyFilters);
  const [options, setOptions] = useState({ zones: [] });
  const [clock, setClock] = useState(() => performance.now());
  const [selectedId, setSelectedId] = useState(null);
  const requestKey = JSON.stringify({ filters, category });
  const loadRooms = useCallback(options => getRooms({ ...filters, category, status: '' }, options), [filters, category]);
  const { data, error, receivedAt, updatedAt, loading, refreshing, refresh } = useLiveData(requestKey, loadRooms);

  useEffect(() => {
    const tick = setInterval(() => setClock(performance.now()), 1000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    getRoomFilterOptions({ signal: controller.signal }).then(data => {
      if (active) setOptions(data);
    }).catch(() => {});
    return () => { active = false; controller.abort(); };
  }, [updatedAt]);

  const elapsed = filters.date ? 0 : Math.max(0, clock - (receivedAt || clock));
  const allRooms = (data || []).map(room => roomAtElapsedTime(room, elapsed));
  const rooms = allRooms.filter(room => !filters.status || filters.status === 'all' || room.status === filters.status);
  const selectedRoom = allRooms.find(room => room.id === selectedId);
  const moment = allRooms[0]?.availabilityAt;
  const momentLabel = moment ? new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Lagos', dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(moment)) : (filters.date ? `${filters.date} ${filters.time}` : 'Current time');
  const openDetails = room => setSelectedId(room.id);

  return (
    <section className="space-y-5" aria-busy={refreshing}>
      <SearchFilters onApply={setFilters} onReset={() => setFilters(emptyFilters)} zones={options.zones} activeCategory={category || 'all'} />
      <div className="flex flex-wrap justify-between items-center gap-3 text-xs text-slate-600">
        <div>
          <p className="font-semibold">Availability: {momentLabel} (Africa/Lagos)</p>
          <p>Availability follows the school timetable. Changes are checked every 5 seconds. Reserved applies only to seminar rooms/halls and event halls, for the 15 minutes before a scheduled session.</p>
          {filters.date && <p>Showing the selected date and time; this countdown is a fixed preview.</p>}
        </div>
        <div className="flex items-center gap-3">
          <p role="status">{refreshing ? 'Refreshing room availability…' : error ? 'Refresh failed. Retrying automatically.' : updatedAt ? `Rooms updated at ${new Date(updatedAt).toLocaleTimeString('en-GB', { timeZone: 'Africa/Lagos' })}` : ''}</p>
          <button type="button" onClick={refresh} disabled={refreshing} className="px-3 py-2 rounded-lg bg-white border border-slate-300 font-semibold disabled:opacity-50">{refreshing ? 'Refreshing…' : 'Refresh rooms'}</button>
        </div>
      </div>
      {loading ? (
        <p role="status" className="bg-white p-8 rounded-xl text-center">Loading room availability…</p>
      ) : error ? (
        <div role="alert" className="bg-rose-50 border border-rose-200 p-5 rounded-xl text-rose-800">
          <p>{error}</p>
          <button onClick={refresh} disabled={refreshing} className="mt-3 underline font-bold">Retry loading rooms</button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
            {[
              ['Matching rooms', rooms.length],
              ['Available', rooms.filter(room => room.status === 'available').length],
              ['Occupied', rooms.filter(room => room.status === 'occupied').length],
              ['Reserved', rooms.filter(room => room.status === 'reserved').length],
              ['Unknown', rooms.filter(room => room.status === 'unknown').length],
            ].map(([label, count]) => (
              <div key={label} className="bg-white border border-slate-200 rounded-xl p-3">
                <span className="text-slate-500">{label}</span><strong className="block text-xl">{count}</strong>
              </div>
            ))}
          </div>
          {children ? children(rooms, openDetails) : <RoomGrid rooms={rooms} onOpenDetails={openDetails} />}
        </>
      )}
      {selectedRoom && <RoomDetailsModal room={selectedRoom} onClose={() => setSelectedId(null)} />}
    </section>
  );
}
