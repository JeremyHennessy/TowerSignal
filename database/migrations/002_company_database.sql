BEGIN;

CREATE OR REPLACE FUNCTION public.towersignal_is_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, neon_auth, auth
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM neon_auth."user" AS u
    WHERE u.id::text = auth.user_id()
      AND lower(coalesce(u.role, '')) = 'admin'
  );
$$;

REVOKE ALL ON FUNCTION public.towersignal_is_admin() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.towersignal_is_admin() TO authenticated;

CREATE OR REPLACE VIEW public.company_admin_access
WITH (security_invoker = true)
AS
SELECT auth.user_id() AS user_id, public.towersignal_is_admin() AS is_admin;

GRANT SELECT ON public.company_admin_access TO authenticated;

CREATE TABLE IF NOT EXISTS public.company_private_profiles (
  company_id text PRIMARY KEY,
  canonical_name text NOT NULL,
  legal_name text,
  rollup_name text,
  rollup_company_id text,
  website text,
  headquarters_address text,
  headquarters_city text,
  headquarters_region text,
  headquarters_postal_code text,
  headquarters_country text,
  parent_company_id text,
  parent_company_name text,
  company_type text,
  revenue_amount numeric(18,2),
  revenue_low numeric(18,2),
  revenue_high numeric(18,2),
  revenue_currency text DEFAULT 'USD' NOT NULL,
  revenue_year integer,
  revenue_type text DEFAULT 'unknown' NOT NULL,
  revenue_source_name text,
  revenue_source_url text,
  revenue_confidence text DEFAULT 'unknown' NOT NULL,
  relationship_status text DEFAULT 'uncontacted' NOT NULL,
  last_contacted_at timestamptz,
  next_action_date date,
  account_owner text,
  internal_summary text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  CONSTRAINT company_private_profiles_revenue_type_check CHECK (revenue_type IN ('reported','estimated','range','unknown')),
  CONSTRAINT company_private_profiles_revenue_confidence_check CHECK (revenue_confidence IN ('confirmed','strong','verify','unknown')),
  CONSTRAINT company_private_profiles_relationship_status_check CHECK (relationship_status IN ('uncontacted','researching','outreach-planned','contacted','engaged','opportunity','customer','not-pursuing')),
  CONSTRAINT company_private_profiles_revenue_year_check CHECK (revenue_year IS NULL OR revenue_year BETWEEN 1900 AND 2100),
  CONSTRAINT company_private_profiles_revenue_nonnegative_check CHECK (
    (revenue_amount IS NULL OR revenue_amount >= 0)
    AND (revenue_low IS NULL OR revenue_low >= 0)
    AND (revenue_high IS NULL OR revenue_high >= 0)
  ),
  CONSTRAINT company_private_profiles_revenue_range_check CHECK (revenue_low IS NULL OR revenue_high IS NULL OR revenue_low <= revenue_high)
);

CREATE TABLE IF NOT EXISTS public.company_private_contacts (
  contact_id text PRIMARY KEY,
  company_id text NOT NULL REFERENCES public.company_private_profiles(company_id) ON DELETE CASCADE,
  name text NOT NULL,
  title text,
  email text,
  phone text,
  linkedin_url text,
  notes text,
  active boolean DEFAULT true NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id()
);

CREATE TABLE IF NOT EXISTS public.company_private_activities (
  activity_id text PRIMARY KEY,
  company_id text NOT NULL REFERENCES public.company_private_profiles(company_id) ON DELETE CASCADE,
  activity_type text NOT NULL,
  occurred_at timestamptz NOT NULL,
  contact_id text REFERENCES public.company_private_contacts(contact_id) ON DELETE SET NULL,
  subject text,
  details text,
  outcome text,
  next_action_date date,
  created_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id()
);

CREATE TABLE IF NOT EXISTS public.company_private_notes (
  note_id text PRIMARY KEY,
  company_id text NOT NULL REFERENCES public.company_private_profiles(company_id) ON DELETE CASCADE,
  note text NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id()
);

CREATE INDEX IF NOT EXISTS company_private_profiles_rollup_name_idx ON public.company_private_profiles (rollup_name);
CREATE INDEX IF NOT EXISTS company_private_profiles_parent_idx ON public.company_private_profiles (parent_company_id);
CREATE INDEX IF NOT EXISTS company_private_profiles_relationship_idx ON public.company_private_profiles (relationship_status);
CREATE INDEX IF NOT EXISTS company_private_profiles_next_action_idx ON public.company_private_profiles (next_action_date);
CREATE INDEX IF NOT EXISTS company_private_contacts_company_idx ON public.company_private_contacts (company_id);
CREATE INDEX IF NOT EXISTS company_private_activities_company_date_idx ON public.company_private_activities (company_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS company_private_notes_company_updated_idx ON public.company_private_notes (company_id, updated_at DESC);

ALTER TABLE public.company_private_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_private_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_private_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_private_notes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_private_profiles_admin_only ON public.company_private_profiles;
CREATE POLICY company_private_profiles_admin_only ON public.company_private_profiles
  TO authenticated
  USING (public.towersignal_is_admin())
  WITH CHECK (public.towersignal_is_admin());

DROP POLICY IF EXISTS company_private_contacts_admin_only ON public.company_private_contacts;
CREATE POLICY company_private_contacts_admin_only ON public.company_private_contacts
  TO authenticated
  USING (public.towersignal_is_admin())
  WITH CHECK (public.towersignal_is_admin());

DROP POLICY IF EXISTS company_private_activities_admin_only ON public.company_private_activities;
CREATE POLICY company_private_activities_admin_only ON public.company_private_activities
  TO authenticated
  USING (public.towersignal_is_admin())
  WITH CHECK (public.towersignal_is_admin());

DROP POLICY IF EXISTS company_private_notes_admin_only ON public.company_private_notes;
CREATE POLICY company_private_notes_admin_only ON public.company_private_notes
  TO authenticated
  USING (public.towersignal_is_admin())
  WITH CHECK (public.towersignal_is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_private_profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_private_contacts TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_private_activities TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_private_notes TO authenticated;

COMMIT;
