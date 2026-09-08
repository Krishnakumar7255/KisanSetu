-- KisanSetu winning-feature migration.
-- Existing grievances table is reused for procurement/weight/QC disputes.
-- Weather and anti-hoarding signals are computed by the API adapter so no sensitive
-- or external credentials are required for the demo environment.
-- Production can replace the demo weather adapter with an authorized IMD provider.

begin;

-- Helpful indexes for queue/risk analytics.
create index if not exists idx_bookings_farmer_status_created
  on public.bookings(farmer_id, status, created_at desc);
create index if not exists idx_bookings_centre_status_date
  on public.bookings(centre_id, status, date, created_at desc);

commit;
notify pgrst, 'reload schema';
