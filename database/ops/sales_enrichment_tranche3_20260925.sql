BEGIN;

DO $$
DECLARE
  v_accounts integer;
  v_contacts integer;
  v_primary integer;
BEGIN
  SELECT count(*) INTO v_accounts
  FROM public.company_sales_accounts
  WHERE record_status='active'
    AND sales_account_id IN (
      'sales-account-4cb3500432e523a83e91',
      'sales-account-7dcd01199284dc727abd',
      'sales-account-5dbbe58abd75da64cb84',
      'sales-account-9ee6fe90f7e2f96b24b2',
      'sales-account-64654024bc1a016fcfb6'
    );

  SELECT count(*) INTO v_contacts FROM public.company_private_contacts;
  SELECT count(*) INTO v_primary
  FROM public.company_private_contacts
  WHERE active AND primary_contact;

  IF v_accounts<>5 OR v_contacts<>43 OR v_primary<>16 THEN
    RAISE EXCEPTION 'Tranche 3 precheck failed accounts=% contacts=% primary=%',v_accounts,v_contacts,v_primary;
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.company_private_contacts
    WHERE sales_account_id IN (
      'sales-account-4cb3500432e523a83e91',
      'sales-account-7dcd01199284dc727abd',
      'sales-account-5dbbe58abd75da64cb84'
    )
  ) THEN
    RAISE EXCEPTION 'Expected Culligan, New York Environmental and Cascade to have no private contacts before tranche 3';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.company_private_contacts
    WHERE contact_id='atlas-environmental-general'
      AND sales_account_id='sales-account-9ee6fe90f7e2f96b24b2'
      AND active AND NOT primary_contact
      AND email='info@atlasenvironmentallab.com'
  ) THEN
    RAISE EXCEPTION 'Atlas existing general contact guard failed';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.company_private_contacts
    WHERE contact_id='chemical-specifics-alberto-flores'
      AND sales_account_id='sales-account-64654024bc1a016fcfb6'
      AND active AND primary_contact
  ) THEN
    RAISE EXCEPTION 'Chemical Specifics existing primary contact guard failed';
  END IF;
END $$;

UPDATE public.company_private_profiles
SET legal_name='Culligan of New York',
    website='https://www.culliganofnewyork.com/',
    website_source_name='Fred Smith Plumbing & Heating current Culligan resource',
    website_source_url='https://fredsmithplumbing.com/press-news-view/',
    identity_source_name='New York corporate filing history for The Fred Smith Company, Inc.',
    identity_source_url='https://www.bizprofile.net/ny/new-york/the-fred-smith-company',
    headquarters_address='1674 First Avenue',
    headquarters_city='New York',
    headquarters_region='NY',
    headquarters_postal_code='10128',
    headquarters_country='US',
    headquarters_source_name='Culligan of New York current About page',
    headquarters_source_url='https://words.pair.com/about-us',
    parent_company_name='The Fred Smith Company, Inc.',
    parent_source_name='New York corporate filing history: active assumed name Culligan Water Conditioning of New York City',
    parent_source_url='https://www.bizprofile.net/ny/new-york/the-fred-smith-company',
    company_type='Water treatment, filtration and purification services',
    enrichment_checked_at=now(),
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche3-20260925'
WHERE company_id='known-firm-8bce1b52bfb4d2b17c37'
  AND website IS NULL
  AND headquarters_address IS NULL
  AND parent_company_name IS NULL;

UPDATE public.company_sales_accounts
SET parent_name='The Fred Smith Company, Inc.',
    parent_source_url='https://www.bizprofile.net/ny/new-york/the-fred-smith-company',
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche3-20260925'
WHERE sales_account_id='sales-account-4cb3500432e523a83e91'
  AND parent_name IS NULL;

UPDATE public.company_private_profiles
SET legal_name='New York Environmental and Analytical Laboratories, Inc.',
    website='https://www.nyenvironmental.com/',
    website_source_name='New York Environmental official website',
    website_source_url='https://www.nyenvironmental.com/',
    identity_source_name='New York Environmental official About page',
    identity_source_url='https://www.nyenvironmental.com/about',
    headquarters_address='88 Harbor Road',
    headquarters_city='Port Washington',
    headquarters_region='NY',
    headquarters_postal_code='11050',
    headquarters_country='US',
    headquarters_source_name='New York Environmental official Contact page',
    headquarters_source_url='https://www.nyenvironmental.com/contact',
    company_type='Environmental consulting and accredited analytical laboratory',
    enrichment_checked_at=now(),
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche3-20260925'
WHERE company_id='known-firm-2a66a41bda912cb030b6'
  AND website IS NULL
  AND headquarters_address IS NULL
  AND legal_name IS NULL;

UPDATE public.company_private_profiles
SET parent_company_name='Ecolab Inc.',
    parent_source_name='Ecolab acquisition announcement',
    parent_source_url='https://investor.ecolab.com/news/news-details/2018/Ecolab-Acquires-Cascade-Water-Services/default.aspx',
    revenue_amount=35000000,
    revenue_currency='USD',
    revenue_year=2017,
    revenue_type='reported',
    revenue_source_name='Ecolab acquisition announcement',
    revenue_source_url='https://investor.ecolab.com/news/news-details/2018/Ecolab-Acquires-Cascade-Water-Services/default.aspx',
    revenue_confidence='confirmed',
    internal_summary=CASE
      WHEN internal_summary IS NULL OR internal_summary='' THEN
        'Ecolab acquired Cascade Water Services in January 2018; Ecolab reported approximately $35 million of Cascade sales in 2017. Later corporate records show Cascade merged into Nalco Company LLC.'
      ELSE internal_summary
    END,
    enrichment_checked_at=now(),
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche3-20260925'
WHERE company_id='observed-company-40a2c59b810a30c84370'
  AND parent_company_name IS NULL
  AND revenue_amount IS NULL;

UPDATE public.company_sales_accounts
SET parent_name='Ecolab Inc.',
    parent_source_url='https://investor.ecolab.com/news/news-details/2018/Ecolab-Acquires-Cascade-Water-Services/default.aspx',
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche3-20260925'
WHERE sales_account_id='sales-account-5dbbe58abd75da64cb84'
  AND parent_name IS NULL;

UPDATE public.company_private_profiles
SET enrichment_checked_at=now(),
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche3-20260925'
WHERE company_id IN (
  'known-firm-d83ead023885a2b589ff',
  'known-firm-39c36da2e2b4ffb729be'
);

INSERT INTO public.company_private_contacts (
  contact_id,company_id,sales_account_id,name,title,email,phone,linkedin_url,notes,
  contact_role,primary_contact,source_name,source_url,verified_at,active,
  last_change_source,last_change_batch_id,created_at,updated_at
) VALUES
(
  'culligan-ny-preston-kraus',
  'known-firm-8bce1b52bfb4d2b17c37',
  'sales-account-4cb3500432e523a83e91',
  'Preston Kraus','President, Culligan of New York',NULL,'212-472-9700',NULL,
  'Current professional biography states he is President of Culligan of New York and oversees operations across New York City, Long Island and surrounding areas. Main Culligan New York phone is from the current local Culligan page.',
  'executive',true,'Preston Kraus professional biography','https://prestonkraus.com/about-me/',
  now(),true,'import','sales-enrichment-tranche3-20260925',now(),now()
),
(
  'ny-environmental-consulting',
  'known-firm-2a66a41bda912cb030b6',
  'sales-account-7dcd01199284dc727abd',
  'New York Environmental Consulting','Consulting Services','consulting@nyenvironmental.com','516-944-9500',NULL,
  'Official consulting-services contact route.',
  'other',true,'New York Environmental official Contact page','https://www.nyenvironmental.com/contact',
  now(),true,'import','sales-enrichment-tranche3-20260925',now(),now()
),
(
  'ny-environmental-laboratory',
  'known-firm-2a66a41bda912cb030b6',
  'sales-account-7dcd01199284dc727abd',
  'New York Environmental Analytical Services','Analytical Laboratory','laboratory@nyenvironmental.com','516-944-9504',NULL,
  'Official analytical-services contact route for the accredited laboratory.',
  'technical',false,'New York Environmental official Contact page','https://www.nyenvironmental.com/contact',
  now(),true,'import','sales-enrichment-tranche3-20260925',now(),now()
),
(
  'chemical-specifics-benny-castro',
  'known-firm-39c36da2e2b4ffb729be',
  'sales-account-64654024bc1a016fcfb6',
  'Benny Castro','V.P. Operations',NULL,'718-361-6666',NULL,
  'Current Blue Book company profile lists Benny Castro as V.P. Operations. No individual email was published and none is inferred.',
  'decision-maker',false,'The Blue Book ProView current company profile','https://ww.thebluebook.com/iProView/237655/chemical-specifics-inc/subcontractors/locations-contacts/',
  now(),true,'import','sales-enrichment-tranche3-20260925',now(),now()
)
ON CONFLICT (contact_id) DO NOTHING;

UPDATE public.company_private_contacts
SET primary_contact=true,
    verified_at=now(),
    source_name='Atlas Environmental Lab official Contact Us page',
    source_url='https://www.atlasenvironmentallab.com/contact-us/',
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche3-20260925'
WHERE contact_id='atlas-environmental-general'
  AND sales_account_id='sales-account-9ee6fe90f7e2f96b24b2'
  AND active
  AND NOT primary_contact;

DO $$
DECLARE
  v_contacts integer;
  v_batch_contacts integer;
  v_primary integer;
  v_primary_conflicts integer;
  v_buying integer;
  v_culligan integer;
  v_nye integer;
  v_cascade integer;
BEGIN
  SELECT count(*) INTO v_contacts FROM public.company_private_contacts;
  SELECT count(*) INTO v_batch_contacts
  FROM public.company_private_contacts
  WHERE last_change_batch_id='sales-enrichment-tranche3-20260925';
  SELECT count(*) INTO v_primary
  FROM public.company_private_contacts
  WHERE active AND primary_contact;
  SELECT count(*) INTO v_buying
  FROM public.company_private_contacts
  WHERE active AND contact_role IN ('decision-maker','executive','champion');

  SELECT count(*) INTO v_primary_conflicts
  FROM (
    SELECT sales_account_id
    FROM public.company_private_contacts
    WHERE active AND primary_contact AND sales_account_id IS NOT NULL
    GROUP BY sales_account_id
    HAVING count(*)>1
  ) x;

  SELECT count(*) INTO v_culligan
  FROM public.company_private_profiles
  WHERE company_id='known-firm-8bce1b52bfb4d2b17c37'
    AND website='https://www.culliganofnewyork.com/'
    AND headquarters_address='1674 First Avenue'
    AND parent_company_name='The Fred Smith Company, Inc.';

  SELECT count(*) INTO v_nye
  FROM public.company_private_profiles
  WHERE company_id='known-firm-2a66a41bda912cb030b6'
    AND website='https://www.nyenvironmental.com/'
    AND headquarters_address='88 Harbor Road';

  SELECT count(*) INTO v_cascade
  FROM public.company_private_profiles
  WHERE company_id='observed-company-40a2c59b810a30c84370'
    AND parent_company_name='Ecolab Inc.'
    AND revenue_amount=35000000
    AND revenue_year=2017;

  IF v_contacts<>47 OR v_batch_contacts<>5 OR v_primary<>19 OR v_primary_conflicts<>0
     OR v_buying<>17 OR v_culligan<>1 OR v_nye<>1 OR v_cascade<>1 THEN
    RAISE EXCEPTION 'Tranche 3 acceptance failed contacts=% batch=% primary=% conflicts=% buying=% culligan=% nye=% cascade=%',
      v_contacts,v_batch_contacts,v_primary,v_primary_conflicts,v_buying,v_culligan,v_nye,v_cascade;
  END IF;
END $$;

COMMIT;

SELECT 'SALES_ENRICHMENT_TRANCHE3=PASS' AS result,
       (SELECT count(*) FROM public.company_private_contacts) AS total_contacts,
       (SELECT count(*) FROM public.company_private_contacts WHERE active AND primary_contact) AS primary_contacts,
       (SELECT count(*) FROM public.company_private_contacts WHERE active AND contact_role IN ('decision-maker','executive','champion')) AS buying_contacts;
