BEGIN;

ALTER TABLE public.company_private_contacts
  ADD COLUMN IF NOT EXISTS contact_role text,
  ADD COLUMN IF NOT EXISTS primary_contact boolean DEFAULT false NOT NULL;

ALTER TABLE public.company_private_contacts
  DROP CONSTRAINT IF EXISTS company_private_contacts_role_check;
ALTER TABLE public.company_private_contacts
  ADD CONSTRAINT company_private_contacts_role_check
  CHECK (contact_role IS NULL OR contact_role IN (
    'decision-maker','champion','technical','procurement','finance','executive','other'
  ));

CREATE UNIQUE INDEX IF NOT EXISTS company_private_contacts_one_primary_idx
  ON public.company_private_contacts(company_id)
  WHERE primary_contact AND active;

CREATE TABLE IF NOT EXISTS public.company_private_opportunities (
  opportunity_id text PRIMARY KEY,
  company_id text NOT NULL REFERENCES public.company_private_profiles(company_id) ON DELETE CASCADE,
  name text NOT NULL,
  stage text DEFAULT 'lead' NOT NULL,
  product_scope jsonb DEFAULT '["TowerSignal"]'::jsonb NOT NULL,
  estimated_arr numeric(18,2),
  one_time_value numeric(18,2),
  probability_percent integer,
  primary_contact_id text REFERENCES public.company_private_contacts(contact_id) ON DELETE SET NULL,
  lead_source text,
  target_close_date date,
  next_step text,
  next_action_date date,
  demo_scheduled_at timestamptz,
  proposal_sent_at timestamptz,
  won_at timestamptz,
  lost_at timestamptz,
  lost_reason text,
  notes text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  last_change_source text DEFAULT 'manual' NOT NULL,
  last_change_batch_id text,
  CONSTRAINT company_private_opportunities_stage_check CHECK (stage IN (
    'lead','qualified','demo-scheduled','demo-complete','proposal','negotiation',
    'closed-won','closed-lost','nurture'
  )),
  CONSTRAINT company_private_opportunities_probability_check CHECK (
    probability_percent IS NULL OR probability_percent BETWEEN 0 AND 100
  ),
  CONSTRAINT company_private_opportunities_value_check CHECK (
    (estimated_arr IS NULL OR estimated_arr >= 0)
    AND (one_time_value IS NULL OR one_time_value >= 0)
  ),
  CONSTRAINT company_private_opportunities_source_check CHECK (
    last_change_source IN ('manual','import','system','database')
  )
);

CREATE INDEX IF NOT EXISTS company_private_opportunities_company_idx
  ON public.company_private_opportunities(company_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS company_private_opportunities_stage_idx
  ON public.company_private_opportunities(stage, target_close_date);
CREATE INDEX IF NOT EXISTS company_private_opportunities_next_action_idx
  ON public.company_private_opportunities(next_action_date);

CREATE TABLE IF NOT EXISTS public.company_private_tasks (
  task_id text PRIMARY KEY,
  company_id text NOT NULL REFERENCES public.company_private_profiles(company_id) ON DELETE CASCADE,
  opportunity_id text REFERENCES public.company_private_opportunities(opportunity_id) ON DELETE SET NULL,
  contact_id text REFERENCES public.company_private_contacts(contact_id) ON DELETE SET NULL,
  title text NOT NULL,
  task_type text DEFAULT 'follow-up' NOT NULL,
  priority text DEFAULT 'medium' NOT NULL,
  status text DEFAULT 'open' NOT NULL,
  due_at timestamptz,
  completed_at timestamptz,
  notes text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  last_change_source text DEFAULT 'manual' NOT NULL,
  last_change_batch_id text,
  CONSTRAINT company_private_tasks_type_check CHECK (task_type IN (
    'call','email','demo','proposal','research','follow-up','meeting','other'
  )),
  CONSTRAINT company_private_tasks_priority_check CHECK (priority IN ('low','medium','high')),
  CONSTRAINT company_private_tasks_status_check CHECK (status IN ('open','completed','cancelled')),
  CONSTRAINT company_private_tasks_source_check CHECK (
    last_change_source IN ('manual','import','system','database')
  )
);

CREATE INDEX IF NOT EXISTS company_private_tasks_company_due_idx
  ON public.company_private_tasks(company_id, status, due_at);
CREATE INDEX IF NOT EXISTS company_private_tasks_due_idx
  ON public.company_private_tasks(status, due_at);

ALTER TABLE public.company_private_opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_private_tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_private_opportunities_admin_only ON public.company_private_opportunities;
CREATE POLICY company_private_opportunities_admin_only ON public.company_private_opportunities
  TO authenticated USING (public.towersignal_is_admin()) WITH CHECK (public.towersignal_is_admin());

DROP POLICY IF EXISTS company_private_tasks_admin_only ON public.company_private_tasks;
CREATE POLICY company_private_tasks_admin_only ON public.company_private_tasks
  TO authenticated USING (public.towersignal_is_admin()) WITH CHECK (public.towersignal_is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_private_opportunities TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_private_tasks TO authenticated;

DROP TRIGGER IF EXISTS company_private_opportunities_audit ON public.company_private_opportunities;
CREATE TRIGGER company_private_opportunities_audit
AFTER INSERT OR UPDATE OR DELETE ON public.company_private_opportunities
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_company_change('opportunity','opportunity_id');

DROP TRIGGER IF EXISTS company_private_tasks_audit ON public.company_private_tasks;
CREATE TRIGGER company_private_tasks_audit
AFTER INSERT OR UPDATE OR DELETE ON public.company_private_tasks
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_company_change('task','task_id');

COMMIT;
