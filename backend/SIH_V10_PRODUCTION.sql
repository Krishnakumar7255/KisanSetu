-- KisanSetu SIH v10 production extension.
-- PostgreSQL/Supabase compatible. Apply after the existing master setup.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN CREATE TYPE user_role_v10 AS ENUM ('FARMER','OPERATOR','ADMIN'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE token_status_v10 AS ENUM ('BOOKED','ARRIVED','QC_PASSED','QC_FAILED','WEIGHED','DISPATCHED','COMPLETED'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE dbt_status_v10 AS ENUM ('PENDING','PROCESSING','CREDITED','FAILED'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS users_v10 (
  user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  farmer_id text UNIQUE,
  mobile varchar(10) NOT NULL UNIQUE,
  name text NOT NULL,
  role user_role_v10 NOT NULL,
  centre_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS land_records (
  land_record_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  farmer_id text NOT NULL,
  survey_khasra_no text NOT NULL,
  land_area_acre numeric(12,3) NOT NULL CHECK (land_area_acre > 0),
  crop text NOT NULL,
  max_crop_quantity_kg numeric(14,2) NOT NULL CHECK (max_crop_quantity_kg > 0),
  verified_source text NOT NULL DEFAULT 'MOCK_BHULEKH_PM_KISAN',
  verified_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(farmer_id, survey_khasra_no, crop)
);
CREATE TABLE IF NOT EXISTS mandi_centers_v10 (
  mandi_id text PRIMARY KEY,
  district text NOT NULL UNIQUE,
  name text NOT NULL,
  address text NOT NULL,
  weighbridge_count integer NOT NULL CHECK (weighbridge_count > 0),
  daily_rated_capacity_kg numeric(16,2) NOT NULL CHECK (daily_rated_capacity_kg > 0),
  active boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS procurement_slots (
  slot_id text PRIMARY KEY,
  mandi_id text NOT NULL REFERENCES mandi_centers_v10(mandi_id),
  booking_date date NOT NULL,
  start_time time NOT NULL,
  end_time time NOT NULL,
  capacity_kg numeric(16,2) NOT NULL CHECK (capacity_kg > 0),
  buffer_kg numeric(16,2) NOT NULL DEFAULT 0 CHECK (buffer_kg >= 0),
  state text NOT NULL DEFAULT 'OPEN' CHECK (state IN ('OPEN','FULL','CLOSED','PAUSED')),
  UNIQUE(mandi_id, booking_date, start_time)
);
CREATE TABLE IF NOT EXISTS token_bookings (
  booking_id uuid PRIMARY KEY,
  farmer_id text NOT NULL,
  mandi_id text NOT NULL REFERENCES mandi_centers_v10(mandi_id),
  crop text NOT NULL,
  quantity_kg numeric(14,2) NOT NULL CHECK (quantity_kg > 0),
  slot_id text NOT NULL REFERENCES procurement_slots(slot_id),
  booking_date date NOT NULL,
  qr_hash text NOT NULL UNIQUE,
  status token_status_v10 NOT NULL DEFAULT 'BOOKED',
  arrived_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_v10_active_farmer_day ON token_bookings(farmer_id, booking_date) WHERE status IN ('BOOKED','ARRIVED','QC_PASSED','WEIGHED','DISPATCHED');
CREATE INDEX IF NOT EXISTS ix_v10_queue ON token_bookings(mandi_id, booking_date, status, created_at);
CREATE TABLE IF NOT EXISTS weighment_logs (
  weighment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES token_bookings(booking_id),
  operator_id text NOT NULL,
  gross_weight_kg numeric(14,2) NOT NULL CHECK (gross_weight_kg > 0),
  tare_weight_kg numeric(14,2) NOT NULL CHECK (tare_weight_kg >= 0),
  net_procured_weight_kg numeric(14,2) GENERATED ALWAYS AS (gross_weight_kg - tare_weight_kg) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (gross_weight_kg >= tare_weight_kg)
);
CREATE TABLE IF NOT EXISTS payout_records (
  payout_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES token_bookings(booking_id),
  farmer_id text NOT NULL,
  amount numeric(14,2) NOT NULL CHECK (amount >= 0),
  msp_rate_per_kg numeric(12,2) NOT NULL CHECK (msp_rate_per_kg >= 0),
  dbt_status dbt_status_v10 NOT NULL DEFAULT 'PENDING',
  utr text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  credited_at timestamptz
);
CREATE INDEX IF NOT EXISTS ix_v10_payout_farmer ON payout_records(farmer_id, created_at DESC);

-- Mock verified land records for demonstration only; replace with an authorized adapter in production.
INSERT INTO land_records (farmer_id, survey_khasra_no, land_area_acre, crop, max_crop_quantity_kg)
SELECT f.farmer_id, 'DEMO-' || f.farmer_id, 2.50, COALESCE(f.crop,'Wheat'), 500
FROM farmers f
WHERE NOT EXISTS (SELECT 1 FROM land_records l WHERE l.farmer_id=f.farmer_id AND l.crop=COALESCE(f.crop,'Wheat'));


-- Demo/master sync: keep the SIH v10 extension usable with the existing KisanSetu centre master.
-- These rows are additive and safe to run repeatedly.
INSERT INTO mandi_centers_v10 (mandi_id, district, name, address, weighbridge_count, daily_rated_capacity_kg, active)
SELECT c.centre_id, c.district, COALESCE(c.city || ' Procurement Centre', c.district || ' Procurement Centre'),
       COALESCE(c.city, c.district), GREATEST(1, COALESCE(c.counters, 1)),
       GREATEST(10000, COALESCE(c.counters, 1) * 48000), true
FROM centres c
ON CONFLICT (mandi_id) DO UPDATE SET
  district = EXCLUDED.district, name = EXCLUDED.name, address = EXCLUDED.address,
  weighbridge_count = EXCLUDED.weighbridge_count, daily_rated_capacity_kg = EXCLUDED.daily_rated_capacity_kg;

-- Create rolling demo slots for the next 7 days. In production these should be generated
-- by the capacity engine from live weighbridge throughput instead of fixed demo values.
INSERT INTO procurement_slots (slot_id, mandi_id, booking_date, start_time, end_time, capacity_kg, buffer_kg, state)
SELECT c.centre_id || '-' || to_char(d::date, 'YYYYMMDD') || '-' || to_char(t.start_time, 'HH24MI'),
       c.centre_id, d::date, t.start_time, t.start_time + interval '2 hours',
       GREATEST(5000, c.counters * 10000), GREATEST(500, c.counters * 1000), 'OPEN'
FROM centres c
CROSS JOIN generate_series(current_date, current_date + interval '6 days', interval '1 day') d
CROSS JOIN (VALUES (time '09:00'), (time '11:00'), (time '13:00'), (time '15:00')) t(start_time)
ON CONFLICT (slot_id) DO NOTHING;

CREATE INDEX IF NOT EXISTS ix_v10_slot_lookup ON procurement_slots(mandi_id, booking_date, state, start_time);
