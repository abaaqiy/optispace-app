const badgeStyles = {
  available: 'bg-emerald-100 text-emerald-800',
  occupied: 'bg-rose-100 text-rose-800',
  soon: 'bg-amber-100 text-amber-800',
  unknown: 'bg-slate-200 text-slate-700',
};

const badgeLabels = {
  available: 'Timetable-free',
  occupied: 'Scheduled',
  soon: 'Needed soon',
  unknown: 'Unknown',
};

const RoomGrid = ({
  rooms,
  onOpenDetails,
  onQuickBook,
  canBook = false,
}) => {
  if (rooms.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center">
        <h4 className="font-bold text-slate-800">
          No rooms to display
        </h4>

        <p className="text-xs text-slate-500 mt-2">
          Check your filters and whether rooms have been added to the database.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {rooms.map((room) => {
        const status = badgeLabels[room.status]
          ? room.status
          : 'unknown';

        return (
          <div
            key={room.id}
            className="bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between overflow-hidden"
          >
            <div className="p-5">
              <div className="flex items-start justify-between gap-2 mb-2">
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                    {room.zone}
                  </span>

                  <h4 className="font-bold text-slate-900 text-base">
                    {room.name}
                  </h4>
                </div>

                <span
                  className={`text-[10px] font-bold px-2.5 py-1 rounded-full ${badgeStyles[status]}`}
                >
                  {badgeLabels[status]}
                </span>
              </div>

              <p className="text-xs text-slate-500 mb-4">
                <i className="fa-solid fa-chair mr-1"></i>
                {room.capacity} capacity · {room.type}
              </p>

              <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 text-xs space-y-1">
                <p className="font-medium text-slate-800">
                  <i className="fa-solid fa-clock mr-1"></i>
                  {room.statusText || 'Timetable information unavailable'}
                </p>

                <p className="text-slate-500">
                  Next: {room.nextSchedule || 'Not known'}
                </p>
              </div>
            </div>

            <div className="bg-slate-50 px-5 py-3 border-t border-slate-200 flex justify-between">
              <button
                type="button"
                onClick={() => onOpenDetails(room)}
                className="px-3 py-2 text-xs font-bold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-100"
              >
                <i className="fa-solid fa-circle-info mr-1"></i>
                Details
              </button>

              {canBook && (
                <button
                  type="button"
                  onClick={() => onQuickBook(room)}
                  className="px-4 py-2 text-xs font-bold text-white bg-blue-600 rounded-lg"
                >
                  Book
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default RoomGrid;

