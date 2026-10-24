const LecturerDashboard = ({ user, rooms, bookings, onOpenDetails, onQuickBook, setActiveTab, bookingEnabled = true }) => {
  // Separate bookings for stats
  const approvedClasses = bookings.filter(b => b.isApproved);
  const pendingClasses = bookings.filter(b => !b.isApproved);
  
  // Look for available LARGE lecture rooms for quick booking
  const availableLectureRooms = rooms.filter(r => ['available', 'soon'].includes(r.status) && r.sizeCategory === 'large');

  return (
    <div className="space-y-6">
      
      {/* Welcome Banner */}
      <div 
        style={{ backgroundColor: '#1e3a8a', border: '1px solid #172554' }} 
        className="rounded-2xl p-8 text-white shadow-lg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
      >
        <div>
          <h1 style={{ color: '#ffffff', fontWeight: 'bold', fontSize: '24px', margin: 0 }}>
            Welcome back, {user.name}
          </h1>
          <p style={{ color: '#bfdbfe', fontSize: '14px', marginTop: '4px', fontWeight: '500' }}>
            Here is your room overview for the selected date and time.
          </p>
        </div>
        <button 
          onClick={() => setActiveTab('find')} 
          style={{ backgroundColor: '#ffffff', color: '#1e3a8a', fontWeight: 'bold' }}
          className="px-5 py-2.5 text-sm rounded-xl shadow-md hover:bg-slate-100 transition-colors flex items-center cursor-pointer"
        >
          <i className="fa-solid fa-magnifying-glass mr-2"></i> Find Lecture Room
        </button>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-xl">
            <i className="fa-solid fa-door-open"></i>
          </div>
          <div>
            <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Vacant Lecture Rooms</p>
            <p className="text-2xl font-black text-slate-800">{availableLectureRooms.length}</p>
          </div>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xl">
            <i className="fa-solid fa-chalkboard"></i>
          </div>
          <div>
            <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Approved Classes</p>
            <p className="text-2xl font-black text-slate-800">{approvedClasses.length}</p>
          </div>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center text-xl">
            <i className="fa-solid fa-hourglass-half"></i>
          </div>
          <div>
            <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Pending Requests</p>
            <p className="text-2xl font-black text-slate-800">{pendingClasses.length}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Quick Book Available Lecture Rooms */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-bold text-slate-800"><i className="fa-solid fa-bolt text-amber-500 mr-2"></i> Available Lecture Rooms</h3>
            <button onClick={() => setActiveTab('find')} className="text-xs text-blue-600 font-bold hover:underline cursor-pointer">View All</button>
          </div>
          <div className="space-y-3">
            {availableLectureRooms.length === 0 ? (
              <p className="text-sm text-slate-500">No large lecture rooms are currently vacant.</p>
            ) : (
              availableLectureRooms.slice(0, 4).map(room => (
                <div key={room.id} className="flex items-center justify-between p-3 border border-slate-100 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors">
                  <div>
                    <p className="font-bold text-sm text-slate-800">{room.name}</p>
                    <p className="text-[10px] text-slate-500">{room.capacity} Seats • {room.type}</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => onOpenDetails(room)} className="px-2 py-1.5 bg-white border border-slate-300 text-slate-600 rounded text-[10px] font-bold hover:bg-slate-50 cursor-pointer shadow-sm">Details</button>
                    {bookingEnabled && <button onClick={() => onQuickBook(room)} className="px-3 py-1.5 bg-blue-600 text-white rounded text-[10px] font-bold hover:bg-blue-700 cursor-pointer shadow-sm">Book</button>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Upcoming Schedule with Status Badges */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-bold text-slate-800"><i className="fa-solid fa-calendar-day text-blue-500 mr-2"></i> My Upcoming Schedule</h3>
          </div>
          <div className="space-y-3 max-h-[350px] overflow-y-auto pr-2">
            {bookings.length === 0 ? (
              <p className="text-sm text-slate-500">You have no scheduled or pending lectures.</p>
            ) : (
              bookings.map(b => (
                <div key={b.refId} className="flex items-start gap-3 p-3 border border-slate-100 rounded-xl bg-slate-50">
                  {/* Visual Indicator Left Border */}
                  <div className={`w-2 h-full min-h-[40px] rounded-full ${b.isApproved ? 'bg-emerald-500' : 'bg-amber-500'}`}></div>
                  
                  <div className="flex-1">
                    <p className="font-bold text-sm text-slate-800">{b.purpose}</p>
                    <p className="text-xs text-slate-500">{b.roomName}</p>
                    <p className="text-[10px] text-slate-400 mt-1 font-mono">{b.date} • {b.timeSlot}</p>
                  </div>
                  
                  {/* Status Badge */}
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    b.isApproved 
                      ? 'bg-emerald-100 text-emerald-800' 
                      : 'bg-amber-100 text-amber-800'
                  }`}>
                    {b.isApproved ? 'Approved' : 'Pending'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default LecturerDashboard;
