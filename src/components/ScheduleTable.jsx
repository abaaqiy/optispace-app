export default function ScheduleTable({ rows }) {
  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
      <div className="flex justify-between items-center mb-6 pb-4 border-b border-slate-100">
        <h2 className="text-lg font-bold text-slate-900">Campus Class Schedule</h2>
        <span className="bg-blue-100 text-blue-700 text-xs px-2.5 py-1 rounded-full font-bold">{rows.length} Classes</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead><tr className="bg-slate-50 text-slate-600 border-y border-slate-200">
            {['Course / Purpose', 'Room / Venue', 'Department', 'Date & Time', 'Status'].map(label => <th key={label} className="p-3">{label}</th>)}
          </tr></thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {!rows.length ? <tr><td colSpan={5} className="text-center p-6 text-slate-500">No scheduled lectures for this date.</td></tr> : rows.map(row => (
              <tr key={row.refId}>
                <td className="p-3 font-bold">{row.purpose}</td><td className="p-3 font-semibold text-blue-600">{row.roomName}</td>
                <td className="p-3">{row.organizer}</td><td className="p-3 font-mono">{row.date}<br />{row.timeSlot}</td>
                <td className="p-3"><span className={`px-2 py-1 rounded-full ${row.status === 'Cancelled' ? 'bg-slate-100 text-slate-700' : 'bg-emerald-100 text-emerald-800'}`}>{row.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
