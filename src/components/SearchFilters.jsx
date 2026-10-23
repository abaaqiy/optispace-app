import React, { useState } from 'react';

// Added maxCapacity prop with a default of 1000
const SearchFilters = ({ onApply, onReset, activeCategory = 'large', maxCapacity = 1000 }) => {
  const [zone, setZone] = useState('all');
  const [capacity, setCapacity] = useState(30);
  const [facilities, setFacilities] = useState([]);

  const handleFacilityChange = (val) => {
    setFacilities(prev => prev.includes(val) ? prev.filter(f => f !== val) : [...prev, val]);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onApply({ zone, capacity, facilities });
  };

  const handleReset = () => {
    setZone('all');
    setCapacity(30);
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
            Filter available spaces within the Faculty
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
            <select value={zone} onChange={(e) => setZone(e.target.value)} className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-xs rounded-lg px-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none">
              <option value="all">All Campus Zones</option>
              <option value="Faculty of Computing & Engineering">Faculty of Computing & Engineering</option>
            </select>
          </div>
          
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">Target Date</label>
            <input type="date" className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-xs rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none" defaultValue={new Date().toISOString().split('T')[0]} />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">Time Window</label>
            <select className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-xs rounded-lg px-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none">
              <option>Now (Next 2 Hours)</option>
              <option>Morning (8:00 AM - 12:00 PM)</option>
              <option>Afternoon (12:00 PM - 4:00 PM)</option>
            </select>
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-bold text-slate-700">Min Capacity</label>
              <span className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">{capacity} Seats</span>
            </div>
            {/* DYNAMIC MAX CAPACITY */}
            <input 
              type="range" 
              min="20" 
              max={maxCapacity} 
              step="10" 
              value={capacity} 
              onChange={(e) => setCapacity(e.target.value)} 
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600 mt-2" 
            />
          </div>
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
