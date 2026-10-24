import { useState } from 'react';

const BookingModal = ({ room, onClose, onConfirm, user }) => {
  const [purpose, setPurpose] = useState('');
  const organizer = user?.name || '';
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [startTime, setStartTime] = useState('12:00');
  const [endTime, setEndTime] = useState('14:00');

  const handleSubmit = (e) => {
    e.preventDefault();
    onConfirm({
      roomId: room.id,
      roomName: room.name,
      purpose,
      organizer: user ? user.name : organizer, // Force the logged-in user's name
      staffId: user ? user.id : "USER/ID/001", // Force the logged-in user's ID
      date,
      timeSlot: `${startTime} - ${endTime}`,
    });
  };

  return (
    <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-100">
        <div className="flex justify-between items-start mb-4 pb-3 border-b border-slate-100">
          <h3 className="text-lg font-bold text-slate-900">Reserve {room?.name}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 bg-slate-100 hover:bg-slate-200 p-2 rounded-full transition-colors cursor-pointer">
            <i className="fa-solid fa-xmark text-sm"></i>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block font-bold text-slate-700 mb-1">Purpose / Lecture Title *</label>
            <input type="text" required value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="e.g., CSC 201 Lecture" className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-blue-500 text-slate-800" />
          </div>
          <div>
            <label className="block font-bold text-slate-700 mb-1">Organizer Name *</label>
            <input type="text" required value={organizer} readOnly className="w-full bg-slate-200 border border-slate-300 rounded-lg px-3 py-2.5 outline-none text-slate-600 cursor-not-allowed" title="Auto-filled based on your login" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><label className="block font-bold text-slate-700 mb-1">Date *</label><input type="date" required value={date} onChange={(e) => setDate(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500 text-slate-800" /></div>
            <div><label className="block font-bold text-slate-700 mb-1">Start *</label><input type="time" required value={startTime} onChange={(e) => setStartTime(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500 text-slate-800" /></div>
            <div><label className="block font-bold text-slate-700 mb-1">End *</label><input type="time" required value={endTime} onChange={(e) => setEndTime(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500 text-slate-800" /></div>
          </div>
          
          <div className="pt-4 border-t border-slate-100 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="px-5 py-2.5 border border-slate-300 text-slate-700 font-bold rounded-xl hover:bg-slate-100 transition-colors cursor-pointer">
              Cancel
            </button>
            <button type="submit" className="px-6 py-2.5 bg-blue-600 border border-blue-700 text-white font-bold rounded-xl shadow-md hover:bg-blue-700 active:scale-95 transition-all flex items-center gap-2 cursor-pointer">
              <i className="fa-solid fa-check"></i> Confirm
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default BookingModal;
