import React from 'react';

const RoomDetailsModal = ({ room, onClose, onBook, canBook = true }) => {
  if (!room) return null;

  // Helper to render facility icons nicely
  const getFacilityBadge = (facility) => {
    const facilityMap = {
      ac: { icon: 'fa-snowflake', label: 'Air Conditioning', color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
      projector: { icon: 'fa-video', label: 'Projector', color: 'text-purple-600', bg: 'bg-purple-50 border-purple-200' },
      power: { icon: 'fa-plug', label: 'Power Outlets', color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200' },
      audio: { icon: 'fa-microphone', label: 'Sound System', color: 'text-rose-600', bg: 'bg-rose-50 border-rose-200' },
      wifi: { icon: 'fa-wifi', label: 'Campus Wi-Fi', color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200' },
    };
    
    const info = facilityMap[facility] || { icon: 'fa-check', label: facility, color: 'text-slate-600', bg: 'bg-slate-50 border-slate-200' };

    return (
      <span key={facility} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold border ${info.bg} ${info.color}`}>
        <i className={`fa-solid ${info.icon}`}></i> {info.label}
      </span>
    );
  };

  return (
    <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-40 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-100">
        
        {/* Header */}
        <div className="flex justify-between items-start mb-4 pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-lg font-bold text-slate-900 mt-1">{room.name}</h3>
            <p className="text-xs text-slate-500"><i className="fa-solid fa-location-dot mr-1"></i> {room.zone}</p>
          </div>
          <button 
            onClick={onClose} 
            className="text-slate-500 hover:text-rose-600 bg-slate-100 hover:bg-rose-50 p-2 rounded-full transition-colors cursor-pointer"
          >
            <i className="fa-solid fa-xmark text-sm"></i>
          </button>
        </div>

        <div className="space-y-5 text-xs">
          
          {/* Capacity & Type Grid */}
          <div className="grid grid-cols-2 gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200">
            <div>
              <span className="text-slate-500 block mb-0.5">Total Capacity:</span>
              <span className="font-bold text-slate-800 text-sm flex items-center gap-1.5">
                <i className="fa-solid fa-chair text-slate-400"></i> {room.capacity} Seats
              </span>
            </div>
            <div>
              <span className="text-slate-500 block mb-0.5">Room Type:</span>
              <span className="font-bold text-slate-800 text-sm flex items-center gap-1.5">
                <i className="fa-solid fa-building text-slate-400"></i> {room.type}
              </span>
            </div>
          </div>

          {/* NEW SECTION: Available Facilities */}
          <div>
            <h4 className="font-bold text-slate-800 mb-2 flex items-center gap-1.5">
              <i className="fa-solid fa-list-check text-blue-500"></i> Available Facilities
            </h4>
            <div className="flex flex-wrap gap-2">
              {room.facilities && room.facilities.length > 0 ? (
                room.facilities.map(fac => getFacilityBadge(fac))
              ) : (
                <span className="text-slate-500 italic">No facilities listed for this room.</span>
              )}
            </div>
          </div>

          {/* Hourly Schedule */}
          <div>
            <h4 className="font-bold text-slate-800 mb-2 flex items-center gap-1.5">
              <i className="fa-solid fa-clock text-blue-500"></i> Today's Hourly Schedule
            </h4>
            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
              {room.hourlySchedule.map((s, idx) => (
                <div key={idx} className={`flex items-center justify-between p-2 rounded-lg text-xs ${s.occupied ? 'bg-rose-50 border border-rose-100 text-rose-900' : 'bg-emerald-50 border border-emerald-100 text-emerald-900'}`}>
                  <span className="font-mono font-semibold">{s.time}</span>
                  <span className="font-medium">{s.event}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Modal Footer Actions */}
        <div className="mt-6 pt-3 border-t border-slate-100 flex justify-end gap-3">
          <button 
            onClick={onClose}
            className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-colors cursor-pointer"
          >
            Close
          </button>
          
          {/* ONLY SHOW RESERVE BUTTON IF canBook IS TRUE */}
          {canBook && (
            <button 
              onClick={() => onBook(room)} 
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 border border-blue-700 text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center gap-2 cursor-pointer"
            >
              <i className="fa-solid fa-calendar-plus"></i> Reserve Room
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default RoomDetailsModal;