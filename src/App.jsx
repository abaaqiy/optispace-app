import { useEffect, useState } from 'react';
import Login from './components/Login';
import Header from './components/Header';
import BookingsTable from './components/BookingsTable';
import RoomDetailsModal from './components/RoomDetailsModal';
import AdminDashboard from './components/AdminDashboard';
import LecturerDashboard from './components/LecturerDashboard';
import Toast from './components/Toast';
import { getCurrentUser, logoutUser } from './api';
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

  const bookingNotice = () => showToast('Reservation requests will be available in the next milestone.');

  return (
    <div className="min-h-screen flex flex-col font-sans text-slate-800 bg-slate-50">

      <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end pointer-events-none">
        {toasts.map(t => <Toast key={t.id} message={t.message} onClose={() => removeToast(t.id)} />)}
      </div>

      <Header user={user} onLogout={handleLogout} isLoggingOut={isLoggingOut} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">

        {user.role === 'admin' ? (
          <>
            <AdminDashboard />
            <RoomBrowser onOpenDetails={setSelectedRoom} canBook={false} />
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
              <RoomBrowser onOpenDetails={setSelectedRoom} canBook={false}>
                {(rooms) => <LecturerDashboard
                  user={user} rooms={rooms} bookings={[]}
                  onOpenDetails={setSelectedRoom} onQuickBook={bookingNotice}
                  setActiveTab={setActiveTab} bookingEnabled={false}
                />}
              </RoomBrowser>
            )}

            {activeTab === 'find' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>Check published room availability before planning your classes. Reservation requests will be available in the next milestone.</p>
                </div>
                <RoomBrowser onOpenDetails={setSelectedRoom} canBook={false} />
              </div>
            )}

            {activeTab === 'bookings' && (
              <div className="space-y-4">
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-check-circle mt-0.5"></i>
                  <p>Personal reservations will appear here once the booking milestone is implemented. Use Campus Schedule for published lectures.</p>
                </div>
                <BookingsTable bookings={[]} onCancel={bookingNotice} />
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
                <RoomBrowser category="large" onOpenDetails={setSelectedRoom} canBook={false} />
              </div>
            )}

            {activeTab === 'reading-rooms' && (
              <div className="space-y-6">
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-check-circle mt-0.5"></i>
                  <p>Find smaller rooms and labs suitable for reading sessions. Availability is based on published schedules.</p>
                </div>
                <RoomBrowser category="small" onOpenDetails={setSelectedRoom} canBook={false} />
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
              <div className="space-y-4"><p className="text-sm text-slate-600">Reservation requests will be available in the next milestone.</p><BookingsTable bookings={[]} onCancel={bookingNotice} /></div>
            )}
          </>
        )}

      </main>

      {selectedRoom && (
        <RoomDetailsModal
          room={selectedRoom}
          onClose={() => setSelectedRoom(null)}
          canBook={false}
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
