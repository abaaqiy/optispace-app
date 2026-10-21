import React from 'react';

const Header = ({ user, onLogout, stats }) => {
  const isStudent = user.role === 'student';
  const isAdmin = user.role === 'admin';

  // Get initials for the avatar
  const getInitials = (name) => {
    return name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
  };

  return (
    <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-30 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* Logo Section */}
          <div className="flex items-center gap-3">
            {/* APP ICON IMAGE (JPG) */}
            <img 
              src="/app-icon.jpg" 
              alt="Optispace Logo" 
              className="h-10 w-10 rounded-xl object-cover shadow-sm bg-white border border-slate-700"
            />
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-lg sm:text-xl tracking-tight text-white">Optispace</h1>
                <span className="bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs px-2 py-0.5 rounded-full font-medium hidden sm:inline-block">OAU Edition</span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">Real-time Lecture Room & Venue Availability</p>
            </div>
          </div>

          {/* User Profile & Logout */}
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-3 pr-3 border-r border-slate-800">
              <div className={`w-10 h-10 rounded-full font-bold flex items-center justify-center text-sm shadow-sm ${isStudent ? 'bg-amber-500 text-slate-950' : isAdmin ? 'bg-rose-600 text-white' : 'bg-blue-600 text-white'}`}>
                {getInitials(user.name)}
              </div>
              <div className="text-xs">
                <p className="font-bold text-white text-sm">{user.name}</p>
                <div className="text-slate-400 text-[11px] flex items-center gap-1.5 mt-0.5">
                  <span className="capitalize">{user.department || user.role}</span>
                  <span className="text-slate-600">•</span>
                  <span className="font-mono bg-slate-800 px-1.5 py-0.5 rounded text-slate-300 border border-slate-700">{user.id}</span>
                </div>
              </div>
            </div>

            <button 
              onClick={onLogout}
              className="px-3 py-1.5 bg-slate-800 hover:bg-rose-600 text-slate-300 hover:text-white rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <i className="fa-solid fa-arrow-right-from-bracket"></i> Logout
            </button>
          </div>
        </div>
      </div>

      {/* Stats Banner */}
      <div className="bg-slate-950/60 border-t border-slate-800/80 py-2.5 px-4 sm:px-6">
        <div className="max-w-7xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-3 text-center sm:text-left">
          <div className="flex items-center justify-center sm:justify-start gap-2.5">
            <div className="p-1.5 bg-blue-500/10 text-blue-400 rounded-md"><i className="fa-solid fa-door-open text-sm"></i></div>
            <div><span className="text-xs text-slate-400 block">Total Capacity</span><span className="text-sm font-bold text-slate-200">{stats.total} Venues</span></div>
          </div>
          <div className="flex items-center justify-center sm:justify-start gap-2.5">
            <div className="p-1.5 bg-emerald-500/10 text-emerald-400 rounded-md"><i className="fa-solid fa-circle-check text-sm"></i></div>
            <div><span className="text-xs text-slate-400 block">Available Now</span><span className="text-sm font-bold text-emerald-400">{stats.available} Venues</span></div>
          </div>
          <div className="flex items-center justify-center sm:justify-start gap-2.5">
            <div className="p-1.5 bg-rose-500/10 text-rose-400 rounded-md"><i className="fa-solid fa-clock text-sm"></i></div>
            <div><span className="text-xs text-slate-400 block">Occupied / Lecture</span><span className="text-sm font-bold text-rose-400">{stats.occupied} Venues</span></div>
          </div>
          <div className="flex items-center justify-center sm:justify-start gap-2.5">
            <div className="p-1.5 bg-amber-500/10 text-amber-400 rounded-md"><i className="fa-solid fa-hourglass-half text-sm"></i></div>
            <div><span className="text-xs text-slate-400 block">Occupied Soon</span><span className="text-sm font-bold text-amber-400">{stats.soon} Venues</span></div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;