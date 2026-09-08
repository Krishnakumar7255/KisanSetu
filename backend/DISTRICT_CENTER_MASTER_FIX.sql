-- One procurement centre per district: fixed master codes C001-C038.
-- Safe for existing data because duplicate district rows are not expected.
create unique index if not exists uq_centres_district on public.centres (lower(trim(district)));
notify pgrst, 'reload schema';
