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
      'sales-account-0ae5d1d45fa2c7408a2b',
      'sales-account-e570c5e2bd2cf6a56765',
      'sales-account-7ad47acd1e4cb84f0173',
      'sales-account-5080cac75506426a5a2e',
      'sales-account-64654024bc1a016fcfb6',
      'sales-account-6a1295cdab60abf62952'
    );

  SELECT count(*) INTO v_contacts FROM public.company_private_contacts;

  SELECT count(*) INTO v_primary
  FROM public.company_private_contacts
  WHERE active AND primary_contact
    AND sales_account_id IN (
      'sales-account-0ae5d1d45fa2c7408a2b',
      'sales-account-e570c5e2bd2cf6a56765',
      'sales-account-7ad47acd1e4cb84f0173',
      'sales-account-5080cac75506426a5a2e',
      'sales-account-64654024bc1a016fcfb6',
      'sales-account-6a1295cdab60abf62952'
    );

  IF v_accounts<>6 OR v_contacts<>33 OR v_primary<>0 THEN
    RAISE EXCEPTION 'Tranche 2 precheck failed accounts=% contacts=% primary=%',v_accounts,v_contacts,v_primary;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.company_private_contacts
    WHERE contact_id='certified-melville-main'
      AND sales_account_id='sales-account-6a1295cdab60abf62952'
      AND active AND NOT primary_contact
  ) THEN
    RAISE EXCEPTION 'Certified Laboratories existing Melville contact guard failed';
  END IF;
END $$;

UPDATE public.company_private_profiles
SET legal_name='Rochester Midland Corporation',
    website='https://www.rochestermidland.com/',
    website_source_name='Rochester Midland official website',
    website_source_url='https://www.rochestermidland.com/',
    identity_source_name='Rochester Midland official About page',
    identity_source_url='https://www.rochestermidland.com/about-us/',
    headquarters_address='155 Paragon Drive',
    headquarters_city='Rochester',
    headquarters_region='NY',
    headquarters_postal_code='14624',
    headquarters_country='US',
    headquarters_source_name='Rochester Midland official Contact page',
    headquarters_source_url='https://www.rochestermidland.com/contact/',
    parent_company_name='Peak Rock Capital',
    parent_source_name='Rochester Midland official CEO biography',
    parent_source_url='https://www.rochestermidland.com/team/jim-white/',
    company_type='Water treatment chemicals and services',
    revenue_low=150000000,
    revenue_currency='USD',
    revenue_type='range',
    revenue_source_name='Rochester Midland official CEO biography',
    revenue_source_url='https://www.rochestermidland.com/team/jim-white/',
    revenue_confidence='strong',
    enrichment_checked_at=now(),
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche2-20260924'
WHERE company_id='observed-company-a3bc0790172dfd16ed5a'
  AND website IS NULL
  AND legal_name IS NULL
  AND headquarters_address IS NULL;

UPDATE public.company_sales_accounts
SET parent_name='Peak Rock Capital',
    parent_source_url='https://www.rochestermidland.com/team/jim-white/',
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche2-20260924'
WHERE sales_account_id='sales-account-0ae5d1d45fa2c7408a2b'
  AND parent_name IS NULL;

UPDATE public.company_private_profiles
SET legal_name='Chemical Specifics, Inc.',
    website='https://chemicalspecifics.com/',
    website_source_name='Chemical Specifics official website',
    website_source_url='https://chemicalspecifics.com/',
    identity_source_name='Chemical Specifics official website',
    identity_source_url='https://chemicalspecifics.com/',
    headquarters_address='46-09 54th Rd',
    headquarters_city='Maspeth',
    headquarters_region='NY',
    headquarters_postal_code='11378',
    headquarters_country='US',
    headquarters_source_name='Mechanical Contractors Association of New York member profile',
    headquarters_source_url='https://www.maccny.org/member/chemical-specifics-inc',
    company_type='Water treatment, cooling-tower cleaning and HVAC services',
    enrichment_checked_at=now(),
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche2-20260924'
WHERE company_id='known-firm-39c36da2e2b4ffb729be'
  AND website IS NULL
  AND headquarters_address IS NULL;

UPDATE public.company_private_profiles
SET enrichment_checked_at=now(),
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche2-20260924'
WHERE company_id IN (
  'observed-company-d2e3c6ea5d94cd5c541a',
  'observed-company-9c424024fa9e6da2e03b',
  'known-firm-a76ae2375cff31677267',
  'known-firm-fbc0cd4c7f1cd22b516c'
);

INSERT INTO public.company_private_contacts (
  contact_id,company_id,sales_account_id,name,title,email,phone,linkedin_url,notes,
  contact_role,primary_contact,source_name,source_url,verified_at,active,
  last_change_source,last_change_batch_id,created_at,updated_at
) VALUES
(
  'rmc-global-inquiries',
  'observed-company-a3bc0790172dfd16ed5a',
  'sales-account-0ae5d1d45fa2c7408a2b',
  'Rochester Midland Global Inquiries','Sales inquiry route',NULL,'1-585-336-2200',NULL,
  'Official contact route; Rochester Midland contact form can route requests to a sales representative.',
  'other',true,'Rochester Midland official Contact page','https://www.rochestermidland.com/contact/',
  now(),true,'import','sales-enrichment-tranche2-20260924',now(),now()
),
(
  'rmc-jim-white',
  'observed-company-a3bc0790172dfd16ed5a',
  'sales-account-0ae5d1d45fa2c7408a2b',
  'Jim White','Chief Executive Officer',NULL,NULL,NULL,
  'Current CEO named on Rochester Midland official leadership pages.',
  'executive',false,'Rochester Midland official CEO biography','https://www.rochestermidland.com/team/jim-white/',
  now(),true,'import','sales-enrichment-tranche2-20260924',now(),now()
),
(
  'rmc-ali-janbakhsh',
  'observed-company-a3bc0790172dfd16ed5a',
  'sales-account-0ae5d1d45fa2c7408a2b',
  'Ali Janbakhsh','VP, Water Energy',NULL,NULL,NULL,
  'Current water-business leadership named on Rochester Midland official leadership pages.',
  'decision-maker',false,'Rochester Midland official About page','https://www.rochestermidland.com/about-us/',
  now(),true,'import','sales-enrichment-tranche2-20260924',now(),now()
),
(
  'clarity-general-inquiries',
  'observed-company-d2e3c6ea5d94cd5c541a',
  'sales-account-e570c5e2bd2cf6a56765',
  'Clarity Water Technologies Inquiries','Water-treatment sales inquiry route',NULL,'845-589-0580',NULL,
  'Official contact page invites facility water-treatment inquiries and free system surveys.',
  'other',true,'Clarity Water Technologies official Contact page','https://claritywatertech.com/contact-us/',
  now(),true,'import','sales-enrichment-tranche2-20260924',now(),now()
),
(
  'pace-greg-whitman',
  'observed-company-9c424024fa9e6da2e03b',
  'sales-account-7ad47acd1e4cb84f0173',
  'Greg Whitman','President, Pace Analytical Services Division',NULL,NULL,NULL,
  'Current division president named on Pace official leadership page; older direct contact details were intentionally not imported.',
  'executive',true,'Pace Analytical official Leadership Team','https://www.pacelabs.com/company/leadership-team/',
  now(),true,'import','sales-enrichment-tranche2-20260924',now(),now()
),
(
  'pace-legionella-response',
  'observed-company-9c424024fa9e6da2e03b',
  'sales-account-7ad47acd1e4cb84f0173',
  'Pace Legionella Response Team','Legionella testing and response',NULL,'412-281-5335',NULL,
  'Current official Pace Building Sciences Legionella response route.',
  'technical',false,'Pace Building Sciences official page','https://www.pacelabs.com/analytical-environmental/building-sciences/',
  now(),true,'import','sales-enrichment-tranche2-20260924',now(),now()
),
(
  'tower-water-noah-baskin',
  'known-firm-a76ae2375cff31677267',
  'sales-account-5080cac75506426a5a2e',
  'Noah Baskin','CEO and co-owner',NULL,NULL,NULL,
  'Current Tower Water leadership stated on the company official 2026 regional water-treatment article.',
  'executive',true,'Tower Water official website','https://towerwater.com/water-treatment-companies-by-region/',
  now(),true,'import','sales-enrichment-tranche2-20260924',now(),now()
),
(
  'tower-water-nyc-consultation',
  'known-firm-a76ae2375cff31677267',
  'sales-account-5080cac75506426a5a2e',
  'Tower Water NYC Consultation','NYC sales and consultation route',NULL,'212-518-6475',NULL,
  'Current NYC consultation route on Tower Water official website.',
  'other',false,'Tower Water official NYC services page','https://towerwater.com/water-treatment-services/new-york-city/',
  now(),true,'import','sales-enrichment-tranche2-20260924',now(),now()
),
(
  'chemical-specifics-alberto-flores',
  'known-firm-39c36da2e2b4ffb729be',
  'sales-account-64654024bc1a016fcfb6',
  'Alberto Flores','Member contact',NULL,'718-361-6666',NULL,
  'Current Mechanical Contractors Association of New York member profile contact for Chemical Specifics; role is not inferred beyond listed member contact.',
  'other',true,'Mechanical Contractors Association of New York member profile','https://www.maccny.org/member/chemical-specifics-inc',
  now(),true,'import','sales-enrichment-tranche2-20260924',now(),now()
),
(
  'certified-jonathan-rosas',
  'known-firm-fbc0cd4c7f1cd22b516c',
  'sales-account-6a1295cdab60abf62952',
  'Jonathan Rosas','Named representative on current NYSDOH ELAP certificate',NULL,NULL,NULL,
  'Named on Certified Laboratories LLC NYSDOH environmental laboratory certificate issued April 1, 2026 and expiring April 1, 2027.',
  'technical',false,'NYSDOH Certificate of Approval for Laboratory Service','https://certified-laboratories.com/wp-content/uploads/Certified-Laboratories-NY-NELAC-April-1-2026-Expires-April-1-2027.pdf',
  now(),true,'import','sales-enrichment-tranche2-20260924',now(),now()
)
ON CONFLICT (contact_id) DO NOTHING;

UPDATE public.company_private_contacts
SET primary_contact=true,
    verified_at=now(),
    source_name='Certified Laboratories official Contact page',
    source_url='https://certified-laboratories.com/contact-us/',
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='sales-enrichment-tranche2-20260924'
WHERE contact_id='certified-melville-main'
  AND sales_account_id='sales-account-6a1295cdab60abf62952'
  AND active;

DO $$
DECLARE
  v_contacts integer;
  v_batch_contacts integer;
  v_primary_conflicts integer;
  v_target_primary integer;
  v_rmc_profile integer;
  v_chemical_profile integer;
BEGIN
  SELECT count(*) INTO v_contacts FROM public.company_private_contacts;

  SELECT count(*) INTO v_batch_contacts
  FROM public.company_private_contacts
  WHERE last_change_batch_id='sales-enrichment-tranche2-20260924';

  SELECT count(*) INTO v_primary_conflicts
  FROM (
    SELECT sales_account_id
    FROM public.company_private_contacts
    WHERE active AND primary_contact AND sales_account_id IS NOT NULL
    GROUP BY sales_account_id
    HAVING count(*)>1
  ) x;

  SELECT count(*) INTO v_target_primary
  FROM public.company_private_contacts
  WHERE active AND primary_contact
    AND sales_account_id IN (
      'sales-account-0ae5d1d45fa2c7408a2b',
      'sales-account-e570c5e2bd2cf6a56765',
      'sales-account-7ad47acd1e4cb84f0173',
      'sales-account-5080cac75506426a5a2e',
      'sales-account-64654024bc1a016fcfb6',
      'sales-account-6a1295cdab60abf62952'
    );

  SELECT count(*) INTO v_rmc_profile
  FROM public.company_private_profiles
  WHERE company_id='observed-company-a3bc0790172dfd16ed5a'
    AND website='https://www.rochestermidland.com/'
    AND headquarters_address='155 Paragon Drive'
    AND parent_company_name='Peak Rock Capital'
    AND revenue_low=150000000;

  SELECT count(*) INTO v_chemical_profile
  FROM public.company_private_profiles
  WHERE company_id='known-firm-39c36da2e2b4ffb729be'
    AND website='https://chemicalspecifics.com/'
    AND headquarters_address='46-09 54th Rd';

  IF v_contacts<>43 OR v_batch_contacts<>11 OR v_primary_conflicts<>0
     OR v_target_primary<>6 OR v_rmc_profile<>1 OR v_chemical_profile<>1 THEN
    RAISE EXCEPTION 'Tranche 2 acceptance failed contacts=% batch=% conflicts=% target_primary=% rmc=% chemical=%',
      v_contacts,v_batch_contacts,v_primary_conflicts,v_target_primary,v_rmc_profile,v_chemical_profile;
  END IF;
END $$;

COMMIT;

SELECT 'SALES_ENRICHMENT_TRANCHE2=PASS' AS result,
       (SELECT count(*) FROM public.company_private_contacts) AS total_contacts,
       (SELECT count(*) FROM public.company_private_contacts WHERE last_change_batch_id='sales-enrichment-tranche2-20260924') AS batch_contacts,
       (SELECT count(*) FROM public.company_private_contacts WHERE active AND primary_contact) AS primary_contacts,
       (SELECT count(*) FROM public.company_private_contacts WHERE active AND contact_role IN ('decision-maker','executive','champion')) AS buying_contacts;
