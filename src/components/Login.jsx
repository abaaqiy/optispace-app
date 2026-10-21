import React, { useState } from 'react';

const Login = ({ onLogin }) => {
  const [isLoginView, setIsLoginView] = useState(true);
  const [role, setRole] = useState('student');
  
  // Form State
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [matricNumber, setMatricNumber] = useState(''); 
  const [staffId, setStaffId] = useState(''); 
  const [department, setDepartment] = useState('');
  const [error, setError] = useState('');

  // Simulated Database
  const [registeredUsers, setRegisteredUsers] = useState([
    { email: 'student@student.oauife.edu.ng', password: 'password123', name: 'John Doe', id: 'CSC/2023/001', department: 'Computer Science', role: 'student' },
    { email: 'lecturer@oauife.edu.ng', password: 'password123', name: 'Dr. Smith', id: 'STF/CSC/002', department: 'Computer Science', role: 'lecturer' }
  ]);

  const handleRoleSwitch = (selectedRole) => {
    setRole(selectedRole);
    setError('');
    if (isLoginView) {
      if (selectedRole === 'student') {
        setEmail('student@student.oauife.edu.ng');
        setPassword('password123');
      } else if (selectedRole === 'lecturer') {
        setEmail('lecturer@oauife.edu.ng');
        setPassword('password123');
      } else {
        setEmail('admin@oauife.edu.ng');
        setPassword('admin123');
      }
    } else {
      setEmail('');
      setPassword('');
    }
  };

  useState(() => {
    handleRoleSwitch('student');
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    // --- VALIDATION LOGIC ---
    if (role === 'student' && !email.endsWith('@student.oauife.edu.ng')) {
      return setError('Students must use a valid @student.oauife.edu.ng email address.');
    }
    if (role === 'lecturer' && !email.endsWith('@oauife.edu.ng')) {
      return setError('Lecturers must use a valid @oauife.edu.ng email address.');
    }

    if (isLoginView) {
      // --- LOGIN LOGIC ---
      if (role === 'admin') {
        if (email === 'admin@oauife.edu.ng' && password === 'admin123') {
          onLogin({ role: 'admin', name: 'System Admin', id: 'ADMIN/ICT/001', department: 'ICT' });
        } else {
          setError('Invalid Admin credentials.');
        }
        return;
      }

      const user = registeredUsers.find(u => u.email === email && u.password === password && u.role === role);
      if (user) {
        onLogin(user);
      } else {
        setError('Invalid email or password. Please try again or create an account.');
      }
    } else {
      // --- REGISTRATION LOGIC ---
      if (!name || !department) return setError('Please fill in all required fields.');
      if (role === 'student' && !matricNumber) return setError('Please enter your Matric Number.');
      if (role === 'lecturer' && !staffId) return setError('Please enter your Staff ID.');

      const userExists = registeredUsers.some(u => u.email === email);
      if (userExists) return setError('An account with this email already exists.');

      const newUser = {
        email, password, name, department,
        id: role === 'student' ? matricNumber : staffId, role
      };

      setRegisteredUsers([...registeredUsers, newUser]);
      onLogin(newUser);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 p-4">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden">
        
        {/* Header Section with App Icon (JPG) */}
        <div className="bg-slate-900 p-8 text-center relative">
          <img 
            src="/app-icon.jpg" 
            alt="Optispace Logo" 
            className="w-20 h-20 rounded-2xl mx-auto object-cover shadow-lg mb-4 bg-white border-2 border-slate-700"
          />
          <h1 className="text-2xl font-bold text-white">Optispace</h1>
          <p className="text-slate-400 text-xs mt-1">Obafemi Awolowo University</p>
        </div>

        {/* Role Selector */}
        {role !== 'admin' && (
          <div className="flex border-b border-slate-200 bg-slate-50">
            {['student', 'lecturer'].map((r) => (
              <button
                key={r}
                onClick={() => handleRoleSwitch(r)}
                className={`flex-1 py-3 text-xs font-bold capitalize transition-colors flex items-center justify-center gap-1.5 ${
                  role === r 
                    ? 'text-blue-600 border-b-2 border-blue-600 bg-white' 
                    : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
                }`}
              >
                <i className={`fa-solid ${r === 'student' ? 'fa-graduation-cap' : 'fa-chalkboard-user'}`}></i>
                {r}
              </button>
            ))}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-8 space-y-4 max-h-[65vh] overflow-y-auto">
          
          <div className="text-center mb-4">
            <h2 className="text-lg font-bold text-slate-800">
              {isLoginView ? (role === 'admin' ? 'Admin Portal' : 'Sign In to Your Account') : 'Create a New Account'}
            </h2>
            <p className="text-xs text-slate-500">
              {isLoginView ? 'Enter your credentials to access the system' : `Register as a ${role}`}
            </p>
          </div>

          {error && (
            <div className="bg-rose-50 border border-rose-200 text-rose-700 p-3 rounded-lg text-xs font-medium flex items-start gap-2">
              <i className="fa-solid fa-circle-exclamation mt-0.5"></i>
              <p>{error}</p>
            </div>
          )}

          {/* REGISTRATION ONLY FIELDS */}
          {!isLoginView && role !== 'admin' && (
            <>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Full Name</label>
                <div className="relative">
                  <i className="fa-solid fa-user absolute left-3 top-3 text-slate-400"></i>
                  <input 
                    type="text" required value={name} onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., John Doe"
                    className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg pl-10 pr-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none" 
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    {role === 'student' ? 'Matric Number' : 'Staff ID'}
                  </label>
                  <div className="relative">
                    <i className="fa-solid fa-id-card absolute left-3 top-3 text-slate-400"></i>
                    <input 
                      type="text" required 
                      value={role === 'student' ? matricNumber : staffId} 
                      onChange={(e) => role === 'student' ? setMatricNumber(e.target.value) : setStaffId(e.target.value)}
                      placeholder={role === 'student' ? "CSC/2021/042" : "STF/CSC/001"}
                      className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg pl-10 pr-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none" 
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Department</label>
                  <div className="relative">
                    <i className="fa-solid fa-building absolute left-3 top-3 text-slate-400"></i>
                    <input 
                      type="text" required value={department} onChange={(e) => setDepartment(e.target.value)}
                      placeholder="Computer Science"
                      className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg pl-10 pr-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none" 
                    />
                  </div>
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">Email Address</label>
            <div className="relative">
              <i className="fa-solid fa-envelope absolute left-3 top-3 text-slate-400"></i>
              <input 
                type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder={role === 'student' ? "john@student.oauife.edu.ng" : "j.smith@oauife.edu.ng"}
                className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg pl-10 pr-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none" 
              />
            </div>
            {role !== 'admin' && (
              <p className="text-[10px] text-slate-500 mt-1">
                {role === 'student' ? 'Must be a @student.oauife.edu.ng address.' : 'Must be an @oauife.edu.ng address.'}
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">Password</label>
            <div className="relative">
              <i className="fa-solid fa-lock absolute left-3 top-3 text-slate-400"></i>
              <input 
                type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg pl-10 pr-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none" 
              />
            </div>
          </div>

          <button 
            type="submit" 
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 mt-4 cursor-pointer"
          >
            <i className={`fa-solid ${isLoginView ? 'fa-right-to-bracket' : 'fa-user-plus'}`}></i> 
            {isLoginView ? `Sign In${role === 'admin' ? '' : ` as ${role.charAt(0).toUpperCase() + role.slice(1)}`}` : 'Create Account'}
          </button>

          {/* Toggle View - HIDDEN IF ADMIN */}
          {role !== 'admin' && (
            <div className="text-center mt-4 border-t border-slate-100 pt-4">
              <p className="text-xs text-slate-600">
                {isLoginView ? "Don't have an account? " : "Already have an account? "}
                <button 
                  type="button"
                  onClick={() => {
                    setIsLoginView(!isLoginView);
                    setError('');
                    if (isLoginView) setEmail(''); 
                  }}
                  className="font-bold text-blue-600 hover:underline cursor-pointer"
                >
                  {isLoginView ? 'Register here' : 'Sign in here'}
                </button>
              </p>
            </div>
          )}

        </form>

        {/* Admin Backdoor / Return to User Login */}
        <div className="text-center pb-4">
           <button 
             onClick={() => { 
               if (role === 'admin') {
                 handleRoleSwitch('student');
               } else {
                 setRole('admin'); 
                 setEmail('admin@oauife.edu.ng'); 
                 setPassword('admin123'); 
                 setIsLoginView(true); 
               }
             }}
             className="text-[10px] text-slate-400 hover:text-slate-600 underline"
           >
             {role === 'admin' ? 'Return to Student/Lecturer Login' : 'Switch to Admin Login'}
           </button>
        </div>
      </div>
    </div>
  );
};

export default Login;