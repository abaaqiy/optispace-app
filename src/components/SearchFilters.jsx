import { useState } from 'react';
import { getLagosDateTime } from '../api';

function makeDefaults() {
  return {
    ...getLagosDateTime(),
    zone: 'all',
    capacity: 30,
    facilities: [],
    availableOnly: false,
  };
}

const SearchFilters = ({
  onApply,
  onReset,
  initialValues,
  zones = [],
  activeCategory = 'all',
  maxCapacity = 1000,
  disabled = false,
}) => {
  const [form, setForm] = useState(
    () => initialValues || makeDefaults()
  );

  const updateField = (field, value) => {
    setForm((previous) => ({
      ...previous,
      [field]: value,
    }));
  };

  const handleFacilityChange = (facility) => {
    setForm((previous) => ({
      ...previous,
      facilities: previous.facilities.includes(facility)
        ? previous.facilities.filter((item) => item !== facility)
        : [...previous.facilities, facility],
    }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    onApply({
      ...form,
      capacity: Number(form.capacity),
    });
  };

  const handleReset = () => {
    const defaults = makeDefaults();

    setForm(defaults);
    onReset(defaults);
  };

  const buttonText =
    activeCategory === 'large'
      ? 'Search Lecture Rooms'
      : activeCategory === 'small'
        ? 'Search Smaller Rooms'
        : 'Search Rooms';

  return (
    <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-100">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <i className="fa-solid fa-sliders text-blue-600"></i>
            Room Availability Search
          </h2>

          <p className="text-xs text-slate-500 mt-1">
            Check timetable availability at a selected date and time.
          </p>
        </div>

        <button
          type="button"
          disabled={disabled}
          onClick={handleReset}
          className="text-xs font-semibold text-slate-500 hover:text-blue-600 flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-50"
        >
          <i className="fa-solid fa-rotate-right"></i>
          Reset to current time
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Faculty / Zone
            </label>

            <select
              value={form.zone}
              disabled={disabled}
              onChange={(event) => updateField('zone', event.target.value)}
              className="w-full bg-slate-50 border border-slate-300 text-xs rounded-lg px-3 py-2.5"
            >
              <option value="all">All Campus Zones</option>

              {zones.map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Target Date
            </label>

            <input
              type="date"
              required
              disabled={disabled}
              value={form.date}
              onChange={(event) => updateField('date', event.target.value)}
              className="w-full bg-slate-50 border border-slate-300 text-xs rounded-lg px-3 py-2.5"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Time — Africa/Lagos
            </label>

            <input
              type="time"
              required
              step="60"
              disabled={disabled}
              value={form.time}
              onChange={(event) => updateField('time', event.target.value)}
              className="w-full bg-slate-50 border border-slate-300 text-xs rounded-lg px-3 py-2.5"
            />
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-bold text-slate-700">
                Minimum Capacity
              </label>

              <span className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                {form.capacity} seats
              </span>
            </div>

            <input
              type="range"
              min="20"
              max={maxCapacity}
              step="10"
              disabled={disabled}
              value={form.capacity}
              onChange={(event) =>
                updateField('capacity', Number(event.target.value))
              }
              className="w-full h-2 bg-slate-200 rounded-lg accent-blue-600 mt-2"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 mb-2">
            Required Facilities
          </label>

          <div className="flex flex-wrap gap-2">
            {['ac', 'projector', 'power', 'audio', 'wifi'].map((facility) => (
              <label
                key={facility}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-slate-300 text-xs"
              >
                <input
                  type="checkbox"
                  disabled={disabled}
                  checked={form.facilities.includes(facility)}
                  onChange={() => handleFacilityChange(facility)}
                />

                {facility.toUpperCase()}
              </label>
            ))}
          </div>
        </div>

        <label className="flex items-center gap-2 text-xs text-slate-700">
          <input
            type="checkbox"
            disabled={disabled}
            checked={form.availableOnly}
            onChange={(event) =>
              updateField('availableOnly', event.target.checked)
            }
          />

          Show only rooms free according to the timetable at that time
        </label>

        <div className="flex justify-end pt-3 border-t border-slate-100">
          <button
            type="submit"
            disabled={disabled}
            className="w-full sm:w-auto px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm rounded-xl shadow-md flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <i className="fa-solid fa-magnifying-glass"></i>
            {disabled ? 'Loading rooms...' : buttonText}
          </button>
        </div>
      </form>
    </section>
  );
};

export default SearchFilters;

