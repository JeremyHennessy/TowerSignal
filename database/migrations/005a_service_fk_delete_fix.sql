BEGIN;

ALTER TABLE public.service_sites DROP CONSTRAINT IF EXISTS service_sites_portfolio_client_fk;
ALTER TABLE public.service_sites
  ADD CONSTRAINT service_sites_portfolio_client_fk
  FOREIGN KEY (portfolio_id, client_id)
  REFERENCES public.service_portfolios(portfolio_id, client_id)
  ON DELETE NO ACTION;

ALTER TABLE public.service_visits DROP CONSTRAINT IF EXISTS service_visits_agreement_site_fk;
ALTER TABLE public.service_visits
  ADD CONSTRAINT service_visits_agreement_site_fk
  FOREIGN KEY (agreement_id, service_site_id)
  REFERENCES public.service_agreements(agreement_id, service_site_id)
  ON DELETE NO ACTION;

ALTER TABLE public.service_measurements DROP CONSTRAINT IF EXISTS service_measurements_asset_site_fk;
ALTER TABLE public.service_measurements
  ADD CONSTRAINT service_measurements_asset_site_fk
  FOREIGN KEY (asset_id, service_site_id)
  REFERENCES public.service_assets(asset_id, service_site_id)
  ON DELETE NO ACTION;

ALTER TABLE public.service_actions DROP CONSTRAINT IF EXISTS service_actions_visit_site_fk;
ALTER TABLE public.service_actions
  ADD CONSTRAINT service_actions_visit_site_fk
  FOREIGN KEY (visit_id, service_site_id)
  REFERENCES public.service_visits(visit_id, service_site_id)
  ON DELETE NO ACTION;

ALTER TABLE public.service_actions DROP CONSTRAINT IF EXISTS service_actions_asset_site_fk;
ALTER TABLE public.service_actions
  ADD CONSTRAINT service_actions_asset_site_fk
  FOREIGN KEY (asset_id, service_site_id)
  REFERENCES public.service_assets(asset_id, service_site_id)
  ON DELETE NO ACTION;

ALTER TABLE public.service_documents DROP CONSTRAINT IF EXISTS service_documents_visit_site_fk;
ALTER TABLE public.service_documents
  ADD CONSTRAINT service_documents_visit_site_fk
  FOREIGN KEY (visit_id, service_site_id)
  REFERENCES public.service_visits(visit_id, service_site_id)
  ON DELETE NO ACTION;

ALTER TABLE public.service_documents DROP CONSTRAINT IF EXISTS service_documents_asset_site_fk;
ALTER TABLE public.service_documents
  ADD CONSTRAINT service_documents_asset_site_fk
  FOREIGN KEY (asset_id, service_site_id)
  REFERENCES public.service_assets(asset_id, service_site_id)
  ON DELETE NO ACTION;

COMMIT;
