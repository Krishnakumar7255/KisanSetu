-- KisanSetu SIH final integrity hardening
-- Safe to run multiple times.

-- One procurement record per booking token.
create unique index if not exists uq_procurements_token on public.procurements(token);

-- One payment record per procurement token.
create unique index if not exists uq_payments_farmer_token on public.payments(farmer_id, token);

-- Helpful queue/history indexes.
create index if not exists idx_bookings_centre_date_slot on public.bookings(centre_id, date, slot, status);
create index if not exists idx_procurements_centre_date on public.procurements(centre_id, created_at desc);

-- Keep centre master IDs tied to the one-district/one-centre architecture.
create unique index if not exists uq_centres_district on public.centres(district);

notify pgrst, 'reload schema';
