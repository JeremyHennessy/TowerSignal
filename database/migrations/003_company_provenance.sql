BEGIN;

ALTER TABLE public.company_private_profiles
  ADD COLUMN IF NOT EXISTS identity_source_name text,
  ADD COLUMN IF NOT EXISTS identity_source_url text,
  ADD COLUMN IF NOT EXISTS website_source_name text,
  ADD COLUMN IF NOT EXISTS website_source_url text,
  ADD COLUMN IF NOT EXISTS rollup_source_name text,
  ADD COLUMN IF NOT EXISTS rollup_source_url text,
  ADD COLUMN IF NOT EXISTS headquarters_source_name text,
  ADD COLUMN IF NOT EXISTS headquarters_source_url text,
  ADD COLUMN IF NOT EXISTS parent_source_name text,
  ADD COLUMN IF NOT EXISTS parent_source_url text,
  ADD COLUMN IF NOT EXISTS enrichment_checked_at timestamptz;

ALTER TABLE public.company_private_contacts
  ADD COLUMN IF NOT EXISTS source_name text,
  ADD COLUMN IF NOT EXISTS source_url text,
  ADD COLUMN IF NOT EXISTS verified_at timestamptz;

COMMIT;
