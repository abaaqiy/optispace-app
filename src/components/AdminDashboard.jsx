import React, { useState } from 'react';

const AdminDashboard = ({ rooms, setRooms, bookings, setBookings, showToast }) => {
  // --- STATE FOR NEW ROOM FORM ---
  const [newRoom, setNewRoom] = useState({
    name: '', zone: 'Faculty of Computing & Engineering', type: 'Lecture Theatre', capacity: 100
  });
  const [newRoomFacilities, setNewRoomFacilities] = useState([]);

  // --- STATE FOR MANAGING EXISTING ROOM FACILITIES ---
  const [selectedRoomId, setSelectedRoomId] = useState(rooms.length > 0 ? rooms[0].id : '');

  const availableFacilities = ['ac', 'projector', 'power', 'audio', 'wifi'];

  // --- HANDLERS: APPROVE/REJECT BOOKINGS ---
  const handleApprove = (refId) => {
    setBookings(bookings.map(b => 
      b.refId === refId ? { ...b, isApproved: true, status: 'Approved' } : b
    ));
    showToast(`Booking ${refId} approved!`);
  };

  const handleReject = (refId) => {
    setBookings(bookings.filter(b => b.refId !== refId));
    showToast(`Booking ${refId} rejected and removed.`);
  };

  // --- HANDLERS: TOGGLE ROOM STATUS ---
  const toggleRoomStatus = (roomId) => {
    setRooms(rooms.map(r => {
      if (r.id === roomId) {
        const newStatus = r.status === 'available' ? 'occupied' : 'available';
        return { 
          ...r, 
          status: newStatus, 
          statusText: newStatus === 'available' ? 'Available Now' : 'Occupied: Manual Override' 
        };
      }
      return r;
    }));
    showToast("Room status updated.");
  };

  // --- HANDLERS: ADD NEW ROOM ---
  const handleAddRoom = (e) => {
    e.preventDefault();
    const room = {
      id: `room-${Date.now()}`,
      ...newRoom,
      status: 'available',
      statusText: 'Available Now',
      facilities: newRoomFacilities,
      currentSchedule: null,
      nextSchedule: 'No scheduled lectures',
      hourlySchedule: [{ time: "08:00 - 18:00", event: "Vacant / Free Slot", occupied: false }]
    };

    setRooms([...rooms, room]);
    setNewRoom({ name: '', zone: 'Faculty of Computing & Engineering', type: 'Lecture Theatre', capacity: 100 });
    setNewRoomFacilities([]);
    showToast("New lecture theatre added successfully!");
  };

  const toggleNewFacility = (fac) => {
    setNewRoomFacilities(prev => 
      prev.includes(fac) ? prev.filter(f => f !== fac) : [...prev, fac]
    );
  };

  // --- HANDLERS: MANAGE EXISTING ROOM FACILITIES ---
  const selectedRoom = rooms.find(r => r.id === selectedRoomId);

  const toggleExistingFacility = (fac) => {
    if (!selectedRoom) return;

    const hasFacility = selectedRoom.facilities.includes(fac);
    let updatedFacilities;

    if (hasFacility) {
      // Remove facility
      updatedFacilities = selectedRoom.facilities.filter(f => f !== fac);
      showToast(`Removed ${fac.toUpperCase()} from ${selectedRoom.name}`);
    } else {
      // Add facility
      updatedFacilities = [...selectedRoom.facilities, fac];
      showToast(`Added ${fac.toUpperCase()} to ${selectedRoom.name}`);
    }

    // Update the rooms state
    setRooms(rooms.map(r => 
      r.id === selectedRoom.id ? { ...r, facilities: updatedFacilities } : r
    ));
  };

  return (
    <div className="space-y-6">
      
      {/* 1. BOOKING APPROVALS */}
      <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 mb-4 pb-3 border-b border-slate-100">
          <i className="fa-solid fa-clipboard-check text-blue-600 mr-2"></i> Pending Booking Approvals
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 text-slate-600 font-bold border-y border-slate-200">
                <th className="p-3">Ref ID</th>
                <th className="p-3">Room</th>
                <th className="p-3">Organizer</th>
                <th className="p-3">Time Slot</th>
                <th className="p-3">Status</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {bookings.length === 0 ? (
                <tr><td colSpan="6" className="text-center p-4 text-slate-500">No active bookings.</td></tr>
              ) : (
                bookings.map(b => (
                  <tr key={b.refId} className="hover:bg-slate-50">
                    <td className="p-3 font-mono font-bold text-blue-600">{b.refId}</td>
                    <td className="p-3 font-semibold">{b.roomName}</td>
                    <td className="p-3">{b.organizer}</td>
                    <td className="p-3 font-mono">{b.date} <br/><span className="text-[10px] text-slate-400">{b.timeSlot}</span></td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${b.isApproved ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                        {b.isApproved ? 'Approved' : 'Pending'}
                      </span>
                    </td>
                    <td className="p-3 text-right space-x-2">
                      {!b.isApproved && (
                        <button onClick={() => handleApprove(b.refId)} className="px-3 py-1 bg-emerald-500 hover:bg-emerald-600 text-white rounded-md font-bold transition-colors cursor-pointer">
                          <i className="fa-solid fa-check mr-1"></i> Approve
                        </button>
                      )}
                      <button onClick={() => handleReject(b.refId)} className="px-3 py-1 bg-rose-500 hover:bg-rose-600 text-white rounded-md font-bold transition-colors cursor-pointer">
                        <i className="fa-solid fa-xmark mr-1"></i> Reject
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* 2. TOGGLE ROOM STATUS */}
        <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900 mb-4 pb-3 border-b border-slate-100">
            <i className="fa-solid fa-toggle-on text-blue-600 mr-2"></i> Manual Status Override
          </h2>
          <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
            {rooms.map(room => (
              <div key={room.id} className="flex items-center justify-between p-3 border border-slate-200 rounded-xl bg-slate-50">
                <div>
                  <p className="font-bold text-sm text-slate-800">{room.name}</p>
                  <p className="text-[10px] text-slate-500">{room.zone}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${room.status === 'available' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                    {room.status.toUpperCase()}
                  </span>
                  <button 
                    onClick={() => toggleRoomStatus(room.id)}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white text-xs font-bold rounded-lg transition-colors cursor-pointer"
                  >
                    Toggle
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 3. ADD NEW ROOM */}
        <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900 mb-4 pb-3 border-b border-slate-100">
            <i className="fa-solid fa-plus-circle text-blue-600 mr-2"></i> Add New Lecture Theatre
          </h2>
          <form onSubmit={handleAddRoom} className="space-y-4 text-xs">
            <div>
              <label className="block font-bold text-slate-700 mb-1">Room Name</label>
              <input type="text" required value={newRoom.name} onChange={(e) => setNewRoom({...newRoom, name: e.target.value})} placeholder="e.g., New ICT Hall" className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Zone</label>
                <select value={newRoom.zone} onChange={(e) => setNewRoom({...newRoom, zone: e.target.value})} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2.5 outline-none">
                  <option value="Faculty of Computing & Engineering">Faculty of Computing & Engineering</option>
                </select>
              </div>
              <div>
                <label className="block font-bold text-slate-700 mb-1">Capacity</label>
                <input type="number" required value={newRoom.capacity} onChange={(e) => setNewRoom({...newRoom, capacity: parseInt(e.target.value)})} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2.5 outline-none" />
              </div>
            </div>
            
            <div>
              <label className="block font-bold text-slate-700 mb-2">Available Facilities</label>
              <div className="flex flex-wrap gap-2">
                {availableFacilities.map(fac => (
                  <label key={fac} className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium cursor-pointer transition-all ${newRoomFacilities.includes(fac) ? 'bg-blue-50 border-blue-500 text-blue-700' : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100'}`}>
                    <input type="checkbox" checked={newRoomFacilities.includes(fac)} onChange={() => toggleNewFacility(fac)} className="rounded text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
                    {fac.toUpperCase()}
                  </label>
                ))}
              </div>
            </div>

            <button type="submit" className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 mt-2 cursor-pointer">
              <i className="fa-solid fa-save"></i> Save New Room
            </button>
          </form>
        </section>
      </div>

      {/* 4. MANAGE EXISTING ROOM FACILITIES (NEW SECTION) */}
      <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 mb-4 pb-3 border-b border-slate-100">
          <i className="fa-solid fa-screwdriver-wrench text-blue-600 mr-2"></i> Manage Room Facilities
        </h2>
        
        <div className="flex flex-col md:flex-row gap-6">
          {/* Room Selector */}
          <div className="w-full md:w-1/3">
            <label className="block font-bold text-slate-700 mb-2 text-xs">Select a Room to Edit</label>
            <select 
              value={selectedRoomId} 
              onChange={(e) => setSelectedRoomId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg px-3 py-3 outline-none focus:ring-2 focus:ring-blue-500 font-semibold"
            >
              {rooms.map(r => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
            {selectedRoom && (
              <div className="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                <p className="font-semibold text-slate-700">Current Setup:</p>
                <p className="text-slate-500 mt-1">{selectedRoom.facilities.length} facilities active.</p>
              </div>
            )}
          </div>

          {/* Facility Toggles */}
          <div className="w-full md:w-2/3">
            <label className="block font-bold text-slate-700 mb-2 text-xs">Click to Toggle Facilities On/Off</label>
            {selectedRoom ? (
              <div className="flex flex-wrap gap-3">
                {availableFacilities.map(fac => {
                  const isActive = selectedRoom.facilities.includes(fac);
                  return (
                    <button
                      key={fac}
                      onClick={() => toggleExistingFacility(fac)}
                      className={`px-4 py-3 rounded-xl border text-sm font-bold flex items-center gap-2 transition-all cursor-pointer shadow-sm ${
                        isActive 
                          ? 'bg-emerald-50 border-emerald-500 text-emerald-700 hover:bg-emerald-100' 
                          : 'bg-white border-slate-300 text-slate-400 hover:bg-slate-50 hover:text-slate-600'
                      }`}
                    >
                      <i className={`fa-solid ${isActive ? 'fa-check-circle' : 'fa-circle-xmark'}`}></i>
                      {fac.toUpperCase()}
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-slate-500">Select a room to manage its facilities.</p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
};

export default AdminDashboard;