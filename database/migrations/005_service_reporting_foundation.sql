BEGIN;

CREATE TABLE IF NOT EXISTS public.service_clients (
  client_id text PRIMARY KEY,
  name text NOT NULL,
  linked_company_id text REFERENCES public.company_private_profiles(company_id) ON DELETE SET NULL,
  billing_name text,
  status text DEFAULT 'active' NOT NULL,
  account_owner text,
  notes text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  CONSTRAINT service_clients_status_check CHECK (status IN ('active','inactive','prospect'))
);

CREATE TABLE IF NOT EXISTS public.service_portfolios (
  portfolio_id text PRIMARY KEY,
  client_id text NOT NULL REFERENCES public.service_clients(client_id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  status text DEFAULT 'active' NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  CONSTRAINT service_portfolios_status_check CHECK (status IN ('active','inactive')),
  CONSTRAINT service_portfolios_id_client_unique UNIQUE (portfolio_id, client_id)
);

CREATE TABLE IF NOT EXISTS public.service_sites (
  service_site_id text PRIMARY KEY,
  system_id text NOT NULL UNIQUE,
  client_id text REFERENCES public.service_clients(client_id) ON DELETE SET NULL,
  portfolio_id text REFERENCES public.service_portfolios(portfolio_id) ON DELETE SET NULL,
  display_name text,
  address text,
  status text DEFAULT 'active' NOT NULL,
  access_notes text,
  service_notes text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  CONSTRAINT service_sites_status_check CHECK (status IN ('active','inactive','prospect')),
  CONSTRAINT service_sites_portfolio_client_fk
    FOREIGN KEY (portfolio_id, client_id)
    REFERENCES public.service_portfolios(portfolio_id, client_id)
    ON DELETE NO ACTION
);

CREATE TABLE IF NOT EXISTS public.service_assets (
  asset_id text PRIMARY KEY,
  service_site_id text NOT NULL REFERENCES public.service_sites(service_site_id) ON DELETE CASCADE,
  asset_type text NOT NULL,
  asset_label text NOT NULL,
  manufacturer text,
  model text,
  serial_number text,
  public_equipment_id text,
  location text,
  active boolean DEFAULT true NOT NULL,
  notes text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  CONSTRAINT service_assets_type_check CHECK (asset_type IN (
    'cooling_tower','controller','pump','chemical_feed','heat_exchanger',
    'domestic_water_tank','sensor','other'
  )),
  CONSTRAINT service_assets_id_site_unique UNIQUE (asset_id, service_site_id)
);

CREATE TABLE IF NOT EXISTS public.service_agreements (
  agreement_id text PRIMARY KEY,
  service_site_id text NOT NULL REFERENCES public.service_sites(service_site_id) ON DELETE CASCADE,
  provider_company_id text REFERENCES public.company_private_profiles(company_id) ON DELETE SET NULL,
  agreement_name text NOT NULL,
  status text DEFAULT 'draft' NOT NULL,
  start_date date,
  end_date date,
  service_interval_days integer,
  scope jsonb DEFAULT '{}'::jsonb NOT NULL,
  notes text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  CONSTRAINT service_agreements_status_check CHECK (status IN ('draft','active','expired','cancelled')),
  CONSTRAINT service_agreements_interval_check CHECK (service_interval_days IS NULL OR service_interval_days > 0),
  CONSTRAINT service_agreements_date_check CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date),
  CONSTRAINT service_agreements_id_site_unique UNIQUE (agreement_id, service_site_id)
);

CREATE TABLE IF NOT EXISTS public.service_visits (
  visit_id text PRIMARY KEY,
  service_site_id text NOT NULL REFERENCES public.service_sites(service_site_id) ON DELETE CASCADE,
  agreement_id text REFERENCES public.service_agreements(agreement_id) ON DELETE SET NULL,
  status text DEFAULT 'scheduled' NOT NULL,
  visit_type text DEFAULT 'routine' NOT NULL,
  scheduled_for timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  technician_name text,
  summary text,
  next_visit_date date,
  report_status text DEFAULT 'draft' NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  CONSTRAINT service_visits_status_check CHECK (status IN ('scheduled','in-progress','completed','cancelled')),
  CONSTRAINT service_visits_report_status_check CHECK (report_status IN ('draft','ready','finalized')),
  CONSTRAINT service_visits_id_site_unique UNIQUE (visit_id, service_site_id),
  CONSTRAINT service_visits_agreement_site_fk
    FOREIGN KEY (agreement_id, service_site_id)
    REFERENCES public.service_agreements(agreement_id, service_site_id)
    ON DELETE NO ACTION
);

CREATE TABLE IF NOT EXISTS public.service_measurements (
  measurement_id text PRIMARY KEY,
  service_site_id text NOT NULL REFERENCES public.service_sites(service_site_id) ON DELETE CASCADE,
  visit_id text NOT NULL REFERENCES public.service_visits(visit_id) ON DELETE CASCADE,
  asset_id text REFERENCES public.service_assets(asset_id) ON DELETE SET NULL,
  parameter text NOT NULL,
  value_numeric numeric,
  value_text text,
  unit text,
  target_min numeric,
  target_max numeric,
  result_status text DEFAULT 'normal' NOT NULL,
  notes text,
  measured_at timestamptz DEFAULT now() NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  CONSTRAINT service_measurements_result_check CHECK (result_status IN ('normal','attention','action')),
  CONSTRAINT service_measurements_value_check CHECK (value_numeric IS NOT NULL OR nullif(trim(value_text),'') IS NOT NULL),
  CONSTRAINT service_measurements_range_check CHECK (target_min IS NULL OR target_max IS NULL OR target_min <= target_max),
  CONSTRAINT service_measurements_visit_site_fk
    FOREIGN KEY (visit_id, service_site_id)
    REFERENCES public.service_visits(visit_id, service_site_id)
    ON DELETE CASCADE,
  CONSTRAINT service_measurements_asset_site_fk
    FOREIGN KEY (asset_id, service_site_id)
    REFERENCES public.service_assets(asset_id, service_site_id)
    ON DELETE NO ACTION
);

CREATE TABLE IF NOT EXISTS public.service_actions (
  action_id text PRIMARY KEY,
  service_site_id text NOT NULL REFERENCES public.service_sites(service_site_id) ON DELETE CASCADE,
  visit_id text REFERENCES public.service_visits(visit_id) ON DELETE SET NULL,
  asset_id text REFERENCES public.service_assets(asset_id) ON DELETE SET NULL,
  title text NOT NULL,
  severity text DEFAULT 'medium' NOT NULL,
  status text DEFAULT 'open' NOT NULL,
  due_date date,
  completed_at timestamptz,
  owner text,
  details text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  CONSTRAINT service_actions_severity_check CHECK (severity IN ('low','medium','high','critical')),
  CONSTRAINT service_actions_status_check CHECK (status IN ('open','in-progress','completed','dismissed')),
  CONSTRAINT service_actions_visit_site_fk
    FOREIGN KEY (visit_id, service_site_id)
    REFERENCES public.service_visits(visit_id, service_site_id)
    ON DELETE NO ACTION,
  CONSTRAINT service_actions_asset_site_fk
    FOREIGN KEY (asset_id, service_site_id)
    REFERENCES public.service_assets(asset_id, service_site_id)
    ON DELETE NO ACTION
);

CREATE TABLE IF NOT EXISTS public.service_reports (
  report_id text PRIMARY KEY,
  service_site_id text NOT NULL REFERENCES public.service_sites(service_site_id) ON DELETE CASCADE,
  visit_id text NOT NULL UNIQUE REFERENCES public.service_visits(visit_id) ON DELETE CASCADE,
  report_number text,
  title text NOT NULL,
  status text DEFAULT 'draft' NOT NULL,
  executive_summary text,
  recommendations text,
  generated_at timestamptz,
  finalized_at timestamptz,
  client_visible boolean DEFAULT false NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  CONSTRAINT service_reports_status_check CHECK (status IN ('draft','ready','finalized')),
  CONSTRAINT service_reports_visit_site_fk
    FOREIGN KEY (visit_id, service_site_id)
    REFERENCES public.service_visits(visit_id, service_site_id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.service_documents (
  document_id text PRIMARY KEY,
  service_site_id text NOT NULL REFERENCES public.service_sites(service_site_id) ON DELETE CASCADE,
  visit_id text REFERENCES public.service_visits(visit_id) ON DELETE SET NULL,
  report_id text REFERENCES public.service_reports(report_id) ON DELETE SET NULL,
  asset_id text REFERENCES public.service_assets(asset_id) ON DELETE SET NULL,
  document_type text DEFAULT 'other' NOT NULL,
  file_name text NOT NULL,
  mime_type text,
  storage_url text,
  sha256 text,
  captured_at timestamptz,
  notes text,
  extraction_status text DEFAULT 'not-requested' NOT NULL,
  extracted_text text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  CONSTRAINT service_documents_type_check CHECK (document_type IN (
    'visit-report','photo','lab-result','water-management-plan','contract',
    'schematic','sds','invoice','other'
  )),
  CONSTRAINT service_documents_extraction_check CHECK (extraction_status IN ('not-requested','pending','complete','failed')),
  CONSTRAINT service_documents_visit_site_fk
    FOREIGN KEY (visit_id, service_site_id)
    REFERENCES public.service_visits(visit_id, service_site_id)
    ON DELETE NO ACTION,
  CONSTRAINT service_documents_asset_site_fk
    FOREIGN KEY (asset_id, service_site_id)
    REFERENCES public.service_assets(asset_id, service_site_id)
    ON DELETE NO ACTION
);

CREATE TABLE IF NOT EXISTS public.service_change_log (
  change_id bigserial PRIMARY KEY,
  service_site_id text,
  entity_type text NOT NULL,
  entity_id text NOT NULL,
  operation text NOT NULL,
  snapshot jsonb NOT NULL,
  changed_at timestamptz DEFAULT now() NOT NULL,
  changed_by text
);

CREATE INDEX IF NOT EXISTS service_portfolios_client_idx ON public.service_portfolios(client_id);
CREATE INDEX IF NOT EXISTS service_sites_client_idx ON public.service_sites(client_id);
CREATE INDEX IF NOT EXISTS service_sites_portfolio_idx ON public.service_sites(portfolio_id);
CREATE INDEX IF NOT EXISTS service_assets_site_idx ON public.service_assets(service_site_id, active);
CREATE INDEX IF NOT EXISTS service_agreements_site_idx ON public.service_agreements(service_site_id, status);
CREATE INDEX IF NOT EXISTS service_visits_site_schedule_idx ON public.service_visits(service_site_id, scheduled_for DESC);
CREATE INDEX IF NOT EXISTS service_measurements_visit_idx ON public.service_measurements(visit_id, measured_at);
CREATE INDEX IF NOT EXISTS service_actions_site_status_idx ON public.service_actions(service_site_id, status, due_date);
CREATE INDEX IF NOT EXISTS service_documents_site_idx ON public.service_documents(service_site_id, created_at DESC);
CREATE INDEX IF NOT EXISTS service_change_site_time_idx ON public.service_change_log(service_site_id, changed_at DESC);

ALTER TABLE public.service_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_agreements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_visits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_measurements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_change_log ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
  table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'service_clients','service_portfolios','service_sites','service_assets',
    'service_agreements','service_visits','service_measurements','service_actions',
    'service_reports','service_documents'
  ]
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', table_name || '_admin_only', table_name);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I TO authenticated USING (public.towersignal_is_admin()) WITH CHECK (public.towersignal_is_admin())',
      table_name || '_admin_only', table_name
    );
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO authenticated', table_name);
  END LOOP;
END $$;

DROP POLICY IF EXISTS service_change_log_admin_read ON public.service_change_log;
CREATE POLICY service_change_log_admin_read ON public.service_change_log
  FOR SELECT TO authenticated USING (public.towersignal_is_admin());
GRANT SELECT ON public.service_change_log TO authenticated;

CREATE OR REPLACE FUNCTION public.towersignal_audit_service_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
  row_data jsonb;
  site_value text;
  entity_value text;
BEGIN
  row_data := CASE WHEN TG_OP = 'DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
  site_value := COALESCE(row_data->>'service_site_id', CASE WHEN TG_TABLE_NAME='service_sites' THEN row_data->>'service_site_id' ELSE NULL END);
  entity_value := COALESCE(row_data->>TG_ARGV[1], '');

  INSERT INTO public.service_change_log (
    service_site_id, entity_type, entity_id, operation, snapshot, changed_by
  ) VALUES (
    site_value, TG_ARGV[0], entity_value, TG_OP, row_data, auth.user_id()
  );

  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.towersignal_audit_service_change() FROM PUBLIC;

DROP TRIGGER IF EXISTS service_clients_audit ON public.service_clients;
CREATE TRIGGER service_clients_audit AFTER INSERT OR UPDATE OR DELETE ON public.service_clients
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_service_change('client','client_id');
DROP TRIGGER IF EXISTS service_portfolios_audit ON public.service_portfolios;
CREATE TRIGGER service_portfolios_audit AFTER INSERT OR UPDATE OR DELETE ON public.service_portfolios
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_service_change('portfolio','portfolio_id');
DROP TRIGGER IF EXISTS service_sites_audit ON public.service_sites;
CREATE TRIGGER service_sites_audit AFTER INSERT OR UPDATE OR DELETE ON public.service_sites
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_service_change('site','service_site_id');
DROP TRIGGER IF EXISTS service_assets_audit ON public.service_assets;
CREATE TRIGGER service_assets_audit AFTER INSERT OR UPDATE OR DELETE ON public.service_assets
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_service_change('asset','asset_id');
DROP TRIGGER IF EXISTS service_agreements_audit ON public.service_agreements;
CREATE TRIGGER service_agreements_audit AFTER INSERT OR UPDATE OR DELETE ON public.service_agreements
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_service_change('agreement','agreement_id');
DROP TRIGGER IF EXISTS service_visits_audit ON public.service_visits;
CREATE TRIGGER service_visits_audit AFTER INSERT OR UPDATE OR DELETE ON public.service_visits
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_service_change('visit','visit_id');
DROP TRIGGER IF EXISTS service_measurements_audit ON public.service_measurements;
CREATE TRIGGER service_measurements_audit AFTER INSERT OR UPDATE OR DELETE ON public.service_measurements
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_service_change('measurement','measurement_id');
DROP TRIGGER IF EXISTS service_actions_audit ON public.service_actions;
CREATE TRIGGER service_actions_audit AFTER INSERT OR UPDATE OR DELETE ON public.service_actions
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_service_change('action','action_id');
DROP TRIGGER IF EXISTS service_reports_audit ON public.service_reports;
CREATE TRIGGER service_reports_audit AFTER INSERT OR UPDATE OR DELETE ON public.service_reports
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_service_change('report','report_id');
DROP TRIGGER IF EXISTS service_documents_audit ON public.service_documents;
CREATE TRIGGER service_documents_audit AFTER INSERT OR UPDATE OR DELETE ON public.service_documents
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_service_change('document','document_id');

COMMIT;
