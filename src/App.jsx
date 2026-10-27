import { useEffect, useState } from 'react';
import Login from './components/Login';
import Header from './components/Header';
import AdminDashboard from './components/AdminDashboard';
import LecturerDashboard from './components/LecturerDashboard';
import Toast from './components/Toast';
import { getCurrentUser, logoutUser } from './api';
import RoomBrowser from './components/RoomBrowser';
import CampusSchedule from './components/CampusSchedule';
import ReservationsPanel from './components/ReservationsPanel';

function App() {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [sessionLoading, setSessionLoading] = useState(true);
  const [sessionError, setSessionError] = useState('');
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
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
            {sessionError || 'Connecting… The first visit may take about a minute.'}
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

  if (!user) return <Login onLogin={handleLogin} adminOnly={window.location.pathname.replace(/\/$/, '') === '/staff-login'} />;

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
            <div className="my-6"><ReservationsPanel admin /></div>
            <RoomBrowser />
          </>
        ) : user.role === 'lecturer' ? (
          /* LECTURER VIEW */
          <>
            <div className="flex border-b border-slate-200 mb-6 gap-2 sm:gap-6 overflow-x-auto pb-0.5">
              <button onClick={() => setActiveTab('dashboard')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'dashboard' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-chalkboard-user"></i> Dashboard
              </button>
              <button onClick={() => setActiveTab('find')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'find' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-magnifying-glass"></i> Find a Room
              </button>
              {/* NEW: Campus Schedule Tab */}
              <button onClick={() => setActiveTab('reservations')} className={`px-4 py-2.5 font-bold text-sm border-b-2 whitespace-nowrap ${activeTab === 'reservations' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500'}`}>My Reservations</button>
              <button onClick={() => setActiveTab('campus-schedule')} className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${activeTab === 'campus-schedule' ? 'border-blue-700 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'}`}>
                <i className="fa-solid fa-calendar-days"></i> Campus Schedule
              </button>
            </div>

            {activeTab === 'dashboard' && (
              <RoomBrowser user={user}>
                {(rooms, openDetails) => <LecturerDashboard user={user} rooms={rooms} onOpenDetails={openDetails} setActiveTab={setActiveTab} />}
              </RoomBrowser>
            )}

            {activeTab === 'find' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>Check room availability against classes and approved bookings. Classes show Occupied; approved bookings show Reserved during their time slots. Cancellations release those slots.</p>
                </div>
                <RoomBrowser user={user} />
              </div>
            )}


            {activeTab === 'reservations' && <ReservationsPanel />}
            {activeTab === 'campus-schedule' && (
              <div className="space-y-4">
                <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>View scheduled lectures across the campus for your selected date.</p>
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
              <button onClick={() => setActiveTab('reservations')} className={`px-4 py-2.5 font-semibold text-sm border-b-2 whitespace-nowrap ${activeTab === 'reservations' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500'}`}>My Reservations</button>
            </div>

            {activeTab === 'lecture-rooms' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>Check the availability and timetables of large lecture theatres. Use the <strong>Reading Rooms</strong> tab to find smaller spaces for personal or group study.</p>
                </div>
                <RoomBrowser category="large" user={user} />
              </div>
            )}

            {activeTab === 'reading-rooms' && (
              <div className="space-y-6">
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-check-circle mt-0.5"></i>
                  <p>Find smaller rooms for personal or group study using the timetable and availability status.</p>
                </div>
                <RoomBrowser category="small" user={user} />
              </div>
            )}

            {activeTab === 'reservations' && <ReservationsPanel />}
            {activeTab === 'schedule' && (
              <div className="space-y-6">
                <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>View scheduled lectures across the campus for your selected date.</p>
                </div>
                <CampusSchedule />
              </div>
            )}

          </>
        )}

      </main>

      <footer className="bg-slate-900 text-slate-400 text-xs py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p>© 2026 Obafemi Awolowo University Optispace System.</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
