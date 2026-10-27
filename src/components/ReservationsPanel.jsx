import { useCallback, useEffect, useRef, useState } from 'react';
import { changeReservation, getReservations } from '../api';
import useLiveData from '../useLiveData';

const colours = { pending: 'bg-amber-100 text-amber-900', approved: 'bg-emerald-100 text-emerald-900', rejected: 'bg-rose-100 text-rose-900', cancelled: 'bg-slate-100 text-slate-700' };

function ReservationAction({ selection, onClose, onDone }) {
  const { row, action } = selection;
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const dialog = useRef(null);
  useEffect(() => { dialog.current.showModal(); }, []);
  const label = action[0].toUpperCase() + action.slice(1);
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError('');
    try { await changeReservation(row.refId, action, note); onDone(); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialog} onCancel={event => { event.preventDefault(); if (!busy) onClose(); }} aria-labelledby="reservation-action-title"
    className="m-auto w-[calc(100%_-_2rem)] max-w-lg rounded-2xl p-6 bg-white text-slate-800 shadow-2xl backdrop:bg-slate-950/60">
    <h3 id="reservation-action-title" className="text-lg font-bold">{label} reservation</h3>
    <p className="mt-2 text-sm">{row.roomName} · {row.date} · {row.timeSlot} (Africa/Lagos)</p>
    <p className="mt-2 break-words">{row.purpose}</p>
    {action === 'approve' && <p className="mt-3 text-sm text-amber-900 bg-amber-50 p-3 rounded-lg">Check that the school timetable is complete for this date. Approval makes the room Reserved during this slot.</p>}
    {action === 'cancel' && <p className="mt-3 text-sm">Cancelling releases any approved slot. This request remains in the history.</p>}
    <form onSubmit={submit} className="space-y-4 mt-4">
      {action !== 'cancel' && <label className="block text-sm font-semibold">Note to requester (optional)<textarea maxLength={500} value={note} onChange={e => setNote(e.target.value)} className="block border border-slate-300 rounded-lg p-2 mt-1 w-full font-normal" /></label>}
      {error && <p role="alert" className="p-3 rounded-lg bg-rose-50 text-rose-800 text-sm">{error}</p>}
      <div className="flex justify-end gap-3">
        <button type="button" disabled={busy} onClick={onClose} className="px-4 py-2 border border-slate-300 rounded-lg disabled:opacity-50">Back</button>
        <button disabled={busy} className="px-4 py-2 bg-blue-700 text-white font-semibold rounded-lg disabled:opacity-50">{busy ? 'Saving…' : `${label} reservation`}</button>
      </div>
    </form>
  </dialog>;
}

export default function ReservationsPanel({ admin = false }) {
  const [status, setStatus] = useState(admin ? 'pending' : '');
  const [selection, setSelection] = useState(null);
  const [message, setMessage] = useState('');
  const load = useCallback(options => getReservations(status, options), [status]);
  const { data, loading, refreshing, error, refresh } = useLiveData(`reservations:${status}`, load);
  return <section className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-6 space-y-4">
    <div className="flex flex-wrap justify-between items-center gap-3">
      <h2 className="text-lg font-bold">{admin ? 'Reservation requests' : 'My reservations'}</h2>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm">Status <select aria-label="Reservation status" value={status} onChange={e => setStatus(e.target.value)} className="border border-slate-300 p-2 rounded-lg ml-2">
          <option value="">All</option>{['pending', 'approved', 'rejected', 'cancelled'].map(value => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}
        </select></label>
        <button disabled={refreshing} onClick={refresh} className="px-3 py-2 border border-slate-300 rounded-lg text-sm disabled:opacity-50">{refreshing ? 'Refreshing…' : 'Refresh requests'}</button>
      </div>
    </div>
    <p className="text-sm text-slate-600">{admin ? 'Approve or reject pending requests. Overlapping classes and approved bookings are checked again when you approve.' : 'Request a room from its details. Pending requests need administrator approval. Approved bookings show the room as Reserved during their time slot.'} Changes are checked every 5 seconds.</p>
    {message && <p role="status" className="text-emerald-800 text-sm">{message}</p>}
    {loading ? <p role="status">Loading reservations…</p> : error ? <p role="alert" className="text-rose-800">{error}</p> : <div className="sm:overflow-x-auto">
      <table className="block w-full text-left text-sm sm:table">
        <thead className="hidden bg-slate-50 sm:table-header-group"><tr>{['Room / purpose', ...(admin ? ['Requested by'] : []), 'Date / time', 'Status', 'Actions'].map(label => <th key={label} className="p-3">{label}</th>)}</tr></thead>
        <tbody className="grid gap-4 sm:table-row-group sm:divide-y sm:divide-slate-100">{data?.length ? data.map(row => <tr key={row.refId} className="block rounded-xl border border-slate-200 p-3 sm:table-row sm:border-0 sm:p-0">
          <td className="block py-2 sm:table-cell sm:p-3 sm:min-w-40"><strong>{row.roomName}</strong><p className="break-words">{row.purpose}</p><small className="text-slate-500 break-all">{row.refId}</small>{row.reviewNote && <p className="text-slate-600 mt-2">Admin note: {row.reviewNote}</p>}</td>
          {admin && <td className="block py-2 sm:table-cell sm:p-3"><span className="text-xs text-slate-500 sm:hidden">Requested by: </span>{row.organizer}<small className="block text-slate-500">{row.userRole} · {row.staffId}</small></td>}
          <td className="block py-2 whitespace-nowrap sm:table-cell sm:p-3">{row.date}<p>{row.timeSlot}</p><small>Africa/Lagos</small></td>
          <td className="block py-2 sm:table-cell sm:p-3"><span className={`inline-block px-2 py-1 rounded-full text-xs font-bold ${colours[row.statusCode]}`}>{row.status}</span></td>
          <td className="block py-2 sm:table-cell sm:p-3"><div className="flex flex-wrap gap-2">
            {row.canApprove && <button onClick={() => setSelection({ row, action: 'approve' })} className="px-3 py-2 bg-emerald-700 text-white rounded-lg">Approve</button>}
            {row.canReview && <button onClick={() => setSelection({ row, action: 'reject' })} className="px-3 py-2 bg-rose-700 text-white rounded-lg">Reject</button>}
            {row.canCancel && <button onClick={() => setSelection({ row, action: 'cancel' })} className="px-3 py-2 border border-slate-300 rounded-lg">Cancel</button>}
            {!row.canCancel && !row.canReview && <span className="text-slate-500">—</span>}
          </div></td>
        </tr>) : <tr className="block sm:table-row"><td colSpan={admin ? 5 : 4} className="block sm:table-cell p-6 text-center text-slate-500">No reservations match this status.</td></tr>}</tbody>
      </table>
    </div>}
    {selection && <ReservationAction selection={selection} onClose={() => setSelection(null)} onDone={() => { setSelection(null); setMessage('Reservation updated.'); refresh(); }} />}
  </section>;
}
