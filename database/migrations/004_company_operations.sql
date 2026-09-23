BEGIN;

ALTER TABLE public.company_private_profiles
  ADD COLUMN IF NOT EXISTS last_change_source text DEFAULT 'manual' NOT NULL,
  ADD COLUMN IF NOT EXISTS last_change_batch_id text;
ALTER TABLE public.company_private_contacts
  ADD COLUMN IF NOT EXISTS last_change_source text DEFAULT 'manual' NOT NULL,
  ADD COLUMN IF NOT EXISTS last_change_batch_id text;
ALTER TABLE public.company_private_activities
  ADD COLUMN IF NOT EXISTS last_change_source text DEFAULT 'manual' NOT NULL,
  ADD COLUMN IF NOT EXISTS last_change_batch_id text;
ALTER TABLE public.company_private_notes
  ADD COLUMN IF NOT EXISTS last_change_source text DEFAULT 'manual' NOT NULL,
  ADD COLUMN IF NOT EXISTS last_change_batch_id text;

ALTER TABLE public.company_private_profiles DROP CONSTRAINT IF EXISTS company_private_profiles_change_source_check;
ALTER TABLE public.company_private_profiles ADD CONSTRAINT company_private_profiles_change_source_check CHECK (last_change_source IN ('manual','import','system','database'));
ALTER TABLE public.company_private_contacts DROP CONSTRAINT IF EXISTS company_private_contacts_change_source_check;
ALTER TABLE public.company_private_contacts ADD CONSTRAINT company_private_contacts_change_source_check CHECK (last_change_source IN ('manual','import','system','database'));
ALTER TABLE public.company_private_activities DROP CONSTRAINT IF EXISTS company_private_activities_change_source_check;
ALTER TABLE public.company_private_activities ADD CONSTRAINT company_private_activities_change_source_check CHECK (last_change_source IN ('manual','import','system','database'));
ALTER TABLE public.company_private_notes DROP CONSTRAINT IF EXISTS company_private_notes_change_source_check;
ALTER TABLE public.company_private_notes ADD CONSTRAINT company_private_notes_change_source_check CHECK (last_change_source IN ('manual','import','system','database'));

CREATE TABLE IF NOT EXISTS public.company_private_research_queue (
  company_id text PRIMARY KEY REFERENCES public.company_private_profiles(company_id) ON DELETE CASCADE,
  priority_score integer NOT NULL,
  priority_reason text NOT NULL,
  missing_fields jsonb DEFAULT '[]'::jsonb NOT NULL,
  status text DEFAULT 'unreviewed' NOT NULL,
  research_owner text,
  last_researched_at timestamptz,
  queued_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  last_change_source text DEFAULT 'system' NOT NULL,
  last_change_batch_id text,
  CONSTRAINT company_private_research_priority_check CHECK (priority_score BETWEEN 0 AND 100),
  CONSTRAINT company_private_research_status_check CHECK (status IN ('unreviewed','researching','verified','needs-review','complete')),
  CONSTRAINT company_private_research_source_check CHECK (last_change_source IN ('manual','import','system','database'))
);

CREATE INDEX IF NOT EXISTS company_private_research_status_priority_idx
  ON public.company_private_research_queue (status, priority_score DESC);

CREATE TABLE IF NOT EXISTS public.company_private_change_log (
  change_id bigserial PRIMARY KEY,
  company_id text NOT NULL,
  entity_type text NOT NULL,
  entity_id text NOT NULL,
  operation text NOT NULL,
  field_name text NOT NULL,
  old_value jsonb,
  new_value jsonb,
  change_source text DEFAULT 'database' NOT NULL,
  import_batch_id text,
  changed_at timestamptz DEFAULT now() NOT NULL,
  changed_by text,
  CONSTRAINT company_private_change_source_check CHECK (change_source IN ('manual','import','system','database'))
);
CREATE INDEX IF NOT EXISTS company_private_change_company_time_idx
  ON public.company_private_change_log (company_id, changed_at DESC);

ALTER TABLE public.company_private_research_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_private_change_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_private_research_admin_only ON public.company_private_research_queue;
CREATE POLICY company_private_research_admin_only ON public.company_private_research_queue
  TO authenticated USING (public.towersignal_is_admin()) WITH CHECK (public.towersignal_is_admin());

DROP POLICY IF EXISTS company_private_change_log_admin_read ON public.company_private_change_log;
CREATE POLICY company_private_change_log_admin_read ON public.company_private_change_log
  FOR SELECT TO authenticated USING (public.towersignal_is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_private_research_queue TO authenticated;
GRANT SELECT ON public.company_private_change_log TO authenticated;

CREATE OR REPLACE FUNCTION public.towersignal_audit_company_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
  old_row jsonb;
  new_row jsonb;
  field_name text;
  old_value jsonb;
  new_value jsonb;
  company_value text;
  entity_value text;
  source_value text;
  batch_value text;
BEGIN
  old_row := CASE WHEN TG_OP = 'INSERT' THEN '{}'::jsonb ELSE to_jsonb(OLD) END;
  new_row := CASE WHEN TG_OP = 'DELETE' THEN '{}'::jsonb ELSE to_jsonb(NEW) END;
  company_value := COALESCE(new_row->>'company_id', old_row->>'company_id', '');
  entity_value := COALESCE(new_row->>TG_ARGV[1], old_row->>TG_ARGV[1], company_value);
  source_value := COALESCE(new_row->>'last_change_source', old_row->>'last_change_source', 'database');
  batch_value := COALESCE(new_row->>'last_change_batch_id', old_row->>'last_change_batch_id');

  FOR field_name IN SELECT jsonb_object_keys(old_row || new_row)
  LOOP
    IF field_name IN ('created_at','updated_at','created_by','updated_by','last_change_source','last_change_batch_id') THEN CONTINUE; END IF;
    old_value := old_row->field_name;
    new_value := new_row->field_name;
    IF old_value IS DISTINCT FROM new_value THEN
      INSERT INTO public.company_private_change_log (
        company_id, entity_type, entity_id, operation, field_name,
        old_value, new_value, change_source, import_batch_id, changed_by
      ) VALUES (
        company_value, TG_ARGV[0], entity_value, TG_OP, field_name,
        old_value, new_value, source_value, batch_value, auth.user_id()
      );
    END IF;
  END LOOP;

  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.towersignal_audit_company_change() FROM PUBLIC;

DROP TRIGGER IF EXISTS company_private_profiles_audit ON public.company_private_profiles;
CREATE TRIGGER company_private_profiles_audit AFTER INSERT OR UPDATE OR DELETE ON public.company_private_profiles
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_company_change('profile','company_id');
DROP TRIGGER IF EXISTS company_private_contacts_audit ON public.company_private_contacts;
CREATE TRIGGER company_private_contacts_audit AFTER INSERT OR UPDATE OR DELETE ON public.company_private_contacts
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_company_change('contact','contact_id');
DROP TRIGGER IF EXISTS company_private_activities_audit ON public.company_private_activities;
CREATE TRIGGER company_private_activities_audit AFTER INSERT OR UPDATE OR DELETE ON public.company_private_activities
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_company_change('activity','activity_id');
DROP TRIGGER IF EXISTS company_private_notes_audit ON public.company_private_notes;
CREATE TRIGGER company_private_notes_audit AFTER INSERT OR UPDATE OR DELETE ON public.company_private_notes
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_company_change('note','note_id');
DROP TRIGGER IF EXISTS company_private_research_audit ON public.company_private_research_queue;
CREATE TRIGGER company_private_research_audit AFTER INSERT OR UPDATE OR DELETE ON public.company_private_research_queue
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_company_change('research','company_id');

COMMIT;
