-- KisanSetu: keep registration applications separate from the live centre master.
create table if not exists public.centre_registration_requests (
  request_id uuid primary key default gen_random_uuid(),
  centre_id text not null,
  district text not null,
  name text not null,
  mobile text not null,
  address text not null,
  counters integer not null default 2 check (counters between 1 and 20),
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  employee_id text,
  created_at timestamptz not null default now(),
  reviewed_at timestamptz
);
create unique index if not exists uq_pending_centre_registration
  on public.centre_registration_requests (centre_id) where status = 'pending';
create index if not exists idx_centre_requests_status on public.centre_registration_requests(status, created_at desc);
notify pgrst, 'reload schema';
