-- Atomic procurement completion: inserts procurement and completes booking in one transaction.
create or replace function public.complete_procurement_atomic(
  p_procurement_id uuid,
  p_farmer_id text,
  p_centre_id text,
  p_crop text,
  p_quantity_kg numeric,
  p_gross_weight_kg numeric,
  p_tare_weight_kg numeric,
  p_moisture_percent numeric,
  p_quality_grade text,
  p_rate_per_kg numeric,
  p_token text,
  p_employee_id text,
  p_completed_at timestamptz
) returns public.procurements
language plpgsql
security definer
set search_path = public
as $$
declare
  v_booking public.bookings%rowtype;
  v_proc public.procurements%rowtype;
  v_amount numeric(14,2);
begin
  perform pg_advisory_xact_lock(hashtextextended(p_farmer_id || ':' || p_token, 0));

  select * into v_booking
  from public.bookings
  where farmer_id = p_farmer_id and token = p_token
  order by created_at desc
  limit 1
  for update;

  if not found then
    raise exception 'Booking not found for farmer/token';
  end if;
  if v_booking.centre_id <> p_centre_id then
    raise exception 'Booking centre mismatch';
  end if;
  if v_booking.status <> 'procurement_pending' then
    raise exception 'Booking must be procurement_pending before procurement';
  end if;

  if exists (select 1 from public.procurements where farmer_id = p_farmer_id and token = p_token) then
    select * into v_proc from public.procurements where farmer_id = p_farmer_id and token = p_token limit 1;
    return v_proc;
  end if;

  v_amount := round(p_quantity_kg * p_rate_per_kg, 2);

  insert into public.procurements (
    procurement_id, farmer_id, centre_id, crop, quantity_kg,
    gross_weight_kg, tare_weight_kg, moisture_percent, quality_grade,
    rate_per_kg, amount, token, employee_id, completed_at
  ) values (
    p_procurement_id, p_farmer_id, p_centre_id, p_crop, p_quantity_kg,
    p_gross_weight_kg, p_tare_weight_kg, p_moisture_percent, p_quality_grade,
    p_rate_per_kg, v_amount, p_token, p_employee_id, p_completed_at
  ) returning * into v_proc;

  update public.bookings
  set status = 'completed', completed_at = p_completed_at
  where booking_id = v_booking.booking_id;

  return v_proc;
end;
$$;

grant execute on function public.complete_procurement_atomic(uuid,text,text,text,numeric,numeric,numeric,numeric,text,numeric,text,text,timestamptz) to service_role;
notify pgrst, 'reload schema';
