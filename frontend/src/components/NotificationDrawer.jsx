import React, { useEffect, useState } from 'react';
import { Bell, MapPin, LogOut, UserRound, Building2, Home as HomeIcon, Ticket, Wallet, Settings, X, CheckCircle2 } from 'lucide-react';
import { api } from '../api/api';
import { Pill, IconButton } from './UI';

function NotificationDrawer({notes,onClose}){return <div className="fixed inset-0 z-[100] bg-slate-950/20 backdrop-blur-[2px]" onClick={onClose}><aside onClick={e=>e.stopPropagation()} className="absolute right-0 top-0 h-full w-full max-w-md overflow-y-auto bg-white p-5 shadow-2xl"><div className="flex items-center justify-between"><div><h2 className="text-lg font-black">Notifications</h2><p className="text-xs text-slate-500">Booking, queue & payment updates</p></div><IconButton label="Close" onClick={onClose}><X size={18}/></IconButton></div><div className="mt-5 space-y-3">{notes.length?notes.map(n=><div key={n.id} className="flex gap-3 rounded-2xl border border-slate-100 bg-slate-50 p-3.5"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-100 text-emerald-700"><Bell size={17}/></div><div><b className="text-sm">{n.title}</b><p className="mt-1 text-xs leading-5 text-slate-500">{n.message}</p></div></div>):<div className="py-16 text-center text-sm text-slate-400">No new notifications</div>}</div></aside></div>}
export default NotificationDrawer;
