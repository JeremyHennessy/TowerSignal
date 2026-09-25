-- Aggregate-only audit. No company/contact values are emitted to public Actions logs.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';
WITH active AS (
  SELECT a.*, p.parent_company_name AS profile_parent, p.parent_source_url AS profile_parent_source,
    p.website, p.headquarters_address, p.company_type, p.identity_source_url,
    p.enrichment_checked_at, p.revenue_amount, p.revenue_low, p.revenue_high
  FROM public.company_sales_accounts a
  JOIN public.company_private_profiles p ON p.company_id = a.primary_company_id
  WHERE a.record_status = 'active'
), coverage AS (
  SELECT count(*) AS accounts,
    count(*) FILTER (WHERE nullif(btrim(website),'') IS NOT NULL) AS with_website,
    count(*) FILTER (WHERE nullif(btrim(headquarters_address),'') IS NOT NULL) AS with_hq,
    count(*) FILTER (WHERE nullif(btrim(company_type),'') IS NOT NULL) AS with_company_type,
    count(*) FILTER (WHERE nullif(btrim(identity_source_url),'') IS NOT NULL) AS with_identity_source,
    count(*) FILTER (WHERE coalesce(nullif(btrim(parent_name),''),nullif(btrim(profile_parent),'')) IS NOT NULL) AS with_parent_name,
    count(*) FILTER (WHERE nullif(btrim(parent_name),'') IS NOT NULL AND nullif(btrim(parent_source_url),'') IS NOT NULL) AS with_account_parent_source,
    count(*) FILTER (WHERE coalesce(nullif(btrim(parent_name),''),nullif(btrim(profile_parent),'')) IS NOT NULL
      AND coalesce(nullif(btrim(parent_source_url),''),nullif(btrim(profile_parent_source),'')) IS NULL) AS parent_without_source,
    count(*) FILTER (WHERE nullif(btrim(parent_name),'') IS NOT NULL AND nullif(btrim(profile_parent),'') IS NOT NULL
      AND lower(btrim(parent_name)) <> lower(btrim(profile_parent))) AS conflicting_parent_names,
    count(*) FILTER (WHERE nullif(btrim(parent_name),'') IS NULL AND nullif(btrim(profile_parent),'') IS NOT NULL) AS parent_only_on_profile,
    count(*) FILTER (WHERE enrichment_checked_at IS NULL) AS never_checked,
    count(*) FILTER (WHERE enrichment_checked_at < now() - interval '90 days') AS stale_90_days,
    count(*) FILTER (WHERE revenue_amount IS NOT NULL OR revenue_low IS NOT NULL OR revenue_high IS NOT NULL) AS with_revenue
  FROM active
), integrity AS (
  SELECT
    (SELECT count(*) FROM public.company_sales_account_members) AS membership_mappings,
    (SELECT count(*) FROM public.company_private_profiles p LEFT JOIN public.company_sales_account_members m USING(company_id) WHERE m.company_id IS NULL) AS unmapped_profiles,
    (SELECT count(*) FROM active a WHERE NOT EXISTS (SELECT 1 FROM public.company_sales_account_members m WHERE m.sales_account_id=a.sales_account_id AND m.company_id=a.primary_company_id AND m.is_primary)) AS invalid_primary_mapping,
    (SELECT count(*) FROM public.company_sales_account_members m JOIN public.company_sales_accounts a USING(sales_account_id) WHERE a.record_status<>'active') AS members_on_merged_accounts,
    (SELECT count(*) FROM (SELECT sales_account_id FROM public.company_private_contacts WHERE active AND primary_contact GROUP BY sales_account_id HAVING count(*)>1) d) AS duplicate_primary_contacts,
    (SELECT count(*) FROM public.company_private_contacts c WHERE c.active AND NOT EXISTS(SELECT 1 FROM active a WHERE a.sales_account_id=c.sales_account_id)) AS contacts_without_active_account
), contacts AS (
  SELECT count(*) AS total_contacts,
    count(*) FILTER (WHERE active) AS active_contacts,
    count(*) FILTER (WHERE active AND primary_contact) AS primary_contacts,
    count(*) FILTER (WHERE active AND contact_role IN ('decision-maker','executive','champion')) AS buying_contacts,
    count(DISTINCT sales_account_id) FILTER (WHERE active) AS accounts_with_contacts,
    count(*) FILTER (WHERE active AND nullif(btrim(source_url),'') IS NULL) AS active_contacts_without_source
  FROM public.company_private_contacts
)
SELECT jsonb_pretty(jsonb_build_object(
  'schema','TOWERSIGNAL_COMPANY_AUDIT_V1','checked_at',now(),'read_only',current_setting('transaction_read_only'),
  'coverage',(SELECT to_jsonb(c) FROM coverage c),'integrity',(SELECT to_jsonb(i) FROM integrity i),
  'contacts',(SELECT to_jsonb(c) FROM contacts c),
  'rollup_statuses',(SELECT coalesce(jsonb_object_agg(status,n),'{}'::jsonb) FROM (SELECT status,count(*) n FROM public.company_rollup_suggestions GROUP BY status) s),
  'research_statuses',(SELECT coalesce(jsonb_object_agg(status,n),'{}'::jsonb) FROM (SELECT status,count(*) n FROM public.company_private_research_queue GROUP BY status) s)
));
ROLLBACK;
