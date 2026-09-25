BEGIN;

-- Additive foundation. Existing parents, membership mappings and CRM values are not backfilled or changed.
CREATE TABLE IF NOT EXISTS public.company_parent_entities (
  parent_entity_id text PRIMARY KEY DEFAULT gen_random_uuid()::text,
  display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 240),
  website text,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text DEFAULT auth.user_id()
);

CREATE TABLE IF NOT EXISTS public.company_parent_relationships (
  relationship_id text PRIMARY KEY DEFAULT gen_random_uuid()::text,
  sales_account_id text NOT NULL REFERENCES public.company_sales_accounts(sales_account_id),
  parent_entity_id text NOT NULL REFERENCES public.company_parent_entities(parent_entity_id),
  relationship_type text NOT NULL CHECK (relationship_type IN ('parent','ultimate-parent')),
  evidence_url text NOT NULL CHECK (evidence_url ~ '^https://[^[:space:]]+$'),
  evidence_note text NOT NULL CHECK (length(btrim(evidence_note)) BETWEEN 1 AND 2000),
  observed_on date NOT NULL,
  valid_from date,
  valid_to date,
  status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','confirmed','disputed','historical')),
  reviewed_at timestamptz,
  reviewed_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
  CHECK (status <> 'confirmed' OR valid_to IS NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS company_parent_one_current
  ON public.company_parent_relationships(sales_account_id,relationship_type) WHERE status='confirmed';

CREATE TABLE IF NOT EXISTS public.company_enrichment_sources (
  source_id text PRIMARY KEY DEFAULT gen_random_uuid()::text,
  sales_account_id text NOT NULL REFERENCES public.company_sales_accounts(sales_account_id),
  source_url text NOT NULL CHECK (source_url ~ '^https://[^[:space:]]+$'),
  expected_name text NOT NULL CHECK (length(btrim(expected_name)) BETWEEN 1 AND 240),
  enabled boolean NOT NULL DEFAULT false,
  approved_at timestamptz,
  approved_by text,
  last_attempt_at timestamptz,
  last_success_at timestamptz,
  last_outcome text CHECK (last_outcome IN ('observed','no-structured-data','identity-unresolved','failed')),
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(sales_account_id,source_url),
  UNIQUE(source_id,sales_account_id)
);

CREATE TABLE IF NOT EXISTS public.company_enrichment_runs (
  run_id text PRIMARY KEY DEFAULT gen_random_uuid()::text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  status text NOT NULL CHECK (status IN ('running','success','partial','failed')),
  checked_count integer NOT NULL DEFAULT 0 CHECK (checked_count>=0),
  observed_count integer NOT NULL DEFAULT 0 CHECK (observed_count>=0),
  unresolved_count integer NOT NULL DEFAULT 0 CHECK (unresolved_count>=0),
  failed_count integer NOT NULL DEFAULT 0 CHECK (failed_count>=0),
  candidate_count integer NOT NULL DEFAULT 0 CHECK (candidate_count>=0),
  workflow_url text
);

CREATE TABLE IF NOT EXISTS public.company_enrichment_candidates (
  candidate_id text PRIMARY KEY,
  sales_account_id text NOT NULL REFERENCES public.company_sales_accounts(sales_account_id),
  source_id text NOT NULL REFERENCES public.company_enrichment_sources(source_id),
  field_name text NOT NULL CHECK (field_name IN ('legal_name','headquarters','parent_company_name')),
  proposed_value jsonb NOT NULL,
  source_url text NOT NULL CHECK (source_url ~ '^https://[^[:space:]]+$'),
  evidence_excerpt text NOT NULL,
  content_sha256 text NOT NULL,
  first_observed_at timestamptz NOT NULL DEFAULT now(),
  last_observed_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','reviewed','rejected')),
  review_note text,
  reviewed_at timestamptz,
  reviewed_by text,
  FOREIGN KEY(source_id,sales_account_id) REFERENCES public.company_enrichment_sources(source_id,sales_account_id)
);
CREATE INDEX IF NOT EXISTS company_enrichment_candidate_review ON public.company_enrichment_candidates(status,last_observed_at DESC);

CREATE OR REPLACE FUNCTION public.towersignal_review_company_evidence()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,auth AS $$
BEGIN
  IF NOT EXISTS(SELECT 1 FROM public.company_sales_accounts WHERE sales_account_id=NEW.sales_account_id AND record_status='active') THEN
    RAISE EXCEPTION 'Evidence must belong to an active master account';
  END IF;
  IF TG_TABLE_NAME='company_enrichment_sources' THEN
    IF NEW.enabled AND (TG_OP='INSERT' OR NOT OLD.enabled OR NEW.source_url IS DISTINCT FROM OLD.source_url OR NEW.expected_name IS DISTINCT FROM OLD.expected_name) THEN
      NEW.approved_at:=now(); NEW.approved_by:=auth.user_id();
    END IF;
    RETURN NEW;
  END IF;
  IF TG_OP='INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
    IF NEW.status IN ('confirmed','reviewed','rejected','disputed','historical') THEN
      NEW.reviewed_at:=now(); NEW.reviewed_by:=auth.user_id();
    END IF;
  END IF;
  RETURN NEW;
END $$;

DO $$ DECLARE t text; id_column text;
BEGIN
  FOREACH t IN ARRAY ARRAY['company_parent_entities','company_parent_relationships','company_enrichment_sources','company_enrichment_runs','company_enrichment_candidates'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('DROP POLICY IF EXISTS admin_only ON public.%I',t);
    EXECUTE format('CREATE POLICY admin_only ON public.%I TO authenticated USING(public.towersignal_is_admin()) WITH CHECK(public.towersignal_is_admin())',t);
    EXECUTE format('GRANT SELECT ON public.%I TO authenticated',t);
    id_column:=CASE t WHEN 'company_parent_entities' THEN 'parent_entity_id' WHEN 'company_parent_relationships' THEN 'relationship_id' WHEN 'company_enrichment_sources' THEN 'source_id' WHEN 'company_enrichment_runs' THEN 'run_id' ELSE 'candidate_id' END;
    EXECUTE format('DROP TRIGGER IF EXISTS audit_evidence ON public.%I',t);
    EXECUTE format('CREATE TRIGGER audit_evidence AFTER INSERT OR UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_sales_account(%L,%L)',t,t,id_column);
    IF t IN ('company_parent_relationships','company_enrichment_sources','company_enrichment_candidates') THEN
      EXECUTE format('DROP TRIGGER IF EXISTS review_evidence ON public.%I',t);
      EXECUTE format('CREATE TRIGGER review_evidence BEFORE INSERT OR UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.towersignal_review_company_evidence()',t);
    END IF;
  END LOOP;
END $$;

GRANT INSERT ON public.company_parent_entities TO authenticated;
GRANT INSERT,UPDATE ON public.company_parent_relationships TO authenticated;
GRANT INSERT ON public.company_enrichment_sources TO authenticated;
GRANT UPDATE(enabled,source_url,expected_name) ON public.company_enrichment_sources TO authenticated;
GRANT UPDATE(status,review_note) ON public.company_enrichment_candidates TO authenticated;

CREATE OR REPLACE FUNCTION public.towersignal_guard_evidence_account_merge()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
BEGIN
  IF NEW.record_status='merged' AND OLD.record_status='active' AND (
    EXISTS(SELECT 1 FROM public.company_parent_relationships WHERE sales_account_id=OLD.sales_account_id AND status IN ('proposed','confirmed')) OR
    EXISTS(SELECT 1 FROM public.company_enrichment_sources WHERE sales_account_id=OLD.sales_account_id AND enabled) OR
    EXISTS(SELECT 1 FROM public.company_enrichment_candidates WHERE sales_account_id=OLD.sales_account_id AND status='pending')
  ) THEN
    RAISE EXCEPTION 'Review pending enrichment, pause sources and archive active parent links before merging this account';
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS company_evidence_merge_guard ON public.company_sales_accounts;
CREATE TRIGGER company_evidence_merge_guard BEFORE UPDATE OF record_status ON public.company_sales_accounts
FOR EACH ROW EXECUTE FUNCTION public.towersignal_guard_evidence_account_merge();

-- Reviewed means evidence was reviewed, never automatic publication of a profile or identity change.
-- The existing source profile editor remains the explicit publication path.
COMMIT;
