const getStatusBadge = (status) => {
  switch(status) {
    case 'available': return <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2.5 py-0.5 rounded-full"><span className="w-1.5 h-1.5 rounded-full bg-emerald-600"></span> Available</span>;
    case 'soon': return <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 text-[10px] font-bold px-2.5 py-0.5 rounded-full"><span className="w-1.5 h-1.5 rounded-full bg-amber-600"></span> Occupied Soon</span>;
    case 'occupied': return <span className="inline-flex items-center gap-1 bg-rose-100 text-rose-800 text-[10px] font-bold px-2.5 py-0.5 rounded-full"><span className="w-1.5 h-1.5 rounded-full bg-rose-600"></span> In Session</span>;
    case 'reserved': return <span className="inline-flex items-center gap-1 bg-indigo-100 text-indigo-800 text-[10px] font-bold px-2.5 py-0.5 rounded-full"><span className="w-1.5 h-1.5 rounded-full bg-indigo-600"></span> Reserved</span>;
    default: return <span className="bg-slate-100 text-slate-700 text-[10px] font-bold px-2.5 py-0.5 rounded-full">Unknown</span>;
  }
};

const RoomGrid = ({ rooms, onOpenDetails, onQuickBook, canBook = true }) => {
  if (rooms.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center my-6">
        <h4 className="text-base font-bold text-slate-800">No Rooms Match Your Criteria</h4>
        <p className="text-xs text-slate-500 mt-1">Try resetting your filters. Rooms appear here after an administrator adds them.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {rooms.map(room => (
        <div key={room.id} className="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-all flex flex-col justify-between overflow-hidden">
          <div className="p-5">
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">{room.zone}</span>
                <h4 className="font-bold text-slate-900 text-base leading-snug">{room.name}</h4>
              </div>
              {getStatusBadge(room.status)}
            </div>
            <p className="text-xs text-slate-500 mb-4"><i className="fa-solid fa-chair text-slate-400 mr-1"></i> {room.capacity} Capacity • {room.type}</p>
            {room.building && <p className="text-xs text-slate-500 mb-3">{room.building.name}{room.roomNumber ? ` · ${room.roomNumber}` : ''}</p>}
            
            <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 text-xs space-y-1">
              <div className="flex items-center gap-1.5 font-medium text-slate-800">
                <i className="fa-solid fa-clock text-slate-400"></i> {room.statusText}
              </div>
              {room.nextSchedule && <div className="text-[11px] text-slate-500 pl-4">Next: {room.nextSchedule}</div>}
            </div>
          </div>

          {/* Card Buttons */}
          <div className="bg-slate-50 px-5 py-3 border-t border-slate-200 flex items-center justify-between gap-2">
            <button 
              onClick={() => onOpenDetails(room)} 
              className="px-3 py-2 text-xs font-bold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-100 transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
            >
              <i className="fa-solid fa-circle-info"></i> Details
            </button>
            
            {/* Only show Book button if canBook is true */}
            {canBook && (
              <button 
                onClick={() => onQuickBook(room)} 
                className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 border border-blue-700 rounded-lg shadow-sm transition-all flex items-center gap-1.5 cursor-pointer"
              >
                <i className="fa-solid fa-calendar-plus"></i> Book
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
export default RoomGrid;
