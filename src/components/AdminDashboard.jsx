import RoomGrid from './RoomGrid';
import ReservationsPanel from './ReservationsPanel';

const adminLinks = [
  { label: 'Manage Buildings', path: 'rooms/building/' },
  { label: 'Manage Courses', path: 'scheduling/course/' },
  { label: 'Manage Reservations', path: 'bookings/reservation/' },
  {
    label: 'Manage Rooms',
    path: 'rooms/room/',
  },
  {
    label: 'Manage Facilities',
    path: 'rooms/facility/',
  },
  {
    label: 'Manage Timetable Days',
    path: 'scheduling/timetableday/',
  },
  {
    label: 'Manage Lecture Allocations',
    path: 'scheduling/allocation/',
  },
  {
    label: 'Manage Users / Activate Lecturers',
    path: 'accounts/user/',
  },
];

const AdminDashboard = ({ rooms, onOpenDetails, onReservationChanged }) => {
  return (
    <div className="space-y-6">
      <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 mb-3">
          Administration
        </h2>

        <p className="text-sm text-slate-600 mb-4">
          Add rooms, facilities, and lecture times through Django admin.
          Publish each day's timetable after checking its coverage and sessions.
          Students see availability from those published schedules.
        </p>

        <div className="flex flex-wrap gap-3">
          {adminLinks.map((link) => (
            <a
              key={link.path}
              href={`/admin/${link.path}`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-bold hover:bg-blue-700"
            >
              {link.label}
            </a>
          ))}
        </div>
      </section>

      <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 mb-2">
          Booking Approvals
        </h2>

        <p className="text-sm text-slate-600">
          Review student and lecturer requests. Approval checks the room's timetable and existing reservations again.
        </p>
        <div className="mt-4"><ReservationsPanel admin onChanged={onReservationChanged} /></div>
      </section>

      {rooms && <section>
        <h2 className="text-lg font-bold text-slate-900 mb-4">
          Room Overview
        </h2>

        <RoomGrid
          rooms={rooms}
          onOpenDetails={onOpenDetails}
          canBook={false}
        />
      </section>}
    </div>
  );
};

export default AdminDashboard;

