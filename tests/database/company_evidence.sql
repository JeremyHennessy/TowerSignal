\set ON_ERROR_STOP on
SET test.user_id='admin-test';
INSERT INTO public.company_private_profiles(company_id,canonical_name,parent_company_name) VALUES('fixture-company','Fixture Company','Legacy Parent');
INSERT INTO public.company_sales_accounts(sales_account_id,primary_company_id,display_name,parent_name) VALUES('fixture-account','fixture-company','Fixture Company','Legacy Parent');
INSERT INTO public.company_sales_account_members(sales_account_id,company_id,is_primary) VALUES('fixture-account','fixture-company',true);

SET ROLE authenticated;
INSERT INTO public.company_parent_entities(parent_entity_id,display_name) VALUES('fixture-parent','Reviewed Parent');
INSERT INTO public.company_parent_relationships(relationship_id,sales_account_id,parent_entity_id,relationship_type,evidence_url,evidence_note,observed_on)
VALUES('fixture-link','fixture-account','fixture-parent','parent','https://example.com/ownership','Official ownership statement',current_date);
UPDATE public.company_parent_relationships SET status='confirmed' WHERE relationship_id='fixture-link';
INSERT INTO public.company_enrichment_sources(source_id,sales_account_id,source_url,expected_name,enabled)
VALUES('fixture-source','fixture-account','https://example.com','Fixture Company',true);
DO $$ BEGIN
  IF (SELECT parent_name FROM public.company_sales_accounts WHERE sales_account_id='fixture-account')<>'Legacy Parent' THEN RAISE EXCEPTION 'Existing parent was overwritten'; END IF;
  IF (SELECT count(*) FROM public.company_sales_account_members WHERE sales_account_id='fixture-account')<>1 THEN RAISE EXCEPTION 'Mapping changed'; END IF;
  IF (SELECT approved_by FROM public.company_enrichment_sources WHERE source_id='fixture-source')<>'admin-test' THEN RAISE EXCEPTION 'Approval not recorded'; END IF;
  IF (SELECT reviewed_by FROM public.company_parent_relationships WHERE relationship_id='fixture-link')<>'admin-test' THEN RAISE EXCEPTION 'Review not recorded'; END IF;
  BEGIN
    UPDATE public.company_sales_accounts SET record_status='merged' WHERE sales_account_id='fixture-account';
    RAISE EXCEPTION 'Active evidence was silently stranded by a merge';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM NOT LIKE 'Review pending enrichment%' THEN RAISE; END IF;
  END;
  BEGIN
    INSERT INTO public.company_parent_relationships(sales_account_id,parent_entity_id,relationship_type,evidence_url,evidence_note,observed_on,status)
    VALUES('fixture-account','fixture-parent','parent','https://example.com','Duplicate',current_date,'confirmed');
    RAISE EXCEPTION 'Duplicate confirmed parent allowed';
  EXCEPTION WHEN unique_violation THEN NULL; END;
END $$;
SET test.user_id='reader-test';
DO $$ BEGIN
  BEGIN
    PERFORM public.towersignal_company_admin_snapshot();
    RAISE EXCEPTION 'Non-admin can load private admin snapshot';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
DO $$ BEGIN
  IF EXISTS(SELECT 1 FROM public.company_parent_entities) OR EXISTS(SELECT 1 FROM public.company_enrichment_sources) THEN RAISE EXCEPTION 'Non-admin can read evidence'; END IF;
  BEGIN
    INSERT INTO public.company_parent_entities(display_name) VALUES('Not allowed');
    RAISE EXCEPTION 'Non-admin can insert evidence';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;
SET test.user_id='admin-test';
SET ROLE authenticated;
DO $$ DECLARE snapshot jsonb;
BEGIN
  snapshot:=public.towersignal_company_admin_snapshot();
  IF jsonb_array_length(snapshot->'accounts')<>1 OR jsonb_array_length(snapshot->'members')<>1 OR
    snapshot->'profiles'->0->>'parent_company_name'<>'Legacy Parent' THEN
    RAISE EXCEPTION 'Admin snapshot did not preserve the account/member/profile join';
  END IF;
END $$;
RESET ROLE;
SELECT 'COMPANY_EVIDENCE_DATABASE=PASS';
