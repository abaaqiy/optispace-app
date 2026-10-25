const BookingsTable = ({ bookings, onCancel, onApprove, onReject, admin = false, readOnly = false }) => {
  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
      <div className="flex justify-between items-center mb-6 pb-4 border-b border-slate-100">
        <h2 className="text-lg font-bold text-slate-900">
          <i className={`fa-solid ${readOnly ? 'fa-calendar-alt' : 'fa-calendar-days'} text-blue-600 mr-2`}></i> 
          {readOnly ? 'Campus Class Schedule' : admin ? 'Reservation Requests' : 'My Reservations'}
        </h2>
        <span className="bg-blue-100 text-blue-700 text-xs px-2.5 py-1 rounded-full font-bold">
          {bookings.length} {readOnly ? 'Classes' : 'Reservations'}
        </span>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-50 text-slate-600 font-bold border-y border-slate-200">
              <th className="p-3">Course / Purpose</th>
              <th className="p-3">Room / Venue</th>
              <th className="p-3">Department / Organizer</th>
              <th className="p-3">Date & Time</th>
              <th className="p-3">Status</th>
              {!readOnly && <th className="p-3 text-right">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {bookings.length === 0 ? (
              <tr>
                <td colSpan={readOnly ? 5 : 6} className="text-center p-6 text-slate-500">
                  {readOnly ? 'No published lectures for this date.' : 'No reservations to display.'}
                </td>
              </tr>
            ) : (
              bookings.map(b => (
                <tr key={b.refId} className="hover:bg-slate-50">
                  <td className="p-3">
                    <span className="font-bold text-slate-800 block">{b.purpose}</span>
                    <span className="text-[10px] text-slate-400 font-mono">{b.refId}</span>
                  </td>
                  <td className="p-3 font-semibold text-blue-600">{b.roomName}</td>
                  <td className="p-3">
                    <span className="block font-medium">{b.organizer}</span>
                    <span className="text-[10px] text-slate-400">{b.staffId}</span>
                  </td>
                  <td className="p-3 font-mono">
                    {b.date} <br/>
                    <span className="text-[10px] text-slate-400">{b.timeSlot}</span>
                  </td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${b.isApproved ? 'bg-emerald-100 text-emerald-800' : b.statusCode === 'rejected' ? 'bg-rose-100 text-rose-800' : b.statusCode === 'cancelled' ? 'bg-slate-100 text-slate-700' : 'bg-amber-100 text-amber-800'}`}>
                      {b.status || (b.isApproved ? 'Approved' : 'Pending')}
                    </span>
                    {b.reviewNote && <p className="mt-2 text-xs max-w-xs whitespace-pre-wrap">{b.reviewNote}</p>}
                  </td>
                  {!readOnly && (
                    <td className="p-3 text-right">
                      <div className="flex flex-wrap justify-end gap-3">
                        {admin && b.canReview && <>
                          {b.canApprove && <button onClick={() => onApprove(b)} className="text-emerald-700 font-bold">Approve</button>}
                          <button onClick={() => onReject(b)} className="text-rose-700 font-bold">Reject</button>
                        </>}
                        {b.canCancel && <button onClick={() => onCancel(b)} className="text-rose-700 font-bold">Cancel</button>}
                      </div>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default BookingsTable;
