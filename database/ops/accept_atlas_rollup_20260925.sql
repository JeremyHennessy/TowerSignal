BEGIN;

DO $$
DECLARE
  v_pending integer;
  v_accepted integer;
  v_active integer;
BEGIN
  SELECT count(*) FILTER (WHERE status='pending'),
         count(*) FILTER (WHERE status='accepted')
    INTO v_pending,v_accepted
  FROM public.company_rollup_suggestions;

  SELECT count(*) INTO v_active
  FROM public.company_sales_accounts
  WHERE record_status='active';

  IF v_pending<>3 OR v_accepted<>11 OR v_active<>90 THEN
    RAISE EXCEPTION 'Atlas roll-up precheck failed pending=% accepted=% active=%',
      v_pending,v_accepted,v_active;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.company_rollup_suggestions
    WHERE suggestion_id='rollup::sales-account-f7674368b06d45bc5f9d::sales-account-9ee6fe90f7e2f96b24b2'
      AND status='pending'
      AND candidate_sales_account_id='sales-account-f7674368b06d45bc5f9d'
      AND suggested_sales_account_id='sales-account-9ee6fe90f7e2f96b24b2'
  ) THEN
    RAISE EXCEPTION 'Expected Atlas roll-up suggestion is not pending';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.company_sales_accounts
    WHERE sales_account_id='sales-account-f7674368b06d45bc5f9d'
      AND display_name='Atlas Enivronmental'
      AND record_status='active'
  ) OR NOT EXISTS (
    SELECT 1 FROM public.company_sales_accounts
    WHERE sales_account_id='sales-account-9ee6fe90f7e2f96b24b2'
      AND display_name='Atlas Environmental Lab'
      AND record_status='active'
  ) THEN
    RAISE EXCEPTION 'Atlas account identity guard failed';
  END IF;
END $$;

UPDATE public.company_rollup_suggestions
SET status='accepted',
    reviewed_by='system:evidence-reviewed',
    reviewed_at=now(),
    review_note='Accepted after source-evidence audit: all 4 candidate sites are a subset of the canonical Atlas Environmental Lab site set (4/4 overlap); candidate spelling is a one-edit typo.',
    updated_at=now()
WHERE suggestion_id='rollup::sales-account-f7674368b06d45bc5f9d::sales-account-9ee6fe90f7e2f96b24b2'
  AND status='pending';

DO $$
DECLARE
  v_pending integer;
  v_accepted integer;
  v_active integer;
BEGIN
  SELECT count(*) FILTER (WHERE status='pending'),
         count(*) FILTER (WHERE status='accepted')
    INTO v_pending,v_accepted
  FROM public.company_rollup_suggestions;
  SELECT count(*) INTO v_active
  FROM public.company_sales_accounts
  WHERE record_status='active';

  IF v_pending<>2 OR v_accepted<>12 OR v_active<>89 THEN
    RAISE EXCEPTION 'Atlas roll-up acceptance failed pending=% accepted=% active=%',
      v_pending,v_accepted,v_active;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.company_sales_accounts
    WHERE sales_account_id='sales-account-f7674368b06d45bc5f9d'
      AND record_status='merged'
      AND merged_into_sales_account_id='sales-account-9ee6fe90f7e2f96b24b2'
  ) THEN
    RAISE EXCEPTION 'Atlas candidate was not merged into canonical account';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.company_sales_account_members
    WHERE sales_account_id='sales-account-f7674368b06d45bc5f9d'
  ) THEN
    RAISE EXCEPTION 'Atlas source identity remains on merged sales account';
  END IF;
END $$;

COMMIT;

SELECT 'ATLAS_ROLLUP=PASS' AS result,
       (SELECT count(*) FROM public.company_sales_accounts WHERE record_status='active') AS active_accounts,
       (SELECT count(*) FROM public.company_rollup_suggestions WHERE status='pending') AS pending_suggestions,
       (SELECT count(*) FROM public.company_rollup_suggestions WHERE status='accepted') AS accepted_suggestions;
