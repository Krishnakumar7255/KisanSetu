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
