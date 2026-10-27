import { useEffect, useRef, useState } from 'react';
import { getLagosDateTime, requestReservation } from '../api';

export default function BookingModal({ room, onClose, onSuccess }) {
  const [date, setDate] = useState(() => room.availabilityAt?.slice(0, 10) || getLagosDateTime().date);
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [purpose, setPurpose] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const dialog = useRef(null);
  useEffect(() => { dialog.current.showModal(); }, []);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    if (endTime <= startTime) { setError('End time must be after start time on the same date.'); return; }
    setBusy(true); setError('');
    try {
      await requestReservation({ roomId: room.id, date, startTime, endTime, purpose });
      onSuccess('Your request was sent. It will hold the room only after administrator approval.');
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }

  return (
    <dialog ref={dialog} onCancel={event => { event.preventDefault(); if (!busy) onClose(); }} aria-labelledby="booking-title"
      className="m-auto w-[calc(100%_-_2rem)] max-w-lg rounded-2xl p-6 text-slate-800 bg-white shadow-2xl backdrop:bg-slate-950/60">
      <h2 id="booking-title" className="text-lg font-bold">Request {room.name}</h2>
      <p className="text-sm text-slate-600 mt-2">Choose a future slot in Africa/Lagos time. Administrators check requests against classes and approved reservations.</p>
      <p className="mt-3 text-sm text-amber-800 bg-amber-50 p-3 rounded-lg">A request does not hold the room until an administrator approves it.</p>
      <form onSubmit={submit} className="mt-5 space-y-4">
        <label className="block text-sm font-semibold">Purpose
          <input required maxLength={200} value={purpose} onChange={e => setPurpose(e.target.value)} placeholder="e.g. Group study or departmental meeting"
            className="block w-full border border-slate-300 rounded-lg p-2 mt-1 font-normal" />
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label className="text-sm font-semibold">Date<input required type="date" min={getLagosDateTime().date} value={date} onChange={e => setDate(e.target.value)} className="block w-full border border-slate-300 rounded-lg p-2 mt-1" /></label>
          <label className="text-sm font-semibold">Start time<input required type="time" value={startTime} onChange={e => setStartTime(e.target.value)} className="block w-full border border-slate-300 rounded-lg p-2 mt-1" /></label>
          <label className="text-sm font-semibold">End time<input required type="time" value={endTime} onChange={e => setEndTime(e.target.value)} className="block w-full border border-slate-300 rounded-lg p-2 mt-1" /></label>
        </div>
        {error && <p role="alert" className="text-sm text-rose-800 bg-rose-50 p-3 rounded-lg">{error}</p>}
        <div className="flex justify-end gap-3 pt-3">
          <button type="button" disabled={busy} onClick={onClose} className="border border-slate-300 rounded-lg px-4 py-2 disabled:opacity-50">Close</button>
          <button disabled={busy} className="bg-blue-700 text-white rounded-lg px-4 py-2 font-semibold disabled:opacity-50">{busy ? 'Submitting…' : 'Submit request'}</button>
        </div>
      </form>
    </dialog>
  );
}
