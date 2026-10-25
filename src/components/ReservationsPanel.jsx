import { useEffect, useState } from 'react';
import { getReservations, updateReservation } from '../api';
import BookingsTable from './BookingsTable';

export default function ReservationsPanel({ admin = false, onChanged }) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState(null);
  const [action, setAction] = useState(null);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState(admin ? 'pending' : 'all');

  useEffect(() => {
    const refresh = () => setRevision(value => value + 1);
    const timer = setInterval(refresh, 60000);
    window.addEventListener('focus', refresh);
    return () => { clearInterval(timer); window.removeEventListener('focus', refresh); };
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    getReservations({ signal: controller.signal }).then(rows => {
      if (active) setResult({ revision, rows });
    }).catch(error => {
      if (active) setResult({ revision, error: error.message });
    });
    return () => { active = false; controller.abort(); };
  }, [revision]);

  const selectAction = (booking, kind) => {
    setAction({ booking, kind });
    setNote('');
    setError('');
    setMessage('');
  };

  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const updated = await updateReservation(action.booking.refId, action.kind, note);
      setAction(null);
      setMessage(`Reservation ${updated.status.toLowerCase()}.`);
      setRevision(value => value + 1);
      onChanged?.();
    } catch (error) {
      setError(error.message);
      setRevision(value => value + 1);
    } finally {
      setBusy(false);
    }
  };

  const loading = result?.revision !== revision;
  const rows = (result?.rows || []).filter(row => status === 'all' || row.statusCode === status);
  const verb = action ? { approve: 'Approve', reject: 'Reject', cancel: 'Cancel' }[action.kind] : '';

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center justify-between">
        <label className="text-sm font-semibold">Reservation status
          <select aria-label="Reservation status" value={status} onChange={e => setStatus(e.target.value)} className="ml-2 border rounded-lg bg-white p-2">
            <option value="all">All statuses</option>
            {['pending', 'approved', 'rejected', 'cancelled'].map(value => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}
          </select>
        </label>
        <button onClick={() => setRevision(value => value + 1)} className="text-sm text-blue-700 font-semibold underline">Refresh reservations</button>
      </div>
      {message && <p role="status" className="text-emerald-800 bg-emerald-50 p-3 rounded-lg">{message}</p>}
      {loading ? <p role="status">Loading reservations…</p> : result.error ? <p role="alert" className="text-rose-800">{result.error}</p> : (
        <BookingsTable bookings={rows} admin={admin}
          onCancel={booking => selectAction(booking, 'cancel')}
          onApprove={booking => selectAction(booking, 'approve')}
          onReject={booking => selectAction(booking, 'reject')} />
      )}
      {action && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 flex items-center justify-center p-4">
          <form onSubmit={submit} role="dialog" aria-modal="true" aria-labelledby="reservation-action-title" className="bg-white w-full max-w-lg p-6 rounded-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <h3 id="reservation-action-title" className="font-bold text-lg">{verb} reservation</h3>
            <p className="text-sm">{action.booking.purpose} — {action.booking.roomName}<br />{action.booking.date}, {action.booking.timeSlot} (Lagos)</p>
            <p className="text-sm text-slate-600">{action.kind === 'approve' ? 'The room will be reserved if the time is still free.' : action.kind === 'reject' ? 'The requester will see the rejection and any note you add.' : 'This ends the request and releases any time it reserved.'}</p>
            {action.kind !== 'cancel' && <label className="block text-sm">Note for requester (optional)
              <textarea aria-label="Note for requester" maxLength={500} disabled={busy} value={note} onChange={e => setNote(e.target.value)} className="block w-full border rounded-lg p-2 mt-1" />
            </label>}
            {error && <p role="alert" className="text-rose-800 bg-rose-50 p-3 rounded-lg">{error}</p>}
            <div className="flex justify-end gap-3">
              <button type="button" disabled={busy} onClick={() => setAction(null)} className="px-4 py-2 rounded-lg border">Go back</button>
              <button type="submit" disabled={busy} className="px-4 py-2 rounded-lg bg-blue-700 text-white disabled:opacity-50">{busy ? 'Saving…' : `${verb} reservation`}</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
