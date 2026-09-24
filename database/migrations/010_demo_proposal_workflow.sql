BEGIN;

CREATE TABLE IF NOT EXISTS public.company_sales_demos (
  demo_id text PRIMARY KEY,
  sales_account_id text NOT NULL REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE CASCADE,
  opportunity_id text REFERENCES public.company_private_opportunities(opportunity_id) ON DELETE SET NULL,
  primary_contact_id text REFERENCES public.company_private_contacts(contact_id) ON DELETE SET NULL,
  status text DEFAULT 'scheduled' NOT NULL,
  scheduled_at timestamptz,
  completed_at timestamptz,
  meeting_url text,
  attendees jsonb DEFAULT '[]'::jsonb NOT NULL,
  demo_scope text,
  demo_accounts text,
  objections text,
  outcome text,
  next_step text,
  notes text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  last_change_source text DEFAULT 'manual' NOT NULL,
  last_change_batch_id text,
  CONSTRAINT company_sales_demos_status_check CHECK (status IN ('scheduled','completed','cancelled','no-show')),
  CONSTRAINT company_sales_demos_source_check CHECK (last_change_source IN ('manual','import','system','database'))
);

CREATE INDEX IF NOT EXISTS company_sales_demos_account_idx
  ON public.company_sales_demos(sales_account_id,scheduled_at DESC);
CREATE INDEX IF NOT EXISTS company_sales_demos_opportunity_idx
  ON public.company_sales_demos(opportunity_id,scheduled_at DESC);
CREATE INDEX IF NOT EXISTS company_sales_demos_upcoming_idx
  ON public.company_sales_demos(status,scheduled_at);

CREATE TABLE IF NOT EXISTS public.company_sales_proposals (
  proposal_id text PRIMARY KEY,
  sales_account_id text NOT NULL REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE CASCADE,
  opportunity_id text REFERENCES public.company_private_opportunities(opportunity_id) ON DELETE SET NULL,
  decision_maker_contact_id text REFERENCES public.company_private_contacts(contact_id) ON DELETE SET NULL,
  status text DEFAULT 'draft' NOT NULL,
  package_name text,
  proposed_arr numeric(18,2),
  one_time_value numeric(18,2),
  seats integer,
  term_months integer,
  sent_at timestamptz,
  valid_until date,
  expected_decision_date date,
  proposal_url text,
  procurement_blockers text,
  objections text,
  next_step text,
  notes text,
  accepted_at timestamptz,
  rejected_at timestamptz,
  rejection_reason text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  last_change_source text DEFAULT 'manual' NOT NULL,
  last_change_batch_id text,
  CONSTRAINT company_sales_proposals_status_check CHECK (status IN ('draft','sent','revising','accepted','rejected','expired')),
  CONSTRAINT company_sales_proposals_value_check CHECK (
    (proposed_arr IS NULL OR proposed_arr >= 0)
    AND (one_time_value IS NULL OR one_time_value >= 0)
    AND (seats IS NULL OR seats >= 0)
    AND (term_months IS NULL OR term_months > 0)
  ),
  CONSTRAINT company_sales_proposals_source_check CHECK (last_change_source IN ('manual','import','system','database'))
);

CREATE INDEX IF NOT EXISTS company_sales_proposals_account_idx
  ON public.company_sales_proposals(sales_account_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS company_sales_proposals_opportunity_idx
  ON public.company_sales_proposals(opportunity_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS company_sales_proposals_status_idx
  ON public.company_sales_proposals(status,expected_decision_date);

ALTER TABLE public.company_sales_demos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_sales_proposals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_sales_demos_admin_only ON public.company_sales_demos;
CREATE POLICY company_sales_demos_admin_only ON public.company_sales_demos
  TO authenticated USING (public.towersignal_is_admin()) WITH CHECK (public.towersignal_is_admin());

DROP POLICY IF EXISTS company_sales_proposals_admin_only ON public.company_sales_proposals;
CREATE POLICY company_sales_proposals_admin_only ON public.company_sales_proposals
  TO authenticated USING (public.towersignal_is_admin()) WITH CHECK (public.towersignal_is_admin());

GRANT SELECT,INSERT,UPDATE,DELETE ON public.company_sales_demos TO authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.company_sales_proposals TO authenticated;

DROP TRIGGER IF EXISTS company_sales_demos_audit ON public.company_sales_demos;
CREATE TRIGGER company_sales_demos_audit
AFTER INSERT OR UPDATE OR DELETE ON public.company_sales_demos
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_sales_account('demo','demo_id');

DROP TRIGGER IF EXISTS company_sales_proposals_audit ON public.company_sales_proposals;
CREATE TRIGGER company_sales_proposals_audit
AFTER INSERT OR UPDATE OR DELETE ON public.company_sales_proposals
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_sales_account('proposal','proposal_id');

CREATE OR REPLACE VIEW public.company_sales_demo_proposal_state
WITH (security_invoker=true)
AS
SELECT
  a.sales_account_id,
  count(d.*) FILTER (WHERE d.status='scheduled' AND d.scheduled_at >= now())::integer AS upcoming_demo_count,
  min(d.scheduled_at) FILTER (WHERE d.status='scheduled' AND d.scheduled_at >= now()) AS next_demo_at,
  count(p.*) FILTER (WHERE p.status IN ('sent','revising'))::integer AS open_proposal_count,
  coalesce(sum(p.proposed_arr) FILTER (WHERE p.status IN ('sent','revising')),0)::numeric AS open_proposal_arr,
  min(p.expected_decision_date) FILTER (WHERE p.status IN ('sent','revising') AND p.expected_decision_date IS NOT NULL) AS next_decision_date
FROM public.company_sales_accounts a
LEFT JOIN public.company_sales_demos d ON d.sales_account_id=a.sales_account_id
LEFT JOIN public.company_sales_proposals p ON p.sales_account_id=a.sales_account_id
WHERE a.record_status='active'
GROUP BY a.sales_account_id;

GRANT SELECT ON public.company_sales_demo_proposal_state TO authenticated;

COMMIT;
