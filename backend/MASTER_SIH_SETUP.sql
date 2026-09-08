-- KisanSetu SIH 2026 - CANONICAL MASTER SUPABASE SETUP
-- Run this file once on a fresh Supabase project.
-- Do NOT run FRESH_START_SIH.sql or RESET_DEMO_DATA.sql as part of normal setup.
-- This file contains the consolidated schema and RPCs used by the backend.

-- KisanSetu SIH consolidated migration for Supabase SQL Editor
-- Run this single file. Do NOT run FRESH_START_SIH.sql or RESET_DEMO_DATA.sql unless you intentionally want destructive demo reset.


-- ===== BEGIN schema.sql =====
-- KisanSetu Supabase schema
create extension if not exists pgcrypto;

create table if not exists centres (
  centre_id text primary key,
  employee_id text unique,
  name text not null,
  district text not null,
  city text not null,
  address text not null,
  lat double precision not null,
  lon double precision not null,
  counters integer not null default 2 check (counters > 0),
  mobile text,
  registration_status text not null default 'approved'
);

alter table public.centres add column if not exists mobile text;

create table if not exists farmers (
  farmer_id text primary key,
  mobile text unique not null,
  email text,
  name text not null,
  village text not null,
  district text not null,
  crop text not null default 'Wheat',
  centre_id text references centres(centre_id),
  created_at timestamptz not null default now()
);

create table if not exists bookings (
  booking_id uuid primary key default gen_random_uuid(),
  farmer_id text not null references farmers(farmer_id),
  centre_id text not null references centres(centre_id),
  crop text not null,
  quantity_kg numeric(12,2) not null check (quantity_kg > 0),
  date date not null,
  slot text not null,
  token text not null,
  status text not null default 'waiting',
  checked_in boolean not null default false,
  called_at timestamptz,
  procurement_started_at timestamptz,
  completed_at timestamptz,
  skipped_at timestamptz,
  skip_reason text,
  deferred_at timestamptz,
  defer_reason text,
  created_at timestamptz not null default now()
);
create index if not exists idx_bookings_queue on bookings(centre_id, date, status, created_at);
create index if not exists idx_bookings_farmer on bookings(farmer_id, date);
drop index if exists uq_active_farmer_date;
create unique index if not exists uq_active_farmer_date on bookings(farmer_id, date) where status in ('waiting','confirmed','serving','procurement_pending');
create unique index if not exists uq_centre_token on bookings(centre_id, token);

create table if not exists token_counters (
  centre_id text primary key references centres(centre_id),
  last_token integer not null default 0
);

create or replace function next_mandi_token(p_centre_id text)
returns text
language plpgsql
as $$
declare n integer;
begin
  insert into token_counters(centre_id, last_token) values (p_centre_id, 0)
  on conflict (centre_id) do nothing;
  update token_counters set last_token = last_token + 1
  where centre_id = p_centre_id
  returning last_token into n;
  return 'T-' || lpad(n::text, 3, '0');
end;
$$;

create table if not exists notifications (
  id uuid primary key default gen_random_uuid(),
  farmer_id text not null references farmers(farmer_id),
  title text not null,
  message text not null,
  created_at timestamptz not null default now(),
  read boolean not null default false
);
create index if not exists idx_notifications_farmer on notifications(farmer_id, created_at desc);

create table if not exists procurements (
  procurement_id uuid primary key default gen_random_uuid(),
  farmer_id text not null references farmers(farmer_id),
  centre_id text not null references centres(centre_id),
  crop text not null,
  quantity_kg numeric(12,2) not null,
  quality_grade text not null default 'FAQ',
  rate_per_kg numeric(12,2) not null,
  amount numeric(14,2) not null,
  token text not null,
  created_at timestamptz not null default now(),
  employee_id text,
  completed_at timestamptz
);

create table if not exists payments (
  payment_id text primary key,
  farmer_id text not null references farmers(farmer_id),
  token text not null,
  status text not null default 'processing',
  amount numeric(14,2),
  created_at timestamptz not null default now(),
  completed_at timestamptz
);
create index if not exists idx_payments_farmer on payments(farmer_id, created_at desc);

-- Backend uses the service-role key, so it bypasses RLS.
-- Enable RLS if you later expose Supabase directly to the browser.
alter table centres enable row level security;
alter table farmers enable row level security;
alter table bookings enable row level security;
alter table notifications enable row level security;
alter table procurements enable row level security;
alter table payments enable row level security;


-- Existing installations: run these migration statements once.
alter table public.centres add column if not exists employee_id text;
create unique index if not exists uq_centres_employee_id on public.centres(employee_id) where employee_id is not null;
notify pgrst, 'reload schema';

-- ===== END schema.sql =====


-- ===== BEGIN SIH_WINNING_FEATURES.sql =====
-- KisanSetu SIH Winning Features migration
alter table public.procurements add column if not exists gross_weight_kg numeric(12,2);
alter table public.procurements add column if not exists tare_weight_kg numeric(12,2) default 0;
alter table public.procurements add column if not exists moisture_percent numeric(5,2);
alter table public.payments add column if not exists utr text;
alter table public.payments add column if not exists settlement_mode text default 'SIMULATED_DBT';
alter table public.bookings add column if not exists arrived_at timestamptz;
alter table public.bookings add column if not exists defer_reason text;

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  event text not null,
  centre_id text references public.centres(centre_id),
  farmer_id text references public.farmers(farmer_id),
  token text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_audit_farmer on public.audit_logs(farmer_id, created_at desc);
create index if not exists idx_audit_centre on public.audit_logs(centre_id, created_at desc);
create index if not exists idx_audit_token on public.audit_logs(token, created_at desc);

create unique index if not exists uq_payment_farmer_token on public.payments(farmer_id, token);
create unique index if not exists uq_procurement_farmer_token on public.procurements(farmer_id, token);

alter table public.audit_logs enable row level security;
notify pgrst, 'reload schema';

create table if not exists public.waitlist (
  waitlist_id uuid primary key default gen_random_uuid(),
  farmer_id text not null references public.farmers(farmer_id),
  centre_id text not null references public.centres(centre_id),
  booking_date date not null,
  slot text not null,
  crop text not null,
  quantity_kg numeric(12,2) not null check (quantity_kg > 0),
  status text not null default 'waiting',
  created_at timestamptz not null default now()
);
create unique index if not exists uq_waitlist_farmer_slot on public.waitlist(farmer_id, booking_date, slot) where status='waiting';
create index if not exists idx_waitlist_centre on public.waitlist(centre_id, booking_date, slot, created_at);
alter table public.waitlist enable row level security;
notify pgrst, 'reload schema';

-- One active booking per farmer across ALL dates (not just per date).
-- This matches the real-world rule used by the KisanSetu demo: a farmer must
-- complete/cancel the current booking before reserving another slot.
create unique index if not exists uq_one_active_booking_per_farmer
on public.bookings(farmer_id)
where status in ('waiting','confirmed','serving','procurement_pending');

-- Atomic slot reservation. The advisory lock is scoped to centre/date/slot,
-- preventing two simultaneous requests from taking the same last capacity.
create or replace function public.create_booking_atomic(
  p_booking_id uuid,
  p_farmer_id text,
  p_centre_id text,
  p_crop text,
  p_quantity_kg numeric,
  p_date date,
  p_slot text,
  p_capacity integer
)
returns public.bookings
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count integer;
  v_active integer;
  v_token text;
  v_row public.bookings;
begin
  perform pg_advisory_xact_lock(hashtext(p_centre_id || '|' || p_date::text || '|' || p_slot));

  select count(*) into v_active
  from public.bookings
  where farmer_id = p_farmer_id
    and status in ('waiting','confirmed','serving','procurement_pending');
  if v_active > 0 then
    raise exception 'ACTIVE_BOOKING_EXISTS';
  end if;

  select count(*) into v_count
  from public.bookings
  where centre_id = p_centre_id
    and date = p_date
    and slot = p_slot
    and status not in ('cancelled','completed','skipped');

  if v_count >= greatest(1, p_capacity) then
    raise exception 'SLOT_FULL';
  end if;

  v_token := public.next_mandi_token(p_centre_id);

  insert into public.bookings(
    booking_id, farmer_id, centre_id, crop, quantity_kg, date, slot, token, status, checked_in
  ) values (
    p_booking_id, p_farmer_id, p_centre_id, p_crop, p_quantity_kg, p_date, p_slot, v_token, 'waiting', false
  ) returning * into v_row;

  return v_row;
end;
$$;

notify pgrst, 'reload schema';

-- ===== END SIH_WINNING_FEATURES.sql =====


-- ===== BEGIN QUEUE_AUDIT_MIGRATION.sql =====
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

-- ===== END QUEUE_AUDIT_MIGRATION.sql =====


-- ===== BEGIN SIH_IMPACT_FEATURES.sql =====
-- KisanSetu SIH impact features: grievances, feedback, configurable crop rates.
begin;
create table if not exists public.crop_rates (
  rate_id uuid primary key default gen_random_uuid(),
  crop text not null,
  quality_grade text not null default 'FAQ',
  rate_per_kg numeric(12,2) not null check (rate_per_kg > 0),
  effective_from date not null default current_date,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  unique(crop, quality_grade, effective_from)
);

insert into public.crop_rates(crop,quality_grade,rate_per_kg) values
('Wheat','FAQ',22.50),('Rice','FAQ',21.50),('Maize','FAQ',20.00),('Mustard','FAQ',25.00)
on conflict do nothing;

create table if not exists public.grievances (
  grievance_id uuid primary key default gen_random_uuid(),
  farmer_id text not null references public.farmers(farmer_id) on delete cascade,
  centre_id text references public.centres(centre_id),
  token text,
  category text not null,
  subject text not null,
  description text not null,
  priority text not null default 'MEDIUM',
  status text not null default 'OPEN',
  resolution text,
  assigned_to text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz
);
create index if not exists idx_grievances_status on public.grievances(status, created_at desc);
create index if not exists idx_grievances_farmer on public.grievances(farmer_id, created_at desc);

create table if not exists public.feedback (
  feedback_id uuid primary key default gen_random_uuid(),
  farmer_id text not null references public.farmers(farmer_id) on delete cascade,
  centre_id text references public.centres(centre_id),
  token text,
  waiting_rating integer check(waiting_rating between 1 and 5),
  service_rating integer check(service_rating between 1 and 5),
  staff_rating integer check(staff_rating between 1 and 5),
  overall_rating integer not null check(overall_rating between 1 and 5),
  comment text,
  created_at timestamptz not null default now(),
  unique(farmer_id, token)
);
create index if not exists idx_feedback_centre on public.feedback(centre_id, created_at desc);

commit;
notify pgrst, 'reload schema';

-- ===== END SIH_IMPACT_FEATURES.sql =====


-- Seed the 38 Bihar district procurement centres so a fresh SQL-only setup is immediately usable.
insert into public.centres(centre_id,name,district,city,address,lat,lon,counters,registration_status) values
  ('C001','Araria Procurement Centre','Araria','Araria','Araria, Bihar',26.1558,87.5017,3,'approved'),
  ('C002','Arwal Procurement Centre','Arwal','Arwal','Arwal, Bihar',25.2492,84.681,2,'approved'),
  ('C003','Aurangabad Procurement Centre','Aurangabad','Aurangabad','Aurangabad, Bihar',24.7521,84.3742,3,'approved'),
  ('C004','Banka Procurement Centre','Banka','Banka','Banka, Bihar',24.8874,86.9198,2,'approved'),
  ('C005','Begusarai Procurement Centre','Begusarai','Begusarai','Begusarai, Bihar',25.4182,86.1272,4,'approved'),
  ('C006','Bhagalpur Procurement Centre','Bhagalpur','Bhagalpur','Bhagalpur, Bihar',25.2425,86.9842,4,'approved'),
  ('C007','Bhojpur Procurement Centre','Bhojpur','Ara','Ara, Bihar',25.556,84.6633,3,'approved'),
  ('C008','Buxar Procurement Centre','Buxar','Buxar','Buxar, Bihar',25.5647,83.9777,2,'approved'),
  ('C009','Darbhanga Procurement Centre','Darbhanga','Darbhanga','Darbhanga, Bihar',26.1542,85.8918,4,'approved'),
  ('C010','East Champaran Procurement Centre','East Champaran','Motihari','Motihari, Bihar',26.6499,84.9161,4,'approved'),
  ('C011','Gaya Procurement Centre','Gaya','Gaya','Gaya, Bihar',24.7955,84.9994,5,'approved'),
  ('C012','Gopalganj Procurement Centre','Gopalganj','Gopalganj','Gopalganj, Bihar',26.4672,84.4402,3,'approved'),
  ('C013','Jamui Procurement Centre','Jamui','Jamui','Jamui, Bihar',24.926,86.2249,2,'approved'),
  ('C014','Jehanabad Procurement Centre','Jehanabad','Jehanabad','Jehanabad, Bihar',25.207,84.9874,3,'approved'),
  ('C015','Kaimur Procurement Centre','Kaimur','Bhabua','Bhabua, Bihar',25.04,83.615,2,'approved'),
  ('C016','Katihar Procurement Centre','Katihar','Katihar','Katihar, Bihar',25.5394,87.5788,4,'approved'),
  ('C017','Khagaria Procurement Centre','Khagaria','Khagaria','Khagaria, Bihar',25.5022,86.4671,3,'approved'),
  ('C018','Kishanganj Procurement Centre','Kishanganj','Kishanganj','Kishanganj, Bihar',26.1025,87.9553,2,'approved'),
  ('C019','Lakhisarai Procurement Centre','Lakhisarai','Lakhisarai','Lakhisarai, Bihar',25.1574,86.0952,2,'approved'),
  ('C020','Madhepura Procurement Centre','Madhepura','Madhepura','Madhepura, Bihar',25.9213,86.7927,3,'approved'),
  ('C021','Madhubani Procurement Centre','Madhubani','Madhubani','Madhubani, Bihar',26.3489,86.0717,4,'approved'),
  ('C022','Munger Procurement Centre','Munger','Munger','Munger, Bihar',25.3708,86.4734,3,'approved'),
  ('C023','Muzaffarpur Procurement Centre','Muzaffarpur','Muzaffarpur','Muzaffarpur, Bihar',26.1209,85.3647,5,'approved'),
  ('C024','Nalanda Procurement Centre','Nalanda','Bihar Sharif','Bihar Sharif, Bihar',25.198,85.5149,4,'approved'),
  ('C025','Nawada Procurement Centre','Nawada','Nawada','Nawada, Bihar',24.886,85.543,3,'approved'),
  ('C026','Patna Procurement Centre','Patna','Patna','Patna, Bihar',25.5941,85.1376,6,'approved'),
  ('C027','Purnia Procurement Centre','Purnia','Purnea','Purnea, Bihar',25.7771,87.4753,4,'approved'),
  ('C028','Rohtas Procurement Centre','Rohtas','Sasaram','Sasaram, Bihar',24.949,84.006,3,'approved'),
  ('C029','Saharsa Procurement Centre','Saharsa','Saharsa','Saharsa, Bihar',25.883,86.6006,3,'approved'),
  ('C030','Samastipur Procurement Centre','Samastipur','Samastipur','Samastipur, Bihar',25.8629,85.781,4,'approved'),
  ('C031','Saran Procurement Centre','Saran','Chhapra','Chhapra, Bihar',25.7796,84.7499,4,'approved'),
  ('C032','Sheikhpura Procurement Centre','Sheikhpura','Sheikhpura','Sheikhpura, Bihar',25.139,85.8551,2,'approved'),
  ('C033','Sheohar Procurement Centre','Sheohar','Sheohar','Sheohar, Bihar',26.5147,85.294,2,'approved'),
  ('C034','Sitamarhi Procurement Centre','Sitamarhi','Sitamarhi','Sitamarhi, Bihar',26.5887,85.5016,3,'approved'),
  ('C035','Siwan Procurement Centre','Siwan','Siwan','Siwan, Bihar',26.22,84.356,3,'approved'),
  ('C036','Supaul Procurement Centre','Supaul','Supaul','Supaul, Bihar',26.126,86.605,3,'approved'),
  ('C037','Vaishali Procurement Centre','Vaishali','Hajipur','Hajipur, Bihar',25.6865,85.2162,4,'approved'),
  ('C038','West Champaran Procurement Centre','West Champaran','Bettiah','Bettiah, Bihar',27.0992,84.09,4,'approved')
on conflict (centre_id) do update set name=excluded.name,district=excluded.district,city=excluded.city,address=excluded.address,lat=excluded.lat,lon=excluded.lon,counters=excluded.counters,registration_status=coalesce(public.centres.registration_status, excluded.registration_status);

-- ===== BEGIN CENTRE_REGISTRATION_REQUESTS.sql =====
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

-- ===== END CENTRE_REGISTRATION_REQUESTS.sql =====


-- ===== BEGIN PRODUCTION_HARDENING.sql =====
-- KisanSetu production-demo hardening
alter table public.payments add column if not exists utr text;
alter table public.payments add column if not exists settlement_mode text;
create unique index if not exists uq_payments_utr on public.payments(utr) where utr is not null;

create table if not exists public.centre_registration_requests (
  request_id uuid primary key default gen_random_uuid(),
  centre_id text not null, district text not null, name text not null, mobile text not null,
  address text not null, counters integer not null default 2 check (counters between 1 and 20),
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  employee_id text, created_at timestamptz not null default now(), reviewed_at timestamptz
);
create unique index if not exists uq_pending_centre_registration on public.centre_registration_requests(centre_id) where status='pending';
create index if not exists idx_centre_requests_status on public.centre_registration_requests(status, created_at desc);
notify pgrst, 'reload schema';

-- ===== END PRODUCTION_HARDENING.sql =====


-- ===== BEGIN DISTRICT_CENTER_MASTER_FIX.sql =====
-- One procurement centre per district: fixed master codes C001-C038.
-- Safe for existing data because duplicate district rows are not expected.
create unique index if not exists uq_centres_district on public.centres (lower(trim(district)));
notify pgrst, 'reload schema';

-- ===== END DISTRICT_CENTER_MASTER_FIX.sql =====


-- ===== BEGIN BOOKING_RPC_SCHEMA_FIX.sql =====
-- KisanSetu SIH: repair/create the atomic booking RPC expected by FastAPI.
-- Safe to run on an existing Supabase project. It does NOT delete booking data.
begin;

create or replace function public.create_booking_atomic(
  p_booking_id uuid,
  p_farmer_id text,
  p_centre_id text,
  p_crop text,
  p_quantity_kg numeric,
  p_date date,
  p_slot text,
  p_capacity integer
)
returns public.bookings
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count integer;
  v_active integer;
  v_token text;
  v_row public.bookings;
begin
  perform pg_advisory_xact_lock(hashtext(p_centre_id || '|' || p_date::text || '|' || p_slot));

  select count(*) into v_active from public.bookings
  where farmer_id = p_farmer_id
    and status in ('waiting','confirmed','serving','procurement_pending');
  if v_active > 0 then raise exception 'ACTIVE_BOOKING_EXISTS'; end if;

  select count(*) into v_count from public.bookings
  where centre_id = p_centre_id and date = p_date and slot = p_slot
    and status not in ('cancelled','completed','skipped');
  if v_count >= greatest(1, p_capacity) then raise exception 'SLOT_FULL'; end if;

  v_token := public.next_mandi_token(p_centre_id);
  insert into public.bookings(booking_id, farmer_id, centre_id, crop, quantity_kg, date, slot, token, status, checked_in)
  values(p_booking_id, p_farmer_id, p_centre_id, p_crop, p_quantity_kg, p_date, p_slot, v_token, 'waiting', false)
  returning * into v_row;
  return v_row;
end;
$$;

revoke all on function public.create_booking_atomic(uuid,text,text,text,numeric,date,text,integer) from public;
grant execute on function public.create_booking_atomic(uuid,text,text,text,numeric,date,text,integer) to service_role;
notify pgrst, 'reload schema';
commit;

-- ===== END BOOKING_RPC_SCHEMA_FIX.sql =====

NOTIFY pgrst, 'reload schema';

-- ===== BEGIN PROCUREMENT_ATOMIC_FIX.sql =====
create or replace function public.complete_procurement_atomic(
  p_procurement_id uuid, p_farmer_id text, p_centre_id text, p_crop text,
  p_quantity_kg numeric, p_gross_weight_kg numeric, p_tare_weight_kg numeric,
  p_moisture_percent numeric, p_quality_grade text, p_rate_per_kg numeric,
  p_token text, p_employee_id text, p_completed_at timestamptz
) returns public.procurements language plpgsql security definer set search_path = public as $$
declare v_booking public.bookings%rowtype; v_proc public.procurements%rowtype; v_amount numeric(14,2);
begin
  perform pg_advisory_xact_lock(hashtextextended(p_farmer_id || ':' || p_token, 0));
  select * into v_booking from public.bookings where farmer_id=p_farmer_id and token=p_token order by created_at desc limit 1 for update;
  if not found then raise exception 'Booking not found for farmer/token'; end if;
  if v_booking.centre_id <> p_centre_id then raise exception 'Booking centre mismatch'; end if;
  if v_booking.status <> 'procurement_pending' then raise exception 'Booking must be procurement_pending before procurement'; end if;
  if exists (select 1 from public.procurements where farmer_id=p_farmer_id and token=p_token) then
    select * into v_proc from public.procurements where farmer_id=p_farmer_id and token=p_token limit 1; return v_proc;
  end if;
  v_amount := round(p_quantity_kg * p_rate_per_kg, 2);
  insert into public.procurements(procurement_id,farmer_id,centre_id,crop,quantity_kg,gross_weight_kg,tare_weight_kg,moisture_percent,quality_grade,rate_per_kg,amount,token,employee_id,completed_at)
  values(p_procurement_id,p_farmer_id,p_centre_id,p_crop,p_quantity_kg,p_gross_weight_kg,p_tare_weight_kg,p_moisture_percent,p_quality_grade,p_rate_per_kg,v_amount,p_token,p_employee_id,p_completed_at)
  returning * into v_proc;
  update public.bookings set status='completed', completed_at=p_completed_at where booking_id=v_booking.booking_id;
  return v_proc;
end; $$;
grant execute on function public.complete_procurement_atomic(uuid,text,text,text,numeric,numeric,numeric,numeric,text,numeric,text,text,timestamptz) to service_role;
notify pgrst, 'reload schema';
-- ===== END PROCUREMENT_ATOMIC_FIX.sql =====

-- SIH Winning Feature Pack (V14)
create index if not exists idx_bookings_farmer_status_created
  on public.bookings(farmer_id, status, created_at desc);
create index if not exists idx_bookings_centre_status_date
  on public.bookings(centre_id, status, date, created_at desc);
