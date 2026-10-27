import { useEffect } from 'react';

const Toast = ({ message, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className="bg-slate-900 text-white border border-slate-700 px-4 py-2.5 rounded-xl text-xs shadow-xl flex items-center gap-2 mb-2 pointer-events-auto">
      <i className="fa-solid fa-circle-info text-amber-400"></i> 
      <span>{message}</span>
    </div>
  );
};
export default Toast;
