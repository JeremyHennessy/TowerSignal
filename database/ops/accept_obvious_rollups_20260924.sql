BEGIN;

DO $$
DECLARE
  v_pending integer;
  v_accepted integer;
  v_superseded integer;
  v_active integer;
  v_selected integer;
BEGIN
  SELECT count(*) FILTER (WHERE status='pending'),
         count(*) FILTER (WHERE status='accepted'),
         count(*) FILTER (WHERE status='superseded')
    INTO v_pending,v_accepted,v_superseded
  FROM public.company_rollup_suggestions;

  SELECT count(*) INTO v_active
  FROM public.company_sales_accounts
  WHERE record_status='active';

  SELECT count(*) INTO v_selected
  FROM public.company_rollup_suggestions
  WHERE status='pending'
    AND suggestion_id IN (
      'rollup::sales-account-128f9e12238a5e16596a::sales-account-9af56529abd9946c378f',
      'rollup::sales-account-1bcf3d9cf7df12f53549::sales-account-9af56529abd9946c378f',
      'rollup::sales-account-fe36d183459b721caffc::sales-account-9af56529abd9946c378f',
      'rollup::sales-account-28f65fea1fad6935e56c::sales-account-9af56529abd9946c378f',
      'rollup::sales-account-6eb601c1cab9c1f1cb81::sales-account-454f9e82f6552a974d1b',
      'rollup::sales-account-7e13c4a3fda45638eef0::sales-account-454f9e82f6552a974d1b',
      'rollup::sales-account-9399b6ccde5fcd663f48::sales-account-8da218e08bf548da9160',
      'rollup::sales-account-d262334c358cb15791cf::sales-account-42494fec2d9099ba11b5',
      'rollup::sales-account-6d07da09133302cafc80::sales-account-42494fec2d9099ba11b5',
      'rollup::sales-account-7ac035eeb39c59d537af::sales-account-414c1fd143a3f77e9309',
      'rollup::sales-account-a20303976c88a4b0a81b::sales-account-e4965f2f8550ece768e6'
    );

  IF v_pending<>19 OR v_accepted<>0 OR v_superseded<>0 OR v_active<>101 OR v_selected<>11 THEN
    RAISE EXCEPTION 'Pre-merge guard failed pending=% accepted=% superseded=% active=% selected=%',
      v_pending,v_accepted,v_superseded,v_active,v_selected;
  END IF;
END $$;

DO $$
DECLARE
  suggestion text;
  changed integer;
BEGIN
  FOREACH suggestion IN ARRAY ARRAY[
    'rollup::sales-account-128f9e12238a5e16596a::sales-account-9af56529abd9946c378f',
    'rollup::sales-account-1bcf3d9cf7df12f53549::sales-account-9af56529abd9946c378f',
    'rollup::sales-account-fe36d183459b721caffc::sales-account-9af56529abd9946c378f',
    'rollup::sales-account-28f65fea1fad6935e56c::sales-account-9af56529abd9946c378f',
    'rollup::sales-account-6eb601c1cab9c1f1cb81::sales-account-454f9e82f6552a974d1b',
    'rollup::sales-account-7e13c4a3fda45638eef0::sales-account-454f9e82f6552a974d1b',
    'rollup::sales-account-9399b6ccde5fcd663f48::sales-account-8da218e08bf548da9160',
    'rollup::sales-account-d262334c358cb15791cf::sales-account-42494fec2d9099ba11b5',
    'rollup::sales-account-6d07da09133302cafc80::sales-account-42494fec2d9099ba11b5',
    'rollup::sales-account-7ac035eeb39c59d537af::sales-account-414c1fd143a3f77e9309',
    'rollup::sales-account-a20303976c88a4b0a81b::sales-account-e4965f2f8550ece768e6'
  ] LOOP
    UPDATE public.company_rollup_suggestions
    SET status='accepted',
        reviewed_by='system:user-authorized',
        reviewed_at=now(),
        review_note='User-authorized direct-to-canonical merge after stored profile evidence review on 2026-09-24',
        updated_at=now()
    WHERE suggestion_id=suggestion AND status='pending';
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed<>1 THEN
      RAISE EXCEPTION 'Expected one pending suggestion for %, changed %',suggestion,changed;
    END IF;
  END LOOP;
END $$;

DO $$
DECLARE
  v_pending integer;
  v_accepted integer;
  v_superseded integer;
  v_active integer;
BEGIN
  SELECT count(*) FILTER (WHERE status='pending'),
         count(*) FILTER (WHERE status='accepted'),
         count(*) FILTER (WHERE status='superseded')
    INTO v_pending,v_accepted,v_superseded
  FROM public.company_rollup_suggestions;

  SELECT count(*) INTO v_active
  FROM public.company_sales_accounts
  WHERE record_status='active';

  IF v_pending<>3 OR v_accepted<>11 OR v_superseded<>5 OR v_active<>90 THEN
    RAISE EXCEPTION 'Post-merge state failed pending=% accepted=% superseded=% active=%',
      v_pending,v_accepted,v_superseded,v_active;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.company_sales_account_members m
    JOIN public.company_sales_accounts a ON a.sales_account_id=m.sales_account_id
    WHERE a.record_status='merged'
  ) THEN
    RAISE EXCEPTION 'A source identity remains attached to a merged sales account';
  END IF;
END $$;

COMMIT;

SELECT 'ROLLUP_ACCEPTANCE=PASS' AS result,
       (SELECT count(*) FROM public.company_sales_accounts WHERE record_status='active') AS active_accounts,
       (SELECT count(*) FROM public.company_rollup_suggestions WHERE status='accepted') AS accepted,
       (SELECT count(*) FROM public.company_rollup_suggestions WHERE status='pending') AS pending,
       (SELECT count(*) FROM public.company_rollup_suggestions WHERE status='superseded') AS superseded;
