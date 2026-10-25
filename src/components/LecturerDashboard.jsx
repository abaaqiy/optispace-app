import RoomGrid from './RoomGrid';

export default function LecturerDashboard({ user, rooms, onOpenDetails, setActiveTab }) {
  return (
    <div className="space-y-6">
      <div className="rounded-2xl p-8 bg-blue-900 text-white shadow-lg flex flex-col sm:flex-row items-start justify-between gap-4">
        <div>
          <h1 className="font-bold text-2xl">Welcome back, {user.name}</h1>
          <p className="text-blue-100 mt-2 text-sm">View room availability and the campus timetable.</p>
        </div>
        <button onClick={() => setActiveTab('find')} className="px-5 py-2.5 text-sm rounded-xl bg-white text-blue-900 font-bold">Find a Room</button>
      </div>
      <RoomGrid rooms={rooms} onOpenDetails={onOpenDetails} />
    </div>
  );
}
