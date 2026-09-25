BEGIN;

-- One admin-checked statement keeps related tables in the same database snapshot.
-- Invoker permissions and each table's RLS continue to apply.
CREATE OR REPLACE FUNCTION public.towersignal_company_admin_snapshot()
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY INVOKER
SET search_path=pg_catalog,public AS $$
BEGIN
  IF NOT public.towersignal_is_admin() THEN
    RAISE EXCEPTION 'Administrator access is required to load company records' USING ERRCODE='42501';
  END IF;
  RETURN jsonb_build_object(
    'profiles',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_private_profiles t),
    'accounts',(SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY display_name),'[]'::jsonb) FROM public.company_sales_accounts t WHERE record_status='active'),
    'members',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_sales_account_members t),
    'contacts',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_private_contacts t),
    'activities',(SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY occurred_at DESC),'[]'::jsonb) FROM public.company_private_activities t),
    'queue',(SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY priority_score DESC),'[]'::jsonb) FROM public.company_private_research_queue t),
    'opportunities',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_private_opportunities t),
    'tasks',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_private_tasks t),
    'demos',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_sales_demos t),
    'proposals',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_sales_proposals t),
    'subscriptions',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_sales_subscriptions t),
    'renewals',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_sales_renewals t)
  );
END $$;
REVOKE ALL ON FUNCTION public.towersignal_company_admin_snapshot() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.towersignal_company_admin_snapshot() TO authenticated;
COMMIT;
