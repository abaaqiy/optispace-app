import React, { useState } from 'react';
import Login from './components/Login';
import Header from './components/Header';
import SearchFilters from './components/SearchFilters';
import RoomGrid from './components/RoomGrid';
import BookingsTable from './components/BookingsTable';
import RoomDetailsModal from './components/RoomDetailsModal';
import BookingModal from './components/BookingModal';
import AdminDashboard from './components/AdminDashboard';
import LecturerDashboard from './components/LecturerDashboard';
import Toast from './components/Toast';
import { initialRoomsData, initialBookings } from './data/mockData';

function App() {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard'); 
  const [rooms, setRooms] = useState(initialRoomsData);
  const [filteredRooms, setFilteredRooms] = useState(initialRoomsData);
  const [bookings, setBookings] = useState(initialBookings);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [isBookingModalOpen, setIsBookingModalOpen] = useState(false);
  const [toasts, setToasts] = useState([]);

  const stats = {
    total: filteredRooms.length,
    available: filteredRooms.filter(r => r.status === 'available').length, 
    occupied: filteredRooms.filter(r => r.status === 'occupied').length,
    soon: filteredRooms.filter(r => r.status === 'soon').length, 
  };

  const showToast = (message) => {
    setToasts(prev => [...prev, { id: Date.now(), message }]);
  };

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  const handleLogin = (userData) => {
    setUser(userData);
    setActiveTab(userData.role === 'lecturer' ? 'dashboard' : 'lecture-rooms'); 
    showToast(`Welcome, ${userData.name}`);
  };

  const handleLogout = () => {
    setUser(null);
    setActiveTab('find');
    setSelectedRoom(null);
    setIsBookingModalOpen(false);
    setFilteredRooms(rooms);
  };

  const handleApplyFilters = ({ zone, capacity, facilities }) => {
    let result = rooms;
    if (user.role === 'student') {
      if (activeTab === 'reading-rooms') result = result.filter(r => r.sizeCategory === 'small');
      if (activeTab === 'lecture-rooms') result = result.filter(r => r.sizeCategory === 'large');
    } 
    if (zone !== 'all') result = result.filter(r => r.zone === zone);
    if (capacity) result = result.filter(r => r.capacity >= parseInt(capacity));
    if (facilities.length > 0) {
      result = result.filter(r => facilities.every(f => r.facilities.includes(f)));
    }
    setFilteredRooms(result);
    showToast(`Filters applied: ${result.length} rooms found.`);
  };

  const handleResetFilters = () => {
    setFilteredRooms(rooms);
    showToast("Filters reset to default.");
  };

  const handleBookingConfirm = (bookingData) => {
    const refCode = "OAU-" + new Date().getFullYear() + "-" + Math.floor(1000 + Math.random() * 9000);
    const newBooking = { ...bookingData, refId: refCode, status: "Pending", isApproved: false };

    setBookings([newBooking, ...bookings]);
    setIsBookingModalOpen(false);
    showToast(`Booking requested! Ref: ${refCode}. Awaiting Admin approval.`);
  };

  const handleCancelBooking = (refId) => {
    setBookings(bookings.filter(b => b.refId !== refId));
    showToast(`Reservation ${refId} cancelled.`);
  };

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  // Global Approved Bookings
  const approvedBookings = bookings.filter(b => b.isApproved);
  
  // Lecturer Specific Bookings
  const lecturerAllBookings = bookings.filter(b => b.staffId === user.id);
  const lecturerApprovedBookings = lecturerAllBookings.filter(b => b.isApproved);

  const canBookSelectedRoom = () => {
    if (!selectedRoom) return false;
    if (user.role === 'admin') return false; 
    if (user.role === 'lecturer') return true; 
    if (user.role === 'student') return selectedRoom.sizeCategory === 'small';
    return false;
  };

  return (
    <div className="min-h-screen flex flex-col font-sans text-slate-800 bg-slate-50">
      
      <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end pointer-events-none">
        {toasts.map(t => <Toast key={t.id} message={t.message} onClose={() => removeToast(t.id)} />)}
      </div>

      <Header user={user} onLogout={handleLogout} stats={stats} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        
        {user.role === 'admin' ? (
          <AdminDashboard 
            rooms={rooms} setRooms={setRooms} bookings={bookings} 
            setBookings={setBookings} showToast={showToast} 
          />
        ) : user.role === 'lecturer' ? (
          /* LECTURER VIEW */
          <>
            <div className="flex border-b border-slate-200 mb-6 gap-2 sm:gap-6 overflow-x-auto pb-0.5">
              <button onClick={() => setActiveTab('dashboard')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'dashboard' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-chalkboard-user"></i> Command Center
              </button>
              <button onClick={() => setActiveTab('find')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'find' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-magnifying-glass"></i> Book a Room
              </button>
              <button onClick={() => setActiveTab('bookings')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'bookings' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-calendar-check"></i> My Schedule
                <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full font-bold ml-1">{lecturerApprovedBookings.length}</span>
              </button>
              {/* NEW: Campus Schedule Tab */}
              <button onClick={() => setActiveTab('campus-schedule')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'campus-schedule' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-calendar-days"></i> Campus Schedule
              </button>
            </div>

            {activeTab === 'dashboard' && (
              <LecturerDashboard 
                user={user} 
                rooms={rooms} 
                bookings={lecturerAllBookings} 
                onOpenDetails={(room) => setSelectedRoom(room)}
                onQuickBook={(room) => { setSelectedRoom(room); setIsBookingModalOpen(true); }}
                setActiveTab={setActiveTab}
              />
            )}

            {activeTab === 'find' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>You can book any available lecture theatre or smaller room for your classes. All bookings require Admin approval.</p>
                </div>
                <SearchFilters onApply={handleApplyFilters} onReset={handleResetFilters} activeCategory="all" />
                <RoomGrid 
                  rooms={filteredRooms} 
                  onOpenDetails={(room) => setSelectedRoom(room)} 
                  onQuickBook={(room) => { setSelectedRoom(room); setIsBookingModalOpen(true); }} 
                  canBook={true} 
                />
              </div>
            )}

            {activeTab === 'bookings' && (
              <div className="space-y-4">
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-check-circle mt-0.5"></i>
                  <p>These are your officially approved classes. Pending requests can be viewed on the Command Center.</p>
                </div>
                <BookingsTable bookings={lecturerApprovedBookings} onCancel={handleCancelBooking} />
              </div>
            )}

            {activeTab === 'campus-schedule' && (
              <div className="space-y-4">
                <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>View all officially approved lectures and classes currently scheduled across the campus by other lecturers.</p>
                </div>
                <BookingsTable bookings={approvedBookings} readOnly={true} />
              </div>
            )}
          </>
        ) : (
          /* STANDARD STUDENT VIEW */
          <>
            <div className="flex border-b border-slate-200 mb-6 gap-2 sm:gap-6 overflow-x-auto pb-0.5">
              <button onClick={() => setActiveTab('lecture-rooms')} className={`px-4 py-2.5 font-semibold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'lecture-rooms' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-building-columns"></i> Lecture Rooms
              </button>
              <button onClick={() => setActiveTab('reading-rooms')} className={`px-4 py-2.5 font-semibold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'reading-rooms' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-book-open"></i> Book Reading Room
              </button>
              <button onClick={() => setActiveTab('schedule')} className={`px-4 py-2.5 font-semibold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'schedule' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-calendar-days"></i> Class Schedule
              </button>
              <button onClick={() => setActiveTab('bookings')} className={`px-4 py-2.5 font-semibold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'bookings' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-calendar-check"></i> My Reading Bookings
              </button>
            </div>

            {activeTab === 'lecture-rooms' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>Students can view the status and class schedules of large lecture theatres here. To reserve a space for personal or group study, please use the <strong>Book Reading Room</strong> tab.</p>
                </div>
                <SearchFilters onApply={handleApplyFilters} onReset={handleResetFilters} activeCategory="large" />
                <RoomGrid 
                  rooms={filteredRooms.filter(r => r.sizeCategory === 'large')} 
                  onOpenDetails={(room) => setSelectedRoom(room)} 
                  onQuickBook={() => {}} 
                  canBook={false} 
                />
              </div>
            )}

            {activeTab === 'reading-rooms' && (
              <div className="space-y-6">
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-check-circle mt-0.5"></i>
                  <p>You can request to book smaller lecture rooms and labs for reading sessions. Requests are sent to the Admin for approval.</p>
                </div>
                <SearchFilters 
                  onApply={handleApplyFilters} 
                  onReset={handleResetFilters} 
                  activeCategory="small" 
                  maxCapacity={50} 
                />
                <RoomGrid 
                  rooms={filteredRooms.filter(r => r.sizeCategory === 'small')} 
                  onOpenDetails={(room) => setSelectedRoom(room)} 
                  onQuickBook={(room) => { setSelectedRoom(room); setIsBookingModalOpen(true); }} 
                  canBook={true} 
                />
              </div>
            )}

            {activeTab === 'schedule' && (
              <div className="space-y-6">
                <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>View all officially approved lectures and classes currently scheduled across the campus.</p>
                </div>
                <BookingsTable bookings={approvedBookings} readOnly={true} />
              </div>
            )}

            {activeTab === 'bookings' && (
              <BookingsTable bookings={bookings} onCancel={handleCancelBooking} />
            )}
          </>
        )}

      </main>

      {selectedRoom && !isBookingModalOpen && (
        <RoomDetailsModal 
          room={selectedRoom} 
          onClose={() => setSelectedRoom(null)} 
          onBook={() => setIsBookingModalOpen(true)} 
          canBook={canBookSelectedRoom()} 
        />
      )}

      {isBookingModalOpen && selectedRoom && (
        <BookingModal 
          room={selectedRoom} 
          user={user}
          onClose={() => { setIsBookingModalOpen(false); setSelectedRoom(null); }} 
          onConfirm={handleBookingConfirm} 
        />
      )}
      
      <footer className="bg-slate-900 text-slate-400 text-xs py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p>© 2026 Obafemi Awolowo University Optispace System.</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
