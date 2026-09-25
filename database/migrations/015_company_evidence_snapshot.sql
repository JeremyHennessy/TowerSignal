BEGIN;

-- Read related ownership records together after each administrative write.
CREATE OR REPLACE FUNCTION public.towersignal_company_evidence_snapshot()
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY INVOKER
SET search_path=pg_catalog,public AS $$
BEGIN
  IF NOT public.towersignal_is_admin() THEN
    RAISE EXCEPTION 'Administrator access is required to load company evidence' USING ERRCODE='42501';
  END IF;
  RETURN jsonb_build_object(
    'parents',(SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY display_name),'[]'::jsonb) FROM public.company_parent_entities t),
    'relationships',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_parent_relationships t),
    'sources',(SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.company_enrichment_sources t),
    'runs',(SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY started_at DESC),'[]'::jsonb) FROM (SELECT * FROM public.company_enrichment_runs ORDER BY started_at DESC LIMIT 20) t),
    'candidates',(SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY last_observed_at DESC),'[]'::jsonb) FROM (SELECT * FROM public.company_enrichment_candidates WHERE status='pending' ORDER BY last_observed_at DESC LIMIT 100) t)
  );
END $$;
REVOKE ALL ON FUNCTION public.towersignal_company_evidence_snapshot() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.towersignal_company_evidence_snapshot() TO authenticated;
COMMIT;
