import { useState } from 'react';
import { getLagosDateTime } from '../api';

const SearchFilters = ({ onApply, onReset, activeCategory = 'all', zones = [] }) => {
  const [zone, setZone] = useState('all');
  const [capacity, setCapacity] = useState('');
  const [facilities, setFacilities] = useState([]);
  const [moment, setMoment] = useState(getLagosDateTime);
  const [useCurrentTime, setUseCurrentTime] = useState(true);
  const [status, setStatus] = useState('all');

  const handleFacilityChange = (val) => {
    setFacilities(prev => prev.includes(val) ? prev.filter(f => f !== val) : [...prev, val]);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onApply({ zone, capacity, facilities, status, ...(useCurrentTime ? {} : moment) });
  };

  const handleReset = () => {
    setZone('all');
    setCapacity('');
    setStatus('all');
    setUseCurrentTime(true);
    setMoment(getLagosDateTime());
    setFacilities([]);
    onReset();
  };

  let buttonText = "Search Rooms";
  if (activeCategory === 'large') buttonText = "Search Lecture Rooms";
  if (activeCategory === 'small') buttonText = "Search Reading Rooms";

  return (
    <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4 sm:p-6 transition-all">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-100">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <i className="fa-solid fa-sliders text-blue-600"></i> Room Availability Search Filter
          </h2>
          <p className="text-xs text-slate-500">
            Find suitable spaces across Obafemi Awolowo University, Ile-Ife
          </p>
        </div>
        
        <button 
          onClick={handleReset} 
          className="text-xs font-semibold text-slate-500 hover:text-blue-600 self-start sm:self-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <i className="fa-solid fa-rotate-right"></i> Reset Filters
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">Faculty / Zone</label>
            <select aria-label="Faculty / Zone" value={zone} onChange={(e) => setZone(e.target.value)} className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-xs rounded-lg px-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none">
              <option value="all">All Campus Zones</option>
              {zones.map(value => <option key={value} value={value}>{value}</option>)}
            </select>
          </div>
          
          <div>
            <label htmlFor="room-search-date" className="block text-xs font-bold text-slate-700 mb-1">Target Date (Lagos)</label>
            <input id="room-search-date" type="date" required disabled={useCurrentTime} value={moment.date}
              onChange={event => setMoment({ ...moment, date: event.target.value })}
              className="w-full bg-slate-50 border border-slate-300 text-xs rounded-lg px-3 py-2.5 disabled:opacity-50" />
          </div>
          <div>
            <label htmlFor="room-search-time" className="block text-xs font-bold text-slate-700 mb-1">Time (Lagos)</label>
            <input id="room-search-time" type="time" required disabled={useCurrentTime} value={moment.time}
              onChange={event => setMoment({ ...moment, time: event.target.value })}
              className="w-full bg-slate-50 border border-slate-300 text-xs rounded-lg px-3 py-2.5 disabled:opacity-50" />
          </div>
          <div>
            <label htmlFor="room-search-capacity" className="block text-xs font-bold text-slate-700 mb-1">Minimum Capacity</label>
            <input id="room-search-capacity" type="number" min="1" step="1" value={capacity}
              onChange={event => setCapacity(event.target.value)} placeholder="Any capacity"
              className="w-full bg-slate-50 border border-slate-300 text-xs rounded-lg px-3 py-2.5" />
          </div>
        </div>

        <div className="flex flex-wrap gap-5 items-center text-xs">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={useCurrentTime} onChange={event => {
              setUseCurrentTime(event.target.checked);
              setMoment(getLagosDateTime());
            }} /> Use current date and time
          </label>
          <label className="flex items-center gap-2">Availability
            <select aria-label="Availability" value={status} onChange={event => setStatus(event.target.value)} className="p-2 rounded-lg border border-slate-300 bg-slate-50">
              <option value="all">All statuses</option>
              <option value="available">Available</option>
              <option value="occupied">Occupied</option>
              <option value="reserved">Reserved</option>
              <option value="soon">Occupied soon</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
        </div>
        <div className="pt-2">
          <label className="block text-xs font-bold text-slate-700 mb-2">Required Room Facilities</label>
          <div className="flex flex-wrap gap-2">
            {['ac', 'projector', 'power', 'audio', 'wifi'].map(fac => (
              <label 
                key={fac} 
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium cursor-pointer transition-all ${
                  facilities.includes(fac) 
                    ? 'bg-blue-50 border-blue-500 text-blue-700' 
                    : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100'
                }`}
              >
                <input type="checkbox" checked={facilities.includes(fac)} onChange={() => handleFacilityChange(fac)} className="rounded text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
                {fac.toUpperCase()}
              </label>
            ))}
          </div>
        </div>

        <div className="flex justify-end pt-3 border-t border-slate-100">
          <button 
            type="submit" 
            className="w-full sm:w-auto px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm rounded-xl shadow-md border border-blue-700 transition-all flex items-center justify-center gap-2 cursor-pointer"
          >
            <i className="fa-solid fa-magnifying-glass"></i> {buttonText}
          </button>
        </div>
      </form>
    </section>
  );
};
export default SearchFilters;
