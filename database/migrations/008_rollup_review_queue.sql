BEGIN;

CREATE TABLE IF NOT EXISTS public.company_rollup_suggestions (
  suggestion_id text PRIMARY KEY,
  candidate_sales_account_id text NOT NULL REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE CASCADE,
  suggested_sales_account_id text NOT NULL REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE CASCADE,
  score integer NOT NULL,
  confidence text NOT NULL,
  evidence jsonb DEFAULT '[]'::jsonb NOT NULL,
  status text DEFAULT 'pending' NOT NULL,
  generated_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  reviewed_at timestamptz,
  reviewed_by text,
  review_note text,
  CONSTRAINT company_rollup_suggestions_pair_unique UNIQUE(candidate_sales_account_id,suggested_sales_account_id),
  CONSTRAINT company_rollup_suggestions_distinct_check CHECK(candidate_sales_account_id<>suggested_sales_account_id),
  CONSTRAINT company_rollup_suggestions_score_check CHECK(score BETWEEN 0 AND 100),
  CONSTRAINT company_rollup_suggestions_confidence_check CHECK(confidence IN ('high','medium','low')),
  CONSTRAINT company_rollup_suggestions_status_check CHECK(status IN ('pending','accepted','rejected','not-same','superseded'))
);

CREATE INDEX IF NOT EXISTS company_rollup_suggestions_status_score_idx
  ON public.company_rollup_suggestions(status,score DESC,generated_at DESC);
CREATE INDEX IF NOT EXISTS company_rollup_suggestions_candidate_idx
  ON public.company_rollup_suggestions(candidate_sales_account_id,status);
CREATE INDEX IF NOT EXISTS company_rollup_suggestions_target_idx
  ON public.company_rollup_suggestions(suggested_sales_account_id,status);

ALTER TABLE public.company_rollup_suggestions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS company_rollup_suggestions_admin_only ON public.company_rollup_suggestions;
CREATE POLICY company_rollup_suggestions_admin_only ON public.company_rollup_suggestions
  TO authenticated USING(public.towersignal_is_admin()) WITH CHECK(public.towersignal_is_admin());
GRANT SELECT,INSERT,UPDATE,DELETE ON public.company_rollup_suggestions TO authenticated;

CREATE OR REPLACE FUNCTION public.towersignal_apply_rollup_suggestion()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,public,auth
AS $$
DECLARE
  candidate_record public.company_sales_accounts%ROWTYPE;
  target_record public.company_sales_accounts%ROWTYPE;
  target_has_primary boolean;
BEGIN
  IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
    NEW.updated_at:=now();
    RETURN NEW;
  END IF;

  IF NEW.status IN ('rejected','not-same') THEN
    NEW.reviewed_at:=COALESCE(NEW.reviewed_at,now());
    NEW.reviewed_by:=COALESCE(NEW.reviewed_by,auth.user_id());
    NEW.updated_at:=now();
    RETURN NEW;
  END IF;

  IF NEW.status <> 'accepted' THEN
    NEW.updated_at:=now();
    RETURN NEW;
  END IF;

  IF OLD.status <> 'pending' THEN
    RAISE EXCEPTION 'Only pending roll-up suggestions can be accepted';
  END IF;

  SELECT * INTO candidate_record
  FROM public.company_sales_accounts
  WHERE sales_account_id=NEW.candidate_sales_account_id
  FOR UPDATE;

  SELECT * INTO target_record
  FROM public.company_sales_accounts
  WHERE sales_account_id=NEW.suggested_sales_account_id
  FOR UPDATE;

  IF candidate_record.sales_account_id IS NULL OR target_record.sales_account_id IS NULL THEN
    RAISE EXCEPTION 'Roll-up accounts are missing';
  END IF;
  IF candidate_record.record_status <> 'active' OR target_record.record_status <> 'active' THEN
    RAISE EXCEPTION 'Both roll-up accounts must be active';
  END IF;

  SELECT EXISTS(
    SELECT 1 FROM public.company_private_contacts
    WHERE sales_account_id=target_record.sales_account_id AND primary_contact AND active
  ) INTO target_has_primary;

  IF target_has_primary THEN
    UPDATE public.company_private_contacts
    SET primary_contact=false,
        updated_at=now(),
        last_change_source='manual',
        last_change_batch_id='rollup-suggestion:'||NEW.suggestion_id
    WHERE sales_account_id=candidate_record.sales_account_id
      AND primary_contact;
  END IF;

  UPDATE public.company_private_profiles p
  SET rollup_company_id=target_record.primary_company_id,
      rollup_name=target_record.display_name,
      rollup_source_name='TowerSignal reviewed roll-up suggestion',
      rollup_source_url=NULL,
      updated_at=now(),
      last_change_source='manual',
      last_change_batch_id='rollup-suggestion:'||NEW.suggestion_id
  WHERE p.company_id IN (
    SELECT company_id
    FROM public.company_sales_account_members
    WHERE sales_account_id=candidate_record.sales_account_id
  );

  UPDATE public.company_sales_account_members
  SET is_primary=false,
      member_type=CASE WHEN member_type='primary-source' THEN 'source-identity' ELSE member_type END,
      relationship_source_name=COALESCE(relationship_source_name,'TowerSignal reviewed roll-up suggestion'),
      relationship_source_url=COALESCE(relationship_source_url,NULL)
  WHERE sales_account_id=candidate_record.sales_account_id;

  UPDATE public.company_sales_account_members
  SET sales_account_id=target_record.sales_account_id
  WHERE sales_account_id=candidate_record.sales_account_id;

  UPDATE public.company_private_contacts
  SET sales_account_id=target_record.sales_account_id,
      updated_at=now(),
      last_change_source='manual',
      last_change_batch_id='rollup-suggestion:'||NEW.suggestion_id
  WHERE sales_account_id=candidate_record.sales_account_id;

  UPDATE public.company_private_activities
  SET sales_account_id=target_record.sales_account_id,
      last_change_source='manual',
      last_change_batch_id='rollup-suggestion:'||NEW.suggestion_id
  WHERE sales_account_id=candidate_record.sales_account_id;

  UPDATE public.company_private_notes
  SET sales_account_id=target_record.sales_account_id,
      updated_at=now(),
      last_change_source='manual',
      last_change_batch_id='rollup-suggestion:'||NEW.suggestion_id
  WHERE sales_account_id=candidate_record.sales_account_id;

  UPDATE public.company_private_research_queue
  SET sales_account_id=target_record.sales_account_id,
      updated_at=now(),
      last_change_source='manual',
      last_change_batch_id='rollup-suggestion:'||NEW.suggestion_id
  WHERE sales_account_id=candidate_record.sales_account_id;

  UPDATE public.company_private_opportunities
  SET sales_account_id=target_record.sales_account_id,
      company_id=target_record.primary_company_id,
      updated_at=now(),
      last_change_source='manual',
      last_change_batch_id='rollup-suggestion:'||NEW.suggestion_id
  WHERE sales_account_id=candidate_record.sales_account_id;

  UPDATE public.company_private_tasks
  SET sales_account_id=target_record.sales_account_id,
      company_id=target_record.primary_company_id,
      updated_at=now(),
      last_change_source='manual',
      last_change_batch_id='rollup-suggestion:'||NEW.suggestion_id
  WHERE sales_account_id=candidate_record.sales_account_id;

  UPDATE public.company_sales_accounts
  SET record_status='merged',
      merged_into_sales_account_id=target_record.sales_account_id,
      updated_at=now(),
      last_change_source='manual',
      last_change_batch_id='rollup-suggestion:'||NEW.suggestion_id
  WHERE sales_account_id=candidate_record.sales_account_id;

  UPDATE public.company_rollup_suggestions
  SET status='superseded',
      reviewed_at=now(),
      reviewed_by=auth.user_id(),
      review_note=COALESCE(review_note,'Superseded by accepted merge '||NEW.suggestion_id),
      updated_at=now()
  WHERE suggestion_id<>NEW.suggestion_id
    AND status='pending'
    AND (
      candidate_sales_account_id=candidate_record.sales_account_id
      OR suggested_sales_account_id=candidate_record.sales_account_id
    );

  NEW.reviewed_at:=COALESCE(NEW.reviewed_at,now());
  NEW.reviewed_by:=COALESCE(NEW.reviewed_by,auth.user_id());
  NEW.updated_at:=now();
  RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.towersignal_apply_rollup_suggestion() FROM PUBLIC;

DROP TRIGGER IF EXISTS company_rollup_suggestion_apply ON public.company_rollup_suggestions;
CREATE TRIGGER company_rollup_suggestion_apply
BEFORE UPDATE OF status ON public.company_rollup_suggestions
FOR EACH ROW EXECUTE FUNCTION public.towersignal_apply_rollup_suggestion();

COMMIT;
