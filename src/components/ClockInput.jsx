import { useState } from 'react';
import { formatClock, parseClock } from '../clock';

export default function ClockInput({ value, onChange, ...props }) {
  const [edit, setEdit] = useState({ value, text: formatClock(value) });
  const text = edit.value === value ? edit.text : formatClock(value);
  return <input {...props} type="text" placeholder="2:30 PM" autoComplete="off" value={text}
    pattern="(0?[1-9]|1[0-2]):[0-5][0-9]\s*[AaPp][Mm]" title="Enter a time such as 2:30 PM, including AM or PM."
    onChange={event => {
      const raw = event.target.value;
      const clock = parseClock(raw);
      setEdit({ value: clock, text: raw });
      onChange(clock);
    }} onBlur={() => { if (parseClock(text)) setEdit({ value, text: formatClock(value) }); }} />;
}
