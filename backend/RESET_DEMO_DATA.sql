-- KisanSetu: clean demo reset
-- Run ONCE in Supabase SQL Editor before a fresh SIH demo.
-- This removes farmer/booking/transaction/demo history but preserves the 38 centre master rows.

begin;

delete from public.notifications;
delete from public.audit_logs;
delete from public.waitlist;
delete from public.payments;
delete from public.procurements;
delete from public.bookings;
delete from public.farmers;
delete from public.centre_registration_requests;

update public.token_counters set last_token = 0;

commit;

notify pgrst, 'reload schema';
