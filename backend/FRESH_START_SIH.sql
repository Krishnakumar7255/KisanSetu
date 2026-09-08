-- KisanSetu Fresh SIH Demo Reset + Integrity Setup
-- IMPORTANT: run this ONCE before the final SIH demo.
-- It clears all old farmer and transactional/demo data, preserves the 38 district centres,
-- resets token counters, and installs the booking integrity rules.

begin;

delete from public.notifications;
delete from public.feedback;
delete from public.grievances;
delete from public.audit_logs;
delete from public.waitlist;
delete from public.payments;
delete from public.procurements;
delete from public.bookings;
delete from public.farmers;
delete from public.centre_registration_requests;
update public.token_counters set last_token = 0;

-- Prevent one farmer from holding multiple active slots, even on different dates.
create unique index if not exists uq_one_active_booking_per_farmer
on public.bookings(farmer_id)
where status in ('waiting','confirmed','serving','procurement_pending');

-- Atomic reservation: locks one centre/date/slot while checking capacity and farmer state.
create or replace function public.create_booking_atomic(
  p_booking_id uuid, p_farmer_id text, p_centre_id text, p_crop text,
  p_quantity_kg numeric, p_date date, p_slot text, p_capacity integer
)
returns public.bookings
language plpgsql security definer set search_path = public
as $$
declare
  v_count integer; v_active integer; v_token text; v_row public.bookings;
begin
  perform pg_advisory_xact_lock(hashtext(p_centre_id || '|' || p_date::text || '|' || p_slot));
  select count(*) into v_active from public.bookings
    where farmer_id=p_farmer_id and status in ('waiting','confirmed','serving','procurement_pending');
  if v_active > 0 then raise exception 'ACTIVE_BOOKING_EXISTS'; end if;
  select count(*) into v_count from public.bookings
    where centre_id=p_centre_id and date=p_date and slot=p_slot
      and status not in ('cancelled','completed','skipped');
  if v_count >= greatest(1,p_capacity) then raise exception 'SLOT_FULL'; end if;
  v_token := public.next_mandi_token(p_centre_id);
  insert into public.bookings(booking_id,farmer_id,centre_id,crop,quantity_kg,date,slot,token,status,checked_in)
    values(p_booking_id,p_farmer_id,p_centre_id,p_crop,p_quantity_kg,p_date,p_slot,v_token,'waiting',false)
    returning * into v_row;
  return v_row;
end;
$$;

commit;
notify pgrst, 'reload schema';

revoke all on function public.create_booking_atomic(uuid,text,text,text,numeric,date,text,integer) from public;
grant execute on function public.create_booking_atomic(uuid,text,text,text,numeric,date,text,integer) to service_role;
notify pgrst, 'reload schema';
