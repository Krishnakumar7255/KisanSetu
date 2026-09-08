-- Run this once in Supabase SQL Editor
alter table public.bookings add column if not exists called_at timestamptz;
alter table public.bookings add column if not exists procurement_started_at timestamptz;
alter table public.bookings add column if not exists completed_at timestamptz;
alter table public.bookings add column if not exists skipped_at timestamptz;
alter table public.bookings add column if not exists skip_reason text;

alter table public.bookings drop constraint if exists bookings_status_check;

-- Procurement audit fields
alter table public.procurements add column if not exists employee_id text;
alter table public.procurements add column if not exists completed_at timestamptz;

create index if not exists idx_bookings_audit on public.bookings(centre_id, date, status, skipped_at, completed_at);
create index if not exists idx_procurements_employee on public.procurements(employee_id, completed_at desc);
notify pgrst, 'reload schema';


-- Dynamic queue / Skip for Now
alter table public.bookings add column if not exists deferred_at timestamptz;
alter table public.bookings add column if not exists defer_reason text;
create index if not exists idx_bookings_deferred on public.bookings(centre_id, date, deferred_at);
notify pgrst, 'reload schema';
alter table public.bookings add column if not exists arrived_at timestamptz;
-- AI feature requires no extra database tables; predictions are computed from operational history.
