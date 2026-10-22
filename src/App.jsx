import { useEffect, useState } from 'react';

import Login from './components/Login';
import Header from './components/Header';
import SearchFilters from './components/SearchFilters';
import RoomGrid from './components/RoomGrid';
import BookingsTable from './components/BookingsTable';
import RoomDetailsModal from './components/RoomDetailsModal';
import AdminDashboard from './components/AdminDashboard';
import LecturerDashboard from './components/LecturerDashboard';
import Toast from './components/Toast';

import {
  getCurrentUser,
  getLagosDateTime,
  getRooms,
  logoutUser,
} from './api';

const studentTabs = [
  { id: 'lecture-rooms', label: 'Lecture Rooms', icon: 'fa-building-columns' },
  { id: 'reading-rooms', label: 'Reading Rooms', icon: 'fa-book-open' },
  { id: 'schedule', label: 'Class Schedule', icon: 'fa-calendar-days' },
  { id: 'bookings', label: 'My Reading Bookings', icon: 'fa-calendar-check' },
];

const lecturerTabs = [
  { id: 'dashboard', label: 'Command Center', icon: 'fa-chalkboard-user' },
  { id: 'find', label: 'Find a Room', icon: 'fa-magnifying-glass' },
  { id: 'bookings', label: 'My Schedule', icon: 'fa-calendar-check' },
  { id: 'campus-schedule', label: 'Campus Schedule', icon: 'fa-calendar-days' },
];

function makeDefaultSearch() {
  return {
    ...getLagosDateTime(),
    zone: 'all',
    capacity: 30,
    facilities: [],
    availableOnly: false,
  };
}

function defaultTab(role) {
  return role === 'student' ? 'lecture-rooms' : 'dashboard';
}

function App() {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [toasts, setToasts] = useState([]);

  // Session state
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [sessionError, setSessionError] = useState('');
  const [sessionCheckAttempt, setSessionCheckAttempt] = useState(0);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  // Real room data
  const [rooms, setRooms] = useState([]);
  const [search, setSearch] = useState(makeDefaultSearch);
  const [isLoadingRooms, setIsLoadingRooms] = useState(false);
  const [roomError, setRoomError] = useState('');
  const [roomReload, setRoomReload] = useState(0);

  const userId = user?.id;

  useEffect(() => {
    let active = true;

    async function restoreSession() {
      try {
        const currentUser = await getCurrentUser();

        if (!active) return;

        setUser(currentUser);

        if (currentUser) {
          setActiveTab(defaultTab(currentUser.role));
        }
      } catch (error) {
        if (active) {
          setSessionError(
            error.message || 'Unable to check your session.'
          );
        }
      } finally {
        if (active) {
          setIsCheckingSession(false);
        }
      }
    }

    restoreSession();

    return () => {
      active = false;
    };
  }, [sessionCheckAttempt]);

  useEffect(() => {
    if (!userId) return;

    let active = true;

    async function loadRooms() {
      setIsLoadingRooms(true);
      setRoomError('');
      setSelectedRoom(null);

      try {
        const data = await getRooms({
          date: search.date,
          time: search.time,
        });

        if (active) {
          setRooms(data);
        }
      } catch (error) {
        if (active) {
          setRooms([]);
          setRoomError(
            error.message || 'Unable to load room information.'
          );
        }
      } finally {
        if (active) {
          setIsLoadingRooms(false);
        }
      }
    }

    loadRooms();

    // Prevent an older request from replacing newer results.
    return () => {
      active = false;
    };
  }, [userId, search, roomReload]);

  const showToast = (message) => {
    setToasts((previous) => [
      ...previous,
      { id: Date.now(), message },
    ]);
  };

  const removeToast = (id) => {
    setToasts((previous) =>
      previous.filter((toast) => toast.id !== id)
    );
  };

  const handleLogin = (userData) => {
    setSearch(makeDefaultSearch());
    setUser(userData);
    setActiveTab(defaultTab(userData.role));
    setSelectedRoom(null);

    showToast(`Welcome, ${userData.name}`);
  };

  const handleLogout = async () => {
    if (isLoggingOut) return;

    setIsLoggingOut(true);

    try {
      await logoutUser();

      setUser(null);
      setRooms([]);
      setRoomError('');
      setSelectedRoom(null);
      setToasts([]);
      setActiveTab('dashboard');
      setSearch(makeDefaultSearch());
    } catch (error) {
      showToast(
        error.message || 'Unable to sign out. Please try again.'
      );
    } finally {
      setIsLoggingOut(false);
    }
  };

  const retrySessionCheck = () => {
    setSessionError('');
    setIsCheckingSession(true);
    setSessionCheckAttempt((previous) => previous + 1);
  };

  const reloadRooms = () => {
    setSelectedRoom(null);
    setRoomReload((previous) => previous + 1);
  };

  const applySearch = (values) => {
    setSelectedRoom(null);
    setSearch(values);
  };

  const bookingNotReady = () => {
    showToast(
      'Booking requests are not connected yet. No reservation has been created.'
    );
  };

  let activeCategory = 'all';

  if (user?.role === 'student') {
    if (activeTab === 'lecture-rooms') activeCategory = 'large';
    if (activeTab === 'reading-rooms') activeCategory = 'small';
  }

  // For this small room catalogue, suitability filters run in React.
  // Timetable availability is calculated by Django.
  const filteredRooms = rooms.filter((room) => {
    if (
      activeCategory !== 'all' &&
      room.sizeCategory !== activeCategory
    ) {
      return false;
    }

    if (search.zone !== 'all' && room.zone !== search.zone) {
      return false;
    }

    if (room.capacity < Number(search.capacity)) {
      return false;
    }

    if (
      !search.facilities.every((facility) =>
        room.facilities.includes(facility)
      )
    ) {
      return false;
    }

    if (
      search.availableOnly &&
      !['available', 'soon'].includes(room.status)
    ) {
      return false;
    }

    return true;
  });

  const visibleRooms =
    isLoadingRooms || roomError ? [] : filteredRooms;

  const stats = {
    total: visibleRooms.length,
    available: visibleRooms.filter(
      (room) => room.status === 'available'
    ).length,
    occupied: visibleRooms.filter(
      (room) => room.status === 'occupied'
    ).length,
    soon: visibleRooms.filter(
      (room) => room.status === 'soon'
    ).length,
    unknown: visibleRooms.filter(
      (room) => room.status === 'unknown'
    ).length,
  };

  const zones = [...new Set(rooms.map((room) => room.zone))];

  if (isCheckingSession || sessionError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100 p-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl text-center">
          <h1 className="text-2xl font-bold mb-4">Optispace</h1>

          {isCheckingSession ? (
            <p role="status">Checking session…</p>
          ) : (
            <>
              <p role="alert" className="text-sm text-rose-700">
                {sessionError}
              </p>

              <button
                type="button"
                onClick={retrySessionCheck}
                className="mt-5 rounded-lg bg-blue-600 px-5 py-2 text-white"
              >
                Retry
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  const tabs =
    user.role === 'lecturer' ? lecturerTabs : studentTabs;

  const isSearchTab = [
    'lecture-rooms',
    'reading-rooms',
    'find',
  ].includes(activeTab);

  const isBookingTab = [
    'schedule',
    'bookings',
    'campus-schedule',
  ].includes(activeTab);

  const roomFeedback = isLoadingRooms ? (
    <p role="status" className="rounded-xl bg-white p-6 text-slate-600">
      Loading rooms from Django…
    </p>
  ) : roomError ? (
    <div
      role="alert"
      className="rounded-xl border border-rose-200 bg-rose-50 p-4"
    >
      <p className="text-sm text-rose-700">{roomError}</p>

      <button
        type="button"
        onClick={reloadRooms}
        className="mt-3 rounded-lg bg-blue-600 px-4 py-2 text-xs text-white"
      >
        Retry loading rooms
      </button>
    </div>
  ) : null;

  return (
    <div className="min-h-screen flex flex-col font-sans text-slate-800 bg-slate-50">
      <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end pointer-events-none">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            message={toast.message}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>

      <Header
        user={user}
        onLogout={handleLogout}
        stats={stats}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {isLoggingOut && (
          <p role="status" className="text-sm text-blue-700">
            Signing out…
          </p>
        )}

        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
          <p className="font-semibold">
            Selected moment: {search.date} at {search.time} — Africa/Lagos
          </p>

          <p className="mt-1">
            Room statuses and counters refer to this selected moment,
            according to the timetable—not verified physical occupancy.
          </p>

          <p className="mt-1">
            Unknown availability does not mean the room is free.
            Booking requests are not connected yet.
          </p>

          {stats.unknown > 0 && (
            <p className="mt-1 font-semibold">
              {stats.unknown} displayed room(s) have unknown availability.
            </p>
          )}

          <button
            type="button"
            disabled={isLoadingRooms}
            onClick={reloadRooms}
            className="mt-3 text-xs font-bold underline disabled:opacity-50"
          >
            Reload database results
          </button>
        </div>

        {user.role !== 'admin' && (
          <nav className="flex border-b border-slate-200 gap-2 sm:gap-6 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 font-semibold text-sm border-b-2 flex items-center gap-2 whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <i className={`fa-solid ${tab.icon}`}></i>
                {tab.label}
              </button>
            ))}
          </nav>
        )}

        {(isSearchTab || user.role === 'admin') && (
          <SearchFilters
            initialValues={search}
            zones={zones}
            activeCategory={activeCategory}
            onApply={applySearch}
            onReset={applySearch}
            disabled={isLoadingRooms}
          />
        )}

        {roomFeedback}

        {!isLoadingRooms && !roomError && user.role === 'admin' && (
          <AdminDashboard
            rooms={visibleRooms}
            onOpenDetails={setSelectedRoom}
          />
        )}

        {!isLoadingRooms && !roomError && user.role !== 'admin' && (
          <>
            {isSearchTab && (
              <div className="space-y-4">
                {activeTab === 'reading-rooms' && (
                  <p className="text-sm text-slate-600">
                    These are smaller rooms in the catalogue.
                    Size alone does not establish permission to use a room
                    for studying; university room-use rules still apply.
                  </p>
                )}

                <RoomGrid
                  rooms={visibleRooms}
                  onOpenDetails={setSelectedRoom}
                  canBook={false}
                />
              </div>
            )}

            {user.role === 'lecturer' && activeTab === 'dashboard' && (
              <LecturerDashboard
                user={user}
                rooms={rooms}
                bookings={[]}
                onOpenDetails={setSelectedRoom}
                onQuickBook={bookingNotReady}
                setActiveTab={setActiveTab}
              />
            )}
          </>
        )}

        {user.role !== 'admin' && isBookingTab && (
          <section className="space-y-4">
            <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              Booking and campus-schedule data have not been connected yet.
              This table does not currently list database reservations.
            </p>

            <BookingsTable bookings={[]} readOnly={true} />
          </section>
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
          © 2026 Obafemi Awolowo University Optispace System.
        </div>
      </footer>
    </div>
  );
}

export default App;

