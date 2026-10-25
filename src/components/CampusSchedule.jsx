import { useCallback, useState } from 'react';
import { getCampusSchedule, getLagosDateTime } from '../api';
import ScheduleTable from './ScheduleTable';
import useLiveData from '../useLiveData';

export default function CampusSchedule() {
  const [date, setDate] = useState(() => getLagosDateTime().date);
  const loadSchedule = useCallback(options => getCampusSchedule(date, options), [date]);
  const { data, error, loading, refreshing, refresh } = useLiveData(date, loadSchedule);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <label className="text-sm font-semibold">Schedule date (Lagos)
          <input aria-label="Schedule date" type="date" required value={date} onChange={event => {
            if (event.target.value) setDate(event.target.value);
          }} className="ml-3 p-2 border rounded-lg bg-white" />
        </label>
        <button type="button" onClick={refresh} disabled={refreshing} className="text-sm font-semibold text-blue-700 underline disabled:opacity-50">{refreshing ? 'Refreshing…' : 'Refresh schedule'}</button>
      </div>
      <p className="text-xs text-slate-600">Timetable changes and cancellations are checked every 5 seconds.</p>
      {loading ? <p role="status">Loading schedule…</p> : error ? (
        <p role="alert" className="text-rose-700">{error} Retrying automatically.</p>
      ) : <ScheduleTable rows={data || []} />}
    </section>
  );
}
