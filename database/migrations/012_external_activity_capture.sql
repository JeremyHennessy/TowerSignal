BEGIN;

ALTER TABLE public.company_private_activities
  ADD COLUMN IF NOT EXISTS external_source text,
  ADD COLUMN IF NOT EXISTS external_event_id text,
  ADD COLUMN IF NOT EXISTS external_url text,
  ADD COLUMN IF NOT EXISTS external_direction text,
  ADD COLUMN IF NOT EXISTS participant_emails jsonb DEFAULT '[]'::jsonb NOT NULL,
  ADD COLUMN IF NOT EXISTS external_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
  ADD COLUMN IF NOT EXISTS external_captured_at timestamptz;

ALTER TABLE public.company_private_activities
  DROP CONSTRAINT IF EXISTS company_private_activities_external_source_check;
ALTER TABLE public.company_private_activities
  ADD CONSTRAINT company_private_activities_external_source_check CHECK (
    external_source IS NULL OR external_source IN (
      'eml','ics','gmail','google-calendar','microsoft-mail','microsoft-calendar'
    )
  );

ALTER TABLE public.company_private_activities
  DROP CONSTRAINT IF EXISTS company_private_activities_external_direction_check;
ALTER TABLE public.company_private_activities
  ADD CONSTRAINT company_private_activities_external_direction_check CHECK (
    external_direction IS NULL OR external_direction IN ('inbound','outbound','internal','unknown')
  );

ALTER TABLE public.company_private_activities
  DROP CONSTRAINT IF EXISTS company_private_activities_external_identity_check;
ALTER TABLE public.company_private_activities
  ADD CONSTRAINT company_private_activities_external_identity_check CHECK (
    (external_source IS NULL AND external_event_id IS NULL)
    OR
    (external_source IS NOT NULL AND external_event_id IS NOT NULL)
  );

CREATE UNIQUE INDEX IF NOT EXISTS company_private_activities_external_event_unique_idx
  ON public.company_private_activities(external_source,external_event_id)
  WHERE external_source IS NOT NULL AND external_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS company_private_activities_sales_external_date_idx
  ON public.company_private_activities(sales_account_id,external_source,occurred_at DESC)
  WHERE external_source IS NOT NULL;

COMMIT;
