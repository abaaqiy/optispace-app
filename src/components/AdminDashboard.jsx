import RoomGrid from './RoomGrid';

const adminLinks = [
  { label: 'Manage Reservations', path: 'bookings/reservation/' },
  { label: 'Manage Buildings', path: 'rooms/building/' },
  { label: 'Manage Courses', path: 'scheduling/course/' },
  {
    label: 'Manage Rooms',
    path: 'rooms/room/',
  },
  {
    label: 'Manage Facilities',
    path: 'rooms/facility/',
  },
  {
    label: 'Manage Timetables',
    path: 'scheduling/timetableday/',
  },
  {
    label: 'Import Timetable CSV',
    path: 'scheduling/timetableday/import/',
  },
  {
    label: 'Import Timetable Image',
    path: 'scheduling/timetableday/import-document/',
  },
  {
    label: 'Manage Users / Activate Lecturers',
    path: 'accounts/user/',
  },
];

const AdminDashboard = ({ rooms, onOpenDetails }) => {
  return (
    <div className="space-y-6">
      <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 mb-3">
          Administration
        </h2>

        <p className="text-sm text-slate-600 mb-4">
          Add rooms, facilities, and lecture times through Django admin.
          Add classes individually or import a school timetable from CSV or a lecture timetable image. Select Cancelled to release a class's time slot.
          Saved timetables immediately determine room availability.
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

      {rooms && <section>
        <h2 className="text-lg font-bold text-slate-900 mb-4">
          Room Overview
        </h2>

        <RoomGrid
          rooms={rooms}
          onOpenDetails={onOpenDetails}
        />
      </section>}
    </div>
  );
};

export default AdminDashboard;

