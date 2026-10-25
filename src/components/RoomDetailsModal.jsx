const facilityMap = {
  ac: {
    icon: 'fa-snowflake',
    label: 'Air Conditioning',
  },
  projector: {
    icon: 'fa-video',
    label: 'Projector',
  },
  power: {
    icon: 'fa-plug',
    label: 'Power Supply',
  },
  audio: {
    icon: 'fa-microphone',
    label: 'Sound System',
  },
  wifi: {
    icon: 'fa-wifi',
    label: 'Campus Wi-Fi',
  },
};

const RoomDetailsModal = ({
  room,
  onClose,
  onBook,
  canBook = false,
}) => {
  if (!room) return null;

  const facilities = room.facilities || [];
  const schedule = room.hourlySchedule || [];

  const selectedMoment = room.availabilityAt
    ? new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Africa/Lagos',
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(room.availabilityAt))
    : 'Not specified';

  return (
    <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-40 flex items-center justify-center p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="room-details-title"
        className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
      >
        <div className="flex justify-between items-start mb-4 pb-3 border-b border-slate-100">
          <div>
            <h3
              id="room-details-title"
              className="text-lg font-bold text-slate-900"
            >
              {room.name}
            </h3>

            <p className="text-xs text-slate-500">
              {room.zone}{room.building ? ` · ${room.building.name}` : ''}{room.roomNumber ? ` · ${room.roomNumber}` : ''}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close room details"
            className="text-slate-500 bg-slate-100 p-2 rounded-full"
          >
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>

        <div className="space-y-5 text-xs">
          <div className="grid grid-cols-2 gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200">
            <div>
              <p className="text-slate-500">Capacity</p>
              <p className="font-bold text-sm">
                {room.capacity} seats
              </p>
            </div>

            <div>
              <p className="text-slate-500">Room type</p>
              <p className="font-bold text-sm">{room.type}</p>
            </div>
          </div>

          <div className="rounded-lg bg-blue-50 border border-blue-100 p-3">
            <p className="font-bold">
              Selected moment: {selectedMoment} — Africa/Lagos
            </p>

            <p className="mt-1">{room.statusText}</p>

            <p className="mt-2 text-slate-600">
              Based on published timetables and approved reservations. Physical use may differ.
            </p>
          </div>

          <div>
            <h4 className="font-bold text-slate-800 mb-2">
              Facilities
            </h4>

            <div className="flex flex-wrap gap-2">
              {facilities.length > 0 ? (
                facilities.map((facility) => {
                  const info = facilityMap[facility] || {
                    icon: 'fa-check',
                    label: facility,
                  };

                  return (
                    <span
                      key={facility}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-50 border border-slate-200"
                    >
                      <i className={`fa-solid ${info.icon}`}></i>
                      {info.label}
                    </span>
                  );
                })
              ) : (
                <p className="text-slate-500">
                  No facilities have been listed.
                </p>
              )}
            </div>
          </div>

          <div>
            <h4 className="font-bold text-slate-800 mb-2">
              Timetable and reservations for the selected date
            </h4>

            {schedule.length === 0 ? (
              <p className="rounded-lg bg-slate-50 p-3 text-slate-600">
                No published timetable is available for this date.
                Do not assume the room is free.
              </p>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {schedule.map((slot, index) => (
                  <div
                    key={`${slot.time}-${index}`}
                    className={`flex justify-between gap-3 p-2 rounded-lg border ${
                      slot.reserved ? 'bg-indigo-50 border-indigo-100 text-indigo-900' : slot.occupied
                        ? 'bg-rose-50 border-rose-100 text-rose-900'
                        : 'bg-emerald-50 border-emerald-100 text-emerald-900'
                    }`}
                  >
                    <span className="font-mono whitespace-nowrap">
                      {slot.time}
                    </span>

                    <span>{slot.event}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 pt-3 border-t border-slate-100 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2.5 bg-slate-100 text-slate-700 font-semibold text-xs rounded-xl"
          >
            Close
          </button>

          {canBook && (
            <button
              type="button"
              onClick={() => onBook(room)}
              className="px-6 py-2.5 bg-blue-600 text-white font-bold text-xs rounded-xl"
            >
              Reserve Room
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default RoomDetailsModal;

