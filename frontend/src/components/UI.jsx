import React from 'react';
import { Bell, MapPin, Mic, Users, MicOff, LogOut, Truck, CalendarDays, Clock, Wallet, ChevronRight, CheckCircle2, Volume2, Send, ShieldCheck, UserRound, Building2, Navigation, LocateFixed, RefreshCw, Route, Languages, Search, Map, ArrowUpRight, X, Mail, Sprout, CircleHelp, Settings, Timer, Wheat, BadgeIndianRupee, ClipboardCheck, AlertCircle, Menu, Home as HomeIcon, Ticket, CreditCard, Phone, Download, ExternalLink, Check, ChevronDown } from 'lucide-react';

export const IconButton=({children,onClick,label,className=''})=><button aria-label={label} title={label} onClick={onClick} className={`grid h-10 w-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-700 transition hover:-translate-y-0.5 hover:border-emerald-200 hover:text-emerald-700 hover:shadow-sm ${className}`}>{children}</button>;

export const Pill=({children,className=''})=><span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-extrabold ${className}`}>{children}</span>;

export const Card=({children,className='',...props})=><section {...props} className={`rounded-[22px] border border-slate-200/80 bg-white shadow-[0_10px_35px_rgba(16,55,34,.07)] ${className}`}>{children}</section>;

export const UsersIcon = ({size=20,className=''}) => <Users size={size} className={className}/>;
