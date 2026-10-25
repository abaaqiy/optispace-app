import { useState } from 'react';
import { getLagosDateTime } from '../api';

const BookingModal = ({ room, onClose, onConfirm, user }) => {
  const [purpose, setPurpose] = useState('');
  const organizer = user?.name || '';
  const [date, setDate] = useState(() => room.availabilityAt?.slice(0, 10) || getLagosDateTime().date);
  const [startTime, setStartTime] = useState('12:00');
  const [endTime, setEndTime] = useState('14:00');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setError('');
    if (startTime >= endTime) {
      setError('End time must be after start time on the same day.');
      return;
    }
    const now = getLagosDateTime();
    if (`${date} ${startTime}` <= `${now.date} ${now.time}`) {
      setError('Choose a future start time (Africa/Lagos).');
      return;
    }
    setSubmitting(true);
    try {
      await onConfirm({ roomId: room.id, purpose: purpose.trim(), date, startTime, endTime });
    } catch (error) {
      setError(error.message);
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="reservation-title" className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-start mb-4 pb-3 border-b border-slate-100">
          <h3 id="reservation-title" className="text-lg font-bold text-slate-900">Reserve {room?.name}</h3>
          <button aria-label="Close reservation form" disabled={submitting} onClick={onClose} className="text-slate-400 hover:text-slate-700 bg-slate-100 hover:bg-slate-200 p-2 rounded-full transition-colors cursor-pointer">
            <i className="fa-solid fa-xmark text-sm"></i>
          </button>
        </div>

        <p className="text-xs text-slate-600 mb-4">Times use Africa/Lagos. Choose a free period within the published timetable. Your request needs administrator approval before the room is reserved.</p>
        {error && <p role="alert" className="mb-4 p-3 rounded-lg bg-rose-50 text-rose-800 text-sm">{error}</p>}
        <form onSubmit={handleSubmit} className="text-xs">
          <fieldset disabled={submitting} className="space-y-4 disabled:opacity-70">
          <div>
            <label htmlFor="reservation-purpose" className="block font-bold text-slate-700 mb-1">Purpose / Lecture Title *</label>
            <input id="reservation-purpose" type="text" required maxLength={200} value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="e.g., Group study or CSC 201 lecture" className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-blue-500 text-slate-800" />
          </div>
          <div>
            <label htmlFor="reservation-organizer" className="block font-bold text-slate-700 mb-1">Organizer Name</label>
            <input id="reservation-organizer" type="text" value={organizer} readOnly className="w-full bg-slate-200 border border-slate-300 rounded-lg px-3 py-2.5 outline-none text-slate-600 cursor-not-allowed" title="Auto-filled based on your login" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div><label htmlFor="reservation-date" className="block font-bold text-slate-700 mb-1">Date *</label><input id="reservation-date" type="date" required min={getLagosDateTime().date} value={date} onChange={(e) => setDate(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500 text-slate-800" /></div>
            <div><label htmlFor="reservation-start" className="block font-bold text-slate-700 mb-1">Start *</label><input id="reservation-start" type="time" required value={startTime} onChange={(e) => setStartTime(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500 text-slate-800" /></div>
            <div><label htmlFor="reservation-end" className="block font-bold text-slate-700 mb-1">End *</label><input id="reservation-end" type="time" required value={endTime} onChange={(e) => setEndTime(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500 text-slate-800" /></div>
          </div>
          
          <div className="pt-4 border-t border-slate-100 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="px-5 py-2.5 border border-slate-300 text-slate-700 font-bold rounded-xl hover:bg-slate-100 transition-colors cursor-pointer">
              Cancel
            </button>
            <button type="submit" className="px-6 py-2.5 bg-blue-600 border border-blue-700 text-white font-bold rounded-xl shadow-md hover:bg-blue-700 active:scale-95 transition-all flex items-center gap-2 cursor-pointer">
              <i className="fa-solid fa-check"></i> {submitting ? 'Submitting…' : 'Submit request'}
            </button>
          </div>
          </fieldset>
        </form>
      </div>
    </div>
  );
};

export default BookingModal;
