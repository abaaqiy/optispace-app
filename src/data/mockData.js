export const initialRoomsData = [
  {
    id: "room-1", name: "Oduduwa Lecture Theatre (ODLT)", zone: "Faculty of Computing & Engineering", 
    type: "Tiered Amphitheatre", capacity: 1000, sizeCategory: "large", // LARGE
    status: "available", statusText: "Free Now (Until 2:00 PM)", facilities: ["ac", "projector", "power", "audio", "wifi"], 
    currentSchedule: null, nextSchedule: "2:00 PM - CSC 201 Lecture",
    hourlySchedule: [
      { time: "08:00 - 10:00", event: "CSC 101 Lecture", occupied: true },
      { time: "10:00 - 14:00", event: "Vacant / Free Slot", occupied: false },
      { time: "14:00 - 16:00", event: "CSC 201 Lecture", occupied: true }
    ]
  },
  {
    id: "room-2", name: "Computer Science Lab 1", zone: "Faculty of Computing & Engineering", 
    type: "Computer Laboratory", capacity: 80, sizeCategory: "small", // SMALL
    status: "occupied", statusText: "Occupied: CSC 305 until 11:30 AM", facilities: ["ac", "projector", "power", "wifi"], 
    currentSchedule: "CSC 305 OOP Practical", nextSchedule: "Free from 11:30 AM",
    hourlySchedule: [
      { time: "09:00 - 11:30", event: "CSC 305 OOP Practical", occupied: true },
      { time: "11:30 - 14:00", event: "Vacant / Free Slot", occupied: false }
    ]
  },
  {
    id: "room-3", name: "Engineering Drawing Studio", zone: "Faculty of Computing & Engineering", 
    type: "Workshop / Studio", capacity: 120, sizeCategory: "small", // SMALL
    status: "soon", statusText: "Free for next 35 mins", facilities: ["power", "wifi"], 
    currentSchedule: null, nextSchedule: "11:00 AM - MEE 301",
    hourlySchedule: [
      { time: "08:00 - 11:00", event: "Vacant / Free Slot", occupied: false },
      { time: "11:00 - 13:00", event: "MEE 301 Thermodynamics", occupied: true }
    ]
  },
  {
    id: "room-4", name: "Tech Auditorium 1", zone: "Faculty of Computing & Engineering", 
    type: "Large Lecture Hall", capacity: 350, sizeCategory: "large", // LARGE
    status: "occupied", statusText: "Occupied: EEE 401", facilities: ["ac", "projector", "power", "audio", "wifi"], 
    currentSchedule: "EEE 401 Power Systems", nextSchedule: "Occupied until 3:00 PM",
    hourlySchedule: [{ time: "08:00 - 15:00", event: "EEE 401 Power Systems", occupied: true }]
  },
  {
    id: "room-5", name: "Civil Engineering Lab 2", zone: "Faculty of Computing & Engineering", 
    type: "Laboratory", capacity: 60, sizeCategory: "small", // SMALL
    status: "available", statusText: "Available All Day", facilities: ["ac", "power", "wifi"], 
    currentSchedule: null, nextSchedule: "No further lectures today",
    hourlySchedule: [{ time: "08:00 - 18:00", event: "Vacant / Open Study Space", occupied: false }]
  },
  {
    id: "room-6", name: "ICT Seminar Room", zone: "Faculty of Computing & Engineering", 
    type: "Seminar Room", capacity: 50, sizeCategory: "small", // SMALL
    status: "available", statusText: "Available Now", facilities: ["ac", "projector", "power", "audio", "wifi"], 
    currentSchedule: null, nextSchedule: "1:00 PM - CSC 401",
    hourlySchedule: [
      { time: "08:00 - 13:00", event: "Vacant / Free Slot", occupied: false },
      { time: "13:00 - 15:00", event: "CSC 401 AI Seminar", occupied: true }
    ]
  }
];

export const initialBookings = [
  // ... keep your existing bookings
];