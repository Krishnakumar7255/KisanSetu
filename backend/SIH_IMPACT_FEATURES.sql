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
