import { useEffect, useState } from 'react';

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
import { getCurrentUser, logoutUser } from './api';

function App() {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');

  // Still demo data until the room and booking integrations.
  const [rooms, setRooms] = useState(initialRoomsData);
  const [filteredRooms, setFilteredRooms] = useState(initialRoomsData);
  const [bookings, setBookings] = useState(initialBookings);

  const [selectedRoom, setSelectedRoom] = useState(null);
  const [isBookingModalOpen, setIsBookingModalOpen] = useState(false);
  const [toasts, setToasts] = useState([]);

  // Session state
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [sessionError, setSessionError] = useState('');
  const [sessionCheckAttempt, setSessionCheckAttempt] = useState(0);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  // Restore the authenticated user when the application opens.
  useEffect(() => {
    let active = true;

    async function restoreSession() {
      try {
        const currentUser = await getCurrentUser();

        if (!active) return;

        setUser(currentUser);

        if (currentUser) {
          setActiveTab(
            currentUser.role === 'lecturer'
              ? 'dashboard'
              : 'lecture-rooms'
          );
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

    // Ignore a response if this effect has already been cleaned up.
    return () => {
      active = false;
    };
  }, [sessionCheckAttempt]);

  const retrySessionCheck = () => {
    setSessionError('');
    setIsCheckingSession(true);
    setSessionCheckAttempt((previous) => previous + 1);
  };

  const stats = {
    total: filteredRooms.length,
    available: filteredRooms.filter(
      (room) => room.status === 'available'
    ).length,
    occupied: filteredRooms.filter(
      (room) => room.status === 'occupied'
    ).length,
    soon: filteredRooms.filter(
      (room) => room.status === 'soon'
    ).length,
  };

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
    setUser(userData);

    setActiveTab(
      userData.role === 'lecturer'
        ? 'dashboard'
        : 'lecture-rooms'
    );

    setSelectedRoom(null);
    setIsBookingModalOpen(false);

    showToast(`Welcome, ${userData.name}`);
  };

  const handleLogout = async () => {
    if (isLoggingOut) return;

    setIsLoggingOut(true);

    try {
      // End the Django session before clearing the interface.
      await logoutUser();

      setUser(null);
      setActiveTab('dashboard');
      setSelectedRoom(null);
      setIsBookingModalOpen(false);
      setToasts([]);

      // Reset temporary demo changes between sessions.
      setRooms(initialRoomsData);
      setFilteredRooms(initialRoomsData);
      setBookings(initialBookings);
    } catch (error) {
      showToast(
        error.message || 'Unable to sign out. Please try again.'
      );
    } finally {
      setIsLoggingOut(false);
    }
  };

  const handleApplyFilters = ({
    zone = 'all',
    capacity = '',
    facilities = [],
  }) => {
    let result = rooms;

    if (user?.role === 'student') {
      if (activeTab === 'reading-rooms') {
        result = result.filter(
          (room) => room.sizeCategory === 'small'
        );
      }

      if (activeTab === 'lecture-rooms') {
        result = result.filter(
          (room) => room.sizeCategory === 'large'
        );
      }
    }

    if (zone !== 'all') {
      result = result.filter((room) => room.zone === zone);
    }

    if (capacity) {
      result = result.filter(
        (room) => room.capacity >= parseInt(capacity, 10)
      );
    }

    if (facilities.length > 0) {
      result = result.filter((room) =>
        facilities.every((facility) =>
          room.facilities.includes(facility)
        )
      );
    }

    setFilteredRooms(result);
    showToast(`Filters applied: ${result.length} rooms found.`);
  };

  const handleResetFilters = () => {
    setFilteredRooms(rooms);
    showToast('Filters reset to default.');
  };

  // Demo booking behaviour only; no booking API call yet.
  const handleBookingConfirm = (bookingData) => {
    const refCode =
      'OAU-' +
      new Date().getFullYear() +
      '-' +
      Math.floor(1000 + Math.random() * 9000);

    const newBooking = {
      ...bookingData,
      refId: refCode,
      status: 'Pending',
      isApproved: false,
    };

    setBookings((previous) => [newBooking, ...previous]);
    setIsBookingModalOpen(false);

    showToast(
      `Demo booking ${refCode} added locally. It has not been sent to Django.`
    );
  };

  const handleCancelBooking = (refId) => {
    setBookings((previous) =>
      previous.filter((booking) => booking.refId !== refId)
    );

    showToast(`Demo reservation ${refId} removed locally.`);
  };

  const canBookSelectedRoom = () => {
    if (!selectedRoom || !user) return false;
    if (user.role === 'admin') return false;
    if (user.role === 'lecturer') return true;

    if (user.role === 'student') {
      return selectedRoom.sizeCategory === 'small';
    }

    return false;
  };

  // Do not briefly show the login page before checking the session.
  if (isCheckingSession || sessionError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100 p-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl text-center">
          <h1 className="text-2xl font-bold text-slate-900 mb-4">
            Optispace
          </h1>

          {isCheckingSession ? (
            <p role="status" className="text-slate-600">
              Checking session…
            </p>
          ) : (
            <>
              <p
                role="alert"
                className="text-sm text-rose-700 whitespace-pre-line"
              >
                {sessionError}
              </p>

              <button
                type="button"
                onClick={retrySessionCheck}
                className="mt-5 rounded-lg bg-blue-600 px-5 py-2 text-white font-semibold hover:bg-blue-700"
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

  // These booking collections still contain demo data.
  const approvedBookings = bookings.filter(
    (booking) => booking.isApproved
  );

  const lecturerAllBookings = bookings.filter(
    (booking) => booking.staffId === user.id
  );

  const lecturerApprovedBookings = lecturerAllBookings.filter(
    (booking) => booking.isApproved
  );

  return (
    <div
      className="min-h-screen flex flex-col font-sans text-slate-800 bg-slate-50"
      aria-busy={isLoggingOut}
    >
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

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {isLoggingOut && (
          <p
            role="status"
            className="mb-4 text-sm font-medium text-blue-700"
          >
            Signing out…
          </p>
        )}

        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Login and registration use Django. Rooms and bookings below
          are still demo data; changes to them are not saved to the backend.
        </div>

        {user.role === 'admin' ? (
          <AdminDashboard
            rooms={rooms}
            setRooms={setRooms}
            bookings={bookings}
            setBookings={setBookings}
            showToast={showToast}
          />
        ) : user.role === 'lecturer' ? (
          <>
            {/* Lecturer navigation */}
            <div className="flex border-b border-slate-200 mb-6 gap-2 sm:gap-6 overflow-x-auto pb-0.5">
              <button
                onClick={() => setActiveTab('dashboard')}
                className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${
                  activeTab === 'dashboard'
                    ? 'border-blue-700 text-blue-700'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <i className="fa-solid fa-chalkboard-user"></i>
                Command Center
              </button>

              <button
                onClick={() => setActiveTab('find')}
                className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${
                  activeTab === 'find'
                    ? 'border-blue-700 text-blue-700'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <i className="fa-solid fa-magnifying-glass"></i>
                Book a Room
              </button>

              <button
                onClick={() => setActiveTab('bookings')}
                className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${
                  activeTab === 'bookings'
                    ? 'border-blue-700 text-blue-700'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <i className="fa-solid fa-calendar-check"></i>
                My Schedule

                <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full font-bold ml-1">
                  {lecturerApprovedBookings.length}
                </span>
              </button>

              <button
                onClick={() => setActiveTab('campus-schedule')}
                className={`px-4 py-2.5 font-bold text-sm border-b-2 flex items-center gap-2 transition-colors ${
                  activeTab === 'campus-schedule'
                    ? 'border-blue-700 text-blue-700'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <i className="fa-solid fa-calendar-days"></i>
                Campus Schedule
              </button>
            </div>

            {activeTab === 'dashboard' && (
              <LecturerDashboard
                user={user}
                rooms={rooms}
                bookings={lecturerAllBookings}
                onOpenDetails={(room) => setSelectedRoom(room)}
                onQuickBook={(room) => {
                  setSelectedRoom(room);
                  setIsBookingModalOpen(true);
                }}
                setActiveTab={setActiveTab}
              />
            )}

            {activeTab === 'find' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>
                    You can book any available lecture theatre or smaller
                    room for your classes. All bookings require Admin approval.
                  </p>
                </div>

                <SearchFilters
                  onApply={handleApplyFilters}
                  onReset={handleResetFilters}
                  activeCategory="all"
                />

                <RoomGrid
                  rooms={filteredRooms}
                  onOpenDetails={(room) => setSelectedRoom(room)}
                  onQuickBook={(room) => {
                    setSelectedRoom(room);
                    setIsBookingModalOpen(true);
                  }}
                  canBook={true}
                />
              </div>
            )}

            {activeTab === 'bookings' && (
              <div className="space-y-4">
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-check-circle mt-0.5"></i>
                  <p>
                    These are your officially approved classes.
                    Pending requests can be viewed on the Command Center.
                  </p>
                </div>

                <BookingsTable
                  bookings={lecturerApprovedBookings}
                  onCancel={handleCancelBooking}
                />
              </div>
            )}

            {activeTab === 'campus-schedule' && (
              <div className="space-y-4">
                <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>
                    View all officially approved lectures and classes
                    currently scheduled across the campus by other lecturers.
                  </p>
                </div>

                <BookingsTable
                  bookings={approvedBookings}
                  readOnly={true}
                />
              </div>
            )}
          </>
        ) : (
          <>
            {/* Student navigation */}
            <div className="flex border-b border-slate-200 mb-6 gap-2 sm:gap-6 overflow-x-auto pb-0.5">
              <button
                onClick={() => setActiveTab('lecture-rooms')}
                className={`px-4 py-2.5 font-semibold text-sm border-b-2 flex items-center gap-2 transition-colors ${
                  activeTab === 'lecture-rooms'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <i className="fa-solid fa-building-columns"></i>
                Lecture Rooms
              </button>

              <button
                onClick={() => setActiveTab('reading-rooms')}
                className={`px-4 py-2.5 font-semibold text-sm border-b-2 flex items-center gap-2 transition-colors ${
                  activeTab === 'reading-rooms'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <i className="fa-solid fa-book-open"></i>
                Book Reading Room
              </button>

              <button
                onClick={() => setActiveTab('schedule')}
                className={`px-4 py-2.5 font-semibold text-sm border-b-2 flex items-center gap-2 transition-colors ${
                  activeTab === 'schedule'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <i className="fa-solid fa-calendar-days"></i>
                Class Schedule
              </button>

              <button
                onClick={() => setActiveTab('bookings')}
                className={`px-4 py-2.5 font-semibold text-sm border-b-2 flex items-center gap-2 transition-colors ${
                  activeTab === 'bookings'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <i className="fa-solid fa-calendar-check"></i>
                My Reading Bookings
              </button>
            </div>

            {activeTab === 'lecture-rooms' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>
                    Students can view the status and class schedules of
                    large lecture theatres here. To reserve a space for
                    personal or group study, please use the{' '}
                    <strong>Book Reading Room</strong> tab.
                  </p>
                </div>

                <SearchFilters
                  onApply={handleApplyFilters}
                  onReset={handleResetFilters}
                  activeCategory="large"
                />

                <RoomGrid
                  rooms={filteredRooms.filter(
                    (room) => room.sizeCategory === 'large'
                  )}
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
                  <p>
                    You can request to book smaller lecture rooms and labs
                    for reading sessions. Requests are sent to the Admin
                    for approval.
                  </p>
                </div>

                <SearchFilters
                  onApply={handleApplyFilters}
                  onReset={handleResetFilters}
                  activeCategory="small"
                  maxCapacity={50}
                />

                <RoomGrid
                  rooms={filteredRooms.filter(
                    (room) => room.sizeCategory === 'small'
                  )}
                  onOpenDetails={(room) => setSelectedRoom(room)}
                  onQuickBook={(room) => {
                    setSelectedRoom(room);
                    setIsBookingModalOpen(true);
                  }}
                  canBook={true}
                />
              </div>
            )}

            {activeTab === 'schedule' && (
              <div className="space-y-6">
                <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 p-4 rounded-xl text-sm flex items-start gap-3">
                  <i className="fa-solid fa-circle-info mt-0.5"></i>
                  <p>
                    View all officially approved lectures and classes
                    currently scheduled across the campus.
                  </p>
                </div>

                <BookingsTable
                  bookings={approvedBookings}
                  readOnly={true}
                />
              </div>
            )}

            {activeTab === 'bookings' && (
              <BookingsTable
                bookings={bookings}
                onCancel={handleCancelBooking}
              />
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
          onClose={() => {
            setIsBookingModalOpen(false);
            setSelectedRoom(null);
          }}
          onConfirm={handleBookingConfirm}
        />
      )}

      <footer className="bg-slate-900 text-slate-400 text-xs py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p>
            © 2026 Obafemi Awolowo University Optispace System.
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;

