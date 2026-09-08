-- KisanSetu centre registration fixes
alter table public.centres add column if not exists registration_status text not null default 'approved';
update public.centres set registration_status='approved' where registration_status is null;
create index if not exists idx_centres_registration_status on public.centres(registration_status);
notify pgrst, 'reload schema';
