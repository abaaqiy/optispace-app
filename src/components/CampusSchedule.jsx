import { useEffect, useState } from 'react';
import { getCampusSchedule, getLagosDateTime } from '../api';
import BookingsTable from './BookingsTable';

export default function CampusSchedule() {
  const [date, setDate] = useState(() => getLagosDateTime().date);
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState(null);
  const key = `${date}:${revision}`;

  useEffect(() => {
    let active = true;
    getCampusSchedule(date).then(rows => {
      if (active) setResult({ key, rows });
    }).catch(error => {
      if (active) setResult({ key, error: error.message });
    });
    return () => { active = false; };
  }, [date, key]);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <label className="text-sm font-semibold">Schedule date (Lagos)
          <input aria-label="Schedule date" type="date" required value={date} onChange={event => {
            if (event.target.value) setDate(event.target.value);
          }} className="ml-3 p-2 border rounded-lg bg-white" />
        </label>
        <button onClick={() => setRevision(value => value + 1)} className="text-sm font-semibold text-blue-700 underline">Refresh schedule</button>
      </div>
      {result?.key !== key ? <p role="status">Loading schedule…</p> : result.error ? (
        <p role="alert" className="text-rose-700">{result.error}</p>
      ) : <BookingsTable bookings={result.rows} readOnly />}
    </section>
  );
}
