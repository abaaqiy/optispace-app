import { useState } from 'react';
import { loginUser, registerUser } from '../api';

const Login = ({ onLogin, adminOnly = false }) => {
  const [isLoginView, setIsLoginView] = useState(true);
  const [role, setRole] = useState(adminOnly ? 'admin' : 'student');

  // Form state
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [matricNumber, setMatricNumber] = useState('');
  const [staffId, setStaffId] = useState('');
  const [department, setDepartment] = useState('');

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRoleSwitch = (selectedRole) => {
    if (isSubmitting) return;

    setRole(selectedRole);
    setError('');
    setSuccess('');
    setEmail('');
    setPassword('');
    setConfirmPassword('');

    // Administrators cannot register publicly.
    if (selectedRole === 'admin') {
      setIsLoginView(true);
    }
  };

  const handleViewSwitch = () => {
    if (isSubmitting) return;

    setIsLoginView((previous) => !previous);
    setError('');
    setSuccess('');
    setPassword('');
    setConfirmPassword('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (isSubmitting) return;

    setError('');
    setSuccess('');
    setIsSubmitting(true);

    try {
      if (isLoginView) {
        const user = await loginUser(email.trim(), password);

        // Django supplies the authenticated account's actual role.
        setPassword('');
        onLogin(user);
        return;
      }

      if (role !== 'student' && role !== 'lecturer') {
        throw new Error('Administrators cannot register publicly.');
      }

      if (password !== confirmPassword) {
        throw new Error('Passwords do not match. Please enter the same password twice.');
      }

      const registrationData = {
        name: name.trim(),
        email: email.trim(),
        password,
        confirmPassword,
        department: department.trim(),
        role,
      };

      if (role === 'student') {
        registrationData.matricNumber = matricNumber.trim();
      } else {
        registrationData.staffId = staffId.trim();
      }

      const result = await registerUser(registrationData);

      // Registration creates an account, but does not sign it in.
      setPassword('');
      setConfirmPassword('');
      setEmail(email.trim());
      setIsLoginView(true);

      setSuccess(
        result.detail ||
          (result.requiresApproval
            ? 'Account created. Wait for administrator activation before signing in.'
            : 'Account created. You can now sign in.')
      );
    } catch (err) {
      setError(err.message || 'Unable to complete the request.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 p-4">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden">

        {/* Header */}
        <div className="bg-slate-900 p-8 text-center relative">
          <img
            src="/app-icon.jpg"
            alt="Optispace Logo"
            className="w-20 h-20 rounded-2xl mx-auto object-cover shadow-lg mb-4 bg-white border-2 border-slate-700"
          />

          <h1 className="text-2xl font-bold text-white">
            Optispace
          </h1>

          <p className="text-slate-400 text-xs mt-1">
            Obafemi Awolowo University
          </p>
        </div>

        {/* Role selector */}
        {role !== 'admin' && (
          <div className="flex border-b border-slate-200 bg-slate-50">
            {['student', 'lecturer'].map((r) => (
              <button
                key={r}
                type="button"
                disabled={isSubmitting}
                onClick={() => handleRoleSwitch(r)}
                className={`flex-1 py-3 text-xs font-bold capitalize transition-colors flex items-center justify-center gap-1.5 ${
                  role === r
                    ? 'text-blue-600 border-b-2 border-blue-600 bg-white'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
                }`}
              >
                <i
                  className={`fa-solid ${
                    r === 'student'
                      ? 'fa-graduation-cap'
                      : 'fa-chalkboard-user'
                  }`}
                ></i>

                {r}
              </button>
            ))}
          </div>
        )}

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="p-8 space-y-4 max-h-[65vh] overflow-y-auto"
        >
          <div className="text-center mb-4">
            <h2 className="text-lg font-bold text-slate-800">
              {isLoginView
                ? role === 'admin'
                  ? 'Admin Portal'
                  : 'Sign In to Your Account'
                : 'Create a New Account'}
            </h2>

            <p className="text-xs text-slate-500">
              {isLoginView
                ? 'Enter your credentials to access the system'
                : `Register as a ${role}`}
            </p>
          </div>

          {/* Error message */}
          {error && (
            <div
              role="alert"
              className="bg-rose-50 border border-rose-200 text-rose-700 p-3 rounded-lg text-xs font-medium flex items-start gap-2"
            >
              <i className="fa-solid fa-circle-exclamation mt-0.5"></i>
              <p className="whitespace-pre-line">{error}</p>
            </div>
          )}

          {/* Success message */}
          {success && (
            <div
              role="status"
              className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-3 rounded-lg text-xs font-medium flex items-start gap-2"
            >
              <i className="fa-solid fa-circle-check mt-0.5"></i>
              <p>{success}</p>
            </div>
          )}

          {/* Registration fields */}
          {!isLoginView && role !== 'admin' && (
            <>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Full Name
                </label>

                <div className="relative">
                  <i className="fa-solid fa-user absolute left-3 top-3 text-slate-400"></i>

                  <input
                    type="text"
                    required
                    disabled={isSubmitting}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., John Doe"
                    autoComplete="name"
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
                      type="text"
                      required
                      disabled={isSubmitting}
                      value={role === 'student' ? matricNumber : staffId}
                      onChange={(e) => {
                        if (role === 'student') {
                          setMatricNumber(e.target.value);
                        } else {
                          setStaffId(e.target.value);
                        }
                      }}
                      placeholder={
                        role === 'student'
                          ? 'CSC/2021/042'
                          : 'STF/CSC/001'
                      }
                      className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg pl-10 pr-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Department
                  </label>

                  <div className="relative">
                    <i className="fa-solid fa-building absolute left-3 top-3 text-slate-400"></i>

                    <input
                      type="text"
                      required
                      disabled={isSubmitting}
                      value={department}
                      onChange={(e) => setDepartment(e.target.value)}
                      placeholder="Computer Science"
                      className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg pl-10 pr-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Email Address
            </label>

            <div className="relative">
              <i className="fa-solid fa-envelope absolute left-3 top-3 text-slate-400"></i>

              <input
                type="email"
                required
                disabled={isSubmitting}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={
                  role === 'student'
                    ? 'john@student.oauife.edu.ng'
                    : 'j.smith@oauife.edu.ng'
                }
                autoComplete={isLoginView ? 'username' : 'email'}
                className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg pl-10 pr-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>

            <p className="text-[10px] text-slate-500 mt-1">
              {isLoginView
                ? 'Use your registered OAU email address.'
                : role === 'student'
                  ? 'Students must use an @student.oauife.edu.ng address.'
                  : 'Lecturers must use an @oauife.edu.ng address.'}
            </p>
          </div>

          <div>
            <label htmlFor="account-password" className="block text-xs font-bold text-slate-700 mb-1">
              Password
            </label>

            <div className="relative">
              <i className="fa-solid fa-lock absolute left-3 top-3 text-slate-400"></i>

              <input
                id="account-password"
                type="password"
                required
                disabled={isSubmitting}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete={
                  isLoginView ? 'current-password' : 'new-password'
                }
                className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg pl-10 pr-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          </div>

          {!isLoginView && role !== 'admin' && (
            <div>
              <label htmlFor="confirm-password" className="block text-xs font-bold text-slate-700 mb-1">
                Confirm Password
              </label>
              <div className="relative">
                <i className="fa-solid fa-lock absolute left-3 top-3 text-slate-400"></i>
                <input
                  id="confirm-password"
                  type="password"
                  required
                  disabled={isSubmitting}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Enter your password again"
                  autoComplete="new-password"
                  className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg pl-10 pr-3 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 mt-4 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <i
              className={`fa-solid ${
                isLoginView ? 'fa-right-to-bracket' : 'fa-user-plus'
              }`}
            ></i>

            {isSubmitting
              ? isLoginView
                ? 'Signing in...'
                : 'Creating account...'
              : isLoginView
                ? `Sign In${
                    role === 'admin'
                      ? ''
                      : ` as ${role.charAt(0).toUpperCase() + role.slice(1)}`
                  }`
                : 'Create Account'}
          </button>

          {/* Login / registration switch */}
          {role !== 'admin' && (
            <div className="text-center mt-4 border-t border-slate-100 pt-4">
              <p className="text-xs text-slate-600">
                {isLoginView
                  ? "Don't have an account? "
                  : 'Already have an account? '}

                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={handleViewSwitch}
                  className="font-bold text-blue-600 hover:underline cursor-pointer"
                >
                  {isLoginView ? 'Register here' : 'Sign in here'}
                </button>
              </p>
            </div>
          )}
        </form>


      </div>
    </div>
  );
};

export default Login;

