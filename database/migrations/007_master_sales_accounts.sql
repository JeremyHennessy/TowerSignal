BEGIN;

CREATE TABLE IF NOT EXISTS public.company_sales_accounts (
  sales_account_id text PRIMARY KEY,
  primary_company_id text NOT NULL UNIQUE REFERENCES public.company_private_profiles(company_id) ON DELETE RESTRICT,
  display_name text NOT NULL,
  account_classification text DEFAULT 'target' NOT NULL,
  record_status text DEFAULT 'active' NOT NULL,
  merged_into_sales_account_id text,
  parent_name text,
  parent_source_url text,
  account_owner text,
  sales_notes text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  last_change_source text DEFAULT 'system' NOT NULL,
  last_change_batch_id text,
  CONSTRAINT company_sales_accounts_classification_check CHECK (
    account_classification IN (
      'target','active-prospect','customer','former-customer',
      'partner','competitor','do-not-pursue'
    )
  ),
  CONSTRAINT company_sales_accounts_record_status_check CHECK (record_status IN ('active','merged')),
  CONSTRAINT company_sales_accounts_source_check CHECK (last_change_source IN ('manual','import','system','database'))
);

ALTER TABLE public.company_sales_accounts
  DROP CONSTRAINT IF EXISTS company_sales_accounts_merged_into_fk;
ALTER TABLE public.company_sales_accounts
  ADD CONSTRAINT company_sales_accounts_merged_into_fk
  FOREIGN KEY (merged_into_sales_account_id)
  REFERENCES public.company_sales_accounts(sales_account_id)
  ON DELETE RESTRICT;

CREATE TABLE IF NOT EXISTS public.company_sales_account_members (
  sales_account_id text NOT NULL REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE CASCADE,
  company_id text NOT NULL UNIQUE REFERENCES public.company_private_profiles(company_id) ON DELETE RESTRICT,
  member_type text DEFAULT 'source-identity' NOT NULL,
  is_primary boolean DEFAULT false NOT NULL,
  relationship_source_name text,
  relationship_source_url text,
  created_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  CONSTRAINT company_sales_account_members_pkey PRIMARY KEY (sales_account_id, company_id),
  CONSTRAINT company_sales_account_members_type_check CHECK (
    member_type IN ('primary-source','source-identity','brand','subsidiary','legal-entity')
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS company_sales_account_one_primary_idx
  ON public.company_sales_account_members(sales_account_id)
  WHERE is_primary;
CREATE INDEX IF NOT EXISTS company_sales_accounts_classification_idx
  ON public.company_sales_accounts(account_classification, record_status);
CREATE INDEX IF NOT EXISTS company_sales_accounts_parent_idx
  ON public.company_sales_accounts(parent_name);
CREATE INDEX IF NOT EXISTS company_sales_members_account_idx
  ON public.company_sales_account_members(sales_account_id);

ALTER TABLE public.company_private_contacts
  ADD COLUMN IF NOT EXISTS sales_account_id text REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE RESTRICT;
ALTER TABLE public.company_private_activities
  ADD COLUMN IF NOT EXISTS sales_account_id text REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE RESTRICT;
ALTER TABLE public.company_private_notes
  ADD COLUMN IF NOT EXISTS sales_account_id text REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE RESTRICT;
ALTER TABLE public.company_private_research_queue
  ADD COLUMN IF NOT EXISTS sales_account_id text REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE RESTRICT;
ALTER TABLE public.company_private_opportunities
  ADD COLUMN IF NOT EXISTS sales_account_id text REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE RESTRICT;
ALTER TABLE public.company_private_tasks
  ADD COLUMN IF NOT EXISTS sales_account_id text REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS company_contacts_sales_account_idx
  ON public.company_private_contacts(sales_account_id, active);
CREATE INDEX IF NOT EXISTS company_activities_sales_account_idx
  ON public.company_private_activities(sales_account_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS company_notes_sales_account_idx
  ON public.company_private_notes(sales_account_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS company_research_sales_account_idx
  ON public.company_private_research_queue(sales_account_id, priority_score DESC);
CREATE INDEX IF NOT EXISTS company_opportunities_sales_account_idx
  ON public.company_private_opportunities(sales_account_id, stage, updated_at DESC);
CREATE INDEX IF NOT EXISTS company_tasks_sales_account_idx
  ON public.company_private_tasks(sales_account_id, status, due_at);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM public.company_private_profiles p
    LEFT JOIN public.company_private_profiles master
      ON master.company_id=p.rollup_company_id
    WHERE p.rollup_company_id IS NOT NULL
      AND master.company_id IS NULL
  ) THEN
    RAISE EXCEPTION 'Cannot create sales accounts: a reviewed rollup points to a missing master profile';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.company_private_profiles p
    JOIN public.company_private_profiles master
      ON master.company_id=p.rollup_company_id
    WHERE p.rollup_company_id IS NOT NULL
      AND master.rollup_company_id IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'Cannot create sales accounts: nested reviewed rollups require explicit normalization first';
  END IF;
END $$;

WITH resolved AS (
  SELECT
    p.*,
    COALESCE(p.rollup_company_id,p.company_id) AS master_company_id
  FROM public.company_private_profiles p
),
masters AS (
  SELECT DISTINCT ON (r.master_company_id)
    r.master_company_id,
    master.canonical_name,
    master.legal_name,
    master.rollup_name,
    master.parent_company_name,
    master.parent_source_url,
    master.account_owner,
    master.internal_summary,
    master.relationship_status
  FROM resolved r
  JOIN public.company_private_profiles master
    ON master.company_id=r.master_company_id
  ORDER BY r.master_company_id
)
INSERT INTO public.company_sales_accounts (
  sales_account_id,
  primary_company_id,
  display_name,
  account_classification,
  parent_name,
  parent_source_url,
  account_owner,
  sales_notes,
  last_change_source,
  last_change_batch_id
)
SELECT
  'sales-account-' || substr(md5(master_company_id),1,20),
  master_company_id,
  COALESCE(NULLIF(rollup_name,''),NULLIF(legal_name,''),canonical_name),
  CASE relationship_status
    WHEN 'customer' THEN 'customer'
    WHEN 'not-pursuing' THEN 'do-not-pursue'
    WHEN 'contacted' THEN 'active-prospect'
    WHEN 'engaged' THEN 'active-prospect'
    WHEN 'opportunity' THEN 'active-prospect'
    WHEN 'outreach-planned' THEN 'active-prospect'
    ELSE 'target'
  END,
  parent_company_name,
  parent_source_url,
  account_owner,
  internal_summary,
  'system',
  'master-sales-account-migration-20260924'
FROM masters
ON CONFLICT (sales_account_id) DO NOTHING;

WITH resolved AS (
  SELECT
    p.company_id,
    p.canonical_name,
    p.rollup_company_id,
    p.rollup_source_name,
    p.rollup_source_url,
    COALESCE(p.rollup_company_id,p.company_id) AS master_company_id
  FROM public.company_private_profiles p
)
INSERT INTO public.company_sales_account_members (
  sales_account_id,
  company_id,
  member_type,
  is_primary,
  relationship_source_name,
  relationship_source_url
)
SELECT
  'sales-account-' || substr(md5(master_company_id),1,20),
  company_id,
  CASE WHEN company_id=master_company_id THEN 'primary-source' ELSE 'source-identity' END,
  company_id=master_company_id,
  CASE WHEN company_id=master_company_id THEN NULL ELSE rollup_source_name END,
  CASE WHEN company_id=master_company_id THEN NULL ELSE rollup_source_url END
FROM resolved
ON CONFLICT (company_id) DO NOTHING;

UPDATE public.company_private_contacts c
SET sales_account_id=m.sales_account_id
FROM public.company_sales_account_members m
WHERE m.company_id=c.company_id
  AND c.sales_account_id IS NULL;

UPDATE public.company_private_activities a
SET sales_account_id=m.sales_account_id
FROM public.company_sales_account_members m
WHERE m.company_id=a.company_id
  AND a.sales_account_id IS NULL;

UPDATE public.company_private_notes n
SET sales_account_id=m.sales_account_id
FROM public.company_sales_account_members m
WHERE m.company_id=n.company_id
  AND n.sales_account_id IS NULL;

UPDATE public.company_private_research_queue q
SET sales_account_id=m.sales_account_id
FROM public.company_sales_account_members m
WHERE m.company_id=q.company_id
  AND q.sales_account_id IS NULL;

UPDATE public.company_private_opportunities o
SET sales_account_id=m.sales_account_id
FROM public.company_sales_account_members m
WHERE m.company_id=o.company_id
  AND o.sales_account_id IS NULL;

UPDATE public.company_private_tasks t
SET sales_account_id=m.sales_account_id
FROM public.company_sales_account_members m
WHERE m.company_id=t.company_id
  AND t.sales_account_id IS NULL;

ALTER TABLE public.company_sales_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_sales_account_members ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_sales_accounts_admin_only ON public.company_sales_accounts;
CREATE POLICY company_sales_accounts_admin_only ON public.company_sales_accounts
  TO authenticated USING (public.towersignal_is_admin()) WITH CHECK (public.towersignal_is_admin());

DROP POLICY IF EXISTS company_sales_account_members_admin_only ON public.company_sales_account_members;
CREATE POLICY company_sales_account_members_admin_only ON public.company_sales_account_members
  TO authenticated USING (public.towersignal_is_admin()) WITH CHECK (public.towersignal_is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_sales_accounts TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_sales_account_members TO authenticated;

CREATE TABLE IF NOT EXISTS public.company_sales_change_log (
  change_id bigserial PRIMARY KEY,
  sales_account_id text NOT NULL,
  entity_type text NOT NULL,
  entity_id text NOT NULL,
  operation text NOT NULL,
  snapshot jsonb NOT NULL,
  changed_at timestamptz DEFAULT now() NOT NULL,
  changed_by text
);
CREATE INDEX IF NOT EXISTS company_sales_change_account_time_idx
  ON public.company_sales_change_log(sales_account_id,changed_at DESC);
ALTER TABLE public.company_sales_change_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS company_sales_change_log_admin_read ON public.company_sales_change_log;
CREATE POLICY company_sales_change_log_admin_read ON public.company_sales_change_log
  FOR SELECT TO authenticated USING (public.towersignal_is_admin());
GRANT SELECT ON public.company_sales_change_log TO authenticated;

CREATE OR REPLACE FUNCTION public.towersignal_audit_sales_account()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,public,auth
AS $$
DECLARE
  row_data jsonb;
  account_value text;
  entity_value text;
BEGIN
  row_data := CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
  account_value := COALESCE(row_data->>'sales_account_id','');
  entity_value := COALESCE(row_data->>TG_ARGV[1],account_value);
  INSERT INTO public.company_sales_change_log(
    sales_account_id,entity_type,entity_id,operation,snapshot,changed_by
  ) VALUES (
    account_value,TG_ARGV[0],entity_value,TG_OP,row_data,auth.user_id()
  );
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.towersignal_audit_sales_account() FROM PUBLIC;

DROP TRIGGER IF EXISTS company_sales_accounts_audit ON public.company_sales_accounts;
CREATE TRIGGER company_sales_accounts_audit
AFTER INSERT OR UPDATE OR DELETE ON public.company_sales_accounts
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_sales_account('sales-account','sales_account_id');

DROP TRIGGER IF EXISTS company_sales_members_audit ON public.company_sales_account_members;
CREATE TRIGGER company_sales_members_audit
AFTER INSERT OR UPDATE OR DELETE ON public.company_sales_account_members
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_sales_account('sales-account-member','company_id');

DO $$
DECLARE
  v_profiles integer;
  v_rollups integer;
  v_expected_accounts integer;
  v_accounts integer;
  v_members integer;
  v_primary_members integer;
BEGIN
  SELECT count(*) INTO v_profiles FROM public.company_private_profiles;
  SELECT count(*) INTO v_rollups FROM public.company_private_profiles WHERE rollup_company_id IS NOT NULL;
  SELECT count(DISTINCT COALESCE(rollup_company_id,company_id)) INTO v_expected_accounts FROM public.company_private_profiles;
  SELECT count(*) INTO v_accounts FROM public.company_sales_accounts WHERE record_status='active';
  SELECT count(*) INTO v_members FROM public.company_sales_account_members;
  SELECT count(*) INTO v_primary_members FROM public.company_sales_account_members WHERE is_primary;

  IF v_members <> v_profiles THEN
    RAISE EXCEPTION 'Sales-account migration lost source identities: profiles=% members=%',v_profiles,v_members;
  END IF;
  IF v_accounts <> v_expected_accounts OR v_primary_members <> v_expected_accounts THEN
    RAISE EXCEPTION 'Sales-account migration account mismatch: expected=% accounts=% primary=%',v_expected_accounts,v_accounts,v_primary_members;
  END IF;
  IF v_profiles - v_expected_accounts <> v_rollups THEN
    RAISE EXCEPTION 'Reviewed rollup preservation mismatch: profiles=% accounts=% rollups=%',v_profiles,v_expected_accounts,v_rollups;
  END IF;
  IF EXISTS (
    SELECT 1
    FROM public.company_private_profiles p
    JOIN public.company_sales_account_members m ON m.company_id=p.company_id
    JOIN public.company_sales_accounts a ON a.sales_account_id=m.sales_account_id
    WHERE COALESCE(p.rollup_company_id,p.company_id) <> a.primary_company_id
  ) THEN
    RAISE EXCEPTION 'Sales-account migration changed a reviewed master decision';
  END IF;
END $$;

COMMIT;
