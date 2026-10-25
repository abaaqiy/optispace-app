import { useEffect, useState } from 'react';
import Login from './components/Login';
import Header from './components/Header';
import ReservationsPanel from './components/ReservationsPanel';
import BookingModal from './components/BookingModal';
import RoomDetailsModal from './components/RoomDetailsModal';
import AdminDashboard from './components/AdminDashboard';
import LecturerDashboard from './components/LecturerDashboard';
import Toast from './components/Toast';
import { createReservation, getCurrentUser, getReservations, logoutUser } from './api';
import RoomBrowser from './components/RoomBrowser';
import CampusSchedule from './components/CampusSchedule';

function App() {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [sessionLoading, setSessionLoading] = useState(true);
  const [sessionError, setSessionError] = useState('');
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [bookingRoom, setBookingRoom] = useState(null);
  const [reservationRevision, setReservationRevision] = useState(0);
  const [lecturerReservations, setLecturerReservations] = useState(null);
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    let active = true;
    getCurrentUser().then((account) => {
      if (!active) return;
      setUser(account);
      setActiveTab(account?.role === 'lecturer' ? 'dashboard' : 'lecture-rooms');
      setSessionError('');
    }).catch((error) => {
      if (active) setSessionError(error.message);
    }).finally(() => {
      if (active) setSessionLoading(false);
    });
    return () => { active = false; };
  }, [sessionAttempt]);

  useEffect(() => {
    if (user?.role !== 'lecturer' || activeTab !== 'dashboard') return;
    let active = true;
    const controller = new AbortController();
    const refresh = () => getReservations({ signal: controller.signal }).then(rows => {
      if (active) setLecturerReservations({ userId: user.id, rows });
    }).catch(error => {
      if (active) setLecturerReservations({ userId: user.id, error: error.message });
    });
    refresh();
    const timer = setInterval(refresh, 60000);
    window.addEventListener('focus', refresh);
    return () => { active = false; controller.abort(); clearInterval(timer); window.removeEventListener('focus', refresh); };
  }, [user, activeTab, reservationRevision]);

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

  const handleLogout = async () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    try {
      await logoutUser();
      setUser(null);
      setActiveTab('lecture-rooms');
      setSelectedRoom(null);
      setBookingRoom(null);
      setLecturerReservations(null);
    } catch (error) {
      showToast(error.message);
    } finally {
      setIsLoggingOut(false);
    }
  };

  if (sessionLoading || sessionError) {
    return (
      <main className="min-h-screen grid place-items-center bg-slate-100 p-6">
        <div className="bg-white border border-slate-200 rounded-2xl p-8 text-center">
          <h1 className="text-xl font-bold mb-3">Optispace</h1>
          <p role={sessionError ? 'alert' : 'status'}>
            {sessionError || 'Restoring your session…'}
          </p>
          {sessionError && (
            <button className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg" onClick={() => {
              setSessionError('');
              setSessionLoading(true);
              setSessionAttempt(value => value + 1);
            }}>Retry connection</button>
          )}
        </div>
      </main>
    );
  }

  if (!user) return <Login onLogin={handleLogin} />;

  const refreshReservations = () => setReservationRevision(value => value + 1);
  const canReserve = room => user.role === 'lecturer' || (user.role === 'student' && room.sizeCategory === 'small');
  const openBooking = room => {
    if (canReserve(room)) {
      setSelectedRoom(null);
      setBookingRoom(room);
    }
  };
  const submitReservation = async details => {
    const booking = await createReservation(details);
    setBookingRoom(null);
    refreshReservations();
    setActiveTab('bookings');
    showToast(`Request submitted (${booking.refId}). Awaiting administrator approval.`);
  };

  return (
    <div className="min-h-screen flex flex-col font-sans text-slate-800 bg-slate-50">

      <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end pointer-events-none">
        {toasts.map(t => <Toast key={t.id} message={t.message} onClose={() => removeToast(t.id)} />)}
      </div>

      <Header user={user} onLogout={handleLogout} isLoggingOut={isLoggingOut} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">

        {user.role === 'admin' ? (
          <>
            <AdminDashboard onReservationChanged={refreshReservations} />
            <RoomBrowser onOpenDetails={setSelectedRoom} refreshKey={reservationRevision} />
          </>
        ) : user.role === 'lecturer' ? (
          /* LECTURER VIEW */
          <>
            <div className="flex border-b border-slate-200 mb-6 gap-2 sm:gap-6 overflow-x-auto pb-0.5">
              <button onClick={() => setActiveTab('dashboard')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'dashboard' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-chalkboard-user"></i> Command Center
              </button>
              <button onClick={() => setActiveTab('find')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'find' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-magnifying-glass"></i> Find a Room
              </button>
              <button onClick={() => setActiveTab('bookings')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'bookings' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-calendar-check"></i> My Schedule

              </button>
              {/* NEW: Campus Schedule Tab */}
              <button onClick={() => setActiveTab('campus-schedule')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'campus-schedule' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-calendar-days"></i> Campus Schedule
              </button>
            </div>

            {activeTab === 'dashboard' && (
              <RoomBrowser onOpenDetails={setSelectedRoom} refreshKey={reservationRevision}>
                {(rooms) => lecturerReservations?.userId !== user.id ? <p role="status">Loading your reservations…</p> : lecturerReservations.error ? (
                  <div role="alert"><p>{lecturerReservations.error}</p><button onClick={refreshReservations} className="text-blue-700 underline">Retry reservations</button></div>
                ) : <LecturerDashboard
                  user={user} rooms={rooms} bookings={lecturerReservations.rows.filter(booking => ['pending', 'approved'].includes(booking.statusCode) && new Date(`${booking.date}T${booking.endTime}:00+01:00`) > new Date()).sort((a, b) => `${a.date} ${a.startTime}`.localeCompare(`${b.date} ${b.startTime}`))}
                  onOpenDetails={setSelectedRoom} onQuickBook={openBooking}
                  setActiveTab={setActiveTab}
                />}
              </RoomBrowser>
            )}

            {activeTab === 'find' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>Choose a room and request a free time within its published timetable. An administrator must approve your request.</p>
                </div>
                <RoomBrowser onOpenDetails={setSelectedRoom} canBook onQuickBook={openBooking} refreshKey={reservationRevision} />
              </div>
            )}

            {activeTab === 'bookings' && (
              <div className="space-y-4">
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-check-circle mt-0.5"></i>
                  <p>Track your requests and administrator decisions here. Pending requests do not reserve a room. You can cancel before the start time.</p>
                </div>
                <ReservationsPanel onChanged={refreshReservations} />
              </div>
            )}

            {activeTab === 'campus-schedule' && (
              <div className="space-y-4">
                <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>View published lectures across the campus for your selected date.</p>
                </div>
                <CampusSchedule />
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
                <i className="fa-solid fa-book-open"></i> Reading Rooms
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
                  <p>Check the availability and published schedules of large lecture theatres. Use the <strong>Reading Rooms</strong> tab to find smaller spaces for personal or group study.</p>
                </div>
                <RoomBrowser category="large" onOpenDetails={setSelectedRoom} refreshKey={reservationRevision} />
              </div>
            )}

            {activeTab === 'reading-rooms' && (
              <div className="space-y-6">
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-check-circle mt-0.5"></i>
                  <p>Request a smaller room for personal or group study during a free period in its published timetable. Administrator approval is required.</p>
                </div>
                <RoomBrowser category="small" onOpenDetails={setSelectedRoom} canBook onQuickBook={openBooking} refreshKey={reservationRevision} />
              </div>
            )}

            {activeTab === 'schedule' && (
              <div className="space-y-6">
                <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>View published lectures across the campus for your selected date.</p>
                </div>
                <CampusSchedule />
              </div>
            )}

            {activeTab === 'bookings' && (
              <div className="space-y-4"><p className="text-sm text-slate-600">Pending requests need administrator approval. You can cancel your request or reservation before its start time.</p><ReservationsPanel onChanged={refreshReservations} /></div>
            )}
          </>
        )}

      </main>

      {selectedRoom && (
        <RoomDetailsModal
          room={selectedRoom}
          onClose={() => setSelectedRoom(null)}
          canBook={canReserve(selectedRoom)}
          onBook={openBooking}
        />
      )}

      {bookingRoom && <BookingModal room={bookingRoom} user={user} onClose={() => setBookingRoom(null)} onConfirm={submitReservation} />}

      <footer className="bg-slate-900 text-slate-400 text-xs py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p>© 2026 Obafemi Awolowo University Optispace System.</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
