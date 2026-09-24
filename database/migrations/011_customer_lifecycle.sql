BEGIN;

CREATE TABLE IF NOT EXISTS public.company_sales_subscriptions (
  subscription_id text PRIMARY KEY,
  sales_account_id text NOT NULL REFERENCES public.company_sales_accounts(sales_account_id) ON DELETE CASCADE,
  opportunity_id text REFERENCES public.company_private_opportunities(opportunity_id) ON DELETE SET NULL,
  proposal_id text REFERENCES public.company_sales_proposals(proposal_id) ON DELETE SET NULL,
  primary_contact_id text REFERENCES public.company_private_contacts(contact_id) ON DELETE SET NULL,
  status text DEFAULT 'onboarding' NOT NULL,
  plan_name text NOT NULL,
  arr numeric(18,2),
  seats integer,
  start_date date,
  renewal_date date,
  term_months integer,
  billing_cadence text DEFAULT 'annual' NOT NULL,
  auto_renew boolean DEFAULT false NOT NULL,
  contract_url text,
  customer_success_owner text,
  notes text,
  ended_at timestamptz,
  end_reason text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  last_change_source text DEFAULT 'manual' NOT NULL,
  last_change_batch_id text,
  CONSTRAINT company_sales_subscriptions_status_check CHECK (status IN ('onboarding','active','paused','cancelled','expired')),
  CONSTRAINT company_sales_subscriptions_value_check CHECK (
    (arr IS NULL OR arr >= 0)
    AND (seats IS NULL OR seats >= 0)
    AND (term_months IS NULL OR term_months > 0)
  ),
  CONSTRAINT company_sales_subscriptions_billing_check CHECK (billing_cadence IN ('monthly','quarterly','annual','multi-year','other')),
  CONSTRAINT company_sales_subscriptions_source_check CHECK (last_change_source IN ('manual','import','system','database')),
  CONSTRAINT company_sales_subscriptions_account_pair UNIQUE(subscription_id,sales_account_id)
);

CREATE INDEX IF NOT EXISTS company_sales_subscriptions_account_idx
  ON public.company_sales_subscriptions(sales_account_id,status,renewal_date);
CREATE INDEX IF NOT EXISTS company_sales_subscriptions_renewal_idx
  ON public.company_sales_subscriptions(status,renewal_date);

CREATE TABLE IF NOT EXISTS public.company_sales_renewals (
  renewal_id text PRIMARY KEY,
  subscription_id text NOT NULL,
  sales_account_id text NOT NULL,
  primary_contact_id text REFERENCES public.company_private_contacts(contact_id) ON DELETE SET NULL,
  status text DEFAULT 'upcoming' NOT NULL,
  renewal_date date NOT NULL,
  current_arr numeric(18,2),
  proposed_arr numeric(18,2),
  renewed_arr numeric(18,2),
  expected_decision_date date,
  next_step text,
  notes text,
  completed_at timestamptz,
  churn_reason text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  created_by text DEFAULT auth.user_id(),
  updated_by text DEFAULT auth.user_id(),
  last_change_source text DEFAULT 'manual' NOT NULL,
  last_change_batch_id text,
  CONSTRAINT company_sales_renewals_subscription_account_fk
    FOREIGN KEY(subscription_id,sales_account_id)
    REFERENCES public.company_sales_subscriptions(subscription_id,sales_account_id)
    ON DELETE CASCADE,
  CONSTRAINT company_sales_renewals_status_check CHECK (status IN ('upcoming','contacted','negotiating','renewed','churned','cancelled')),
  CONSTRAINT company_sales_renewals_value_check CHECK (
    (current_arr IS NULL OR current_arr >= 0)
    AND (proposed_arr IS NULL OR proposed_arr >= 0)
    AND (renewed_arr IS NULL OR renewed_arr >= 0)
  ),
  CONSTRAINT company_sales_renewals_source_check CHECK (last_change_source IN ('manual','import','system','database'))
);

CREATE INDEX IF NOT EXISTS company_sales_renewals_account_idx
  ON public.company_sales_renewals(sales_account_id,status,renewal_date);
CREATE INDEX IF NOT EXISTS company_sales_renewals_subscription_idx
  ON public.company_sales_renewals(subscription_id,renewal_date DESC);

ALTER TABLE public.company_sales_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_sales_renewals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_sales_subscriptions_admin_only ON public.company_sales_subscriptions;
CREATE POLICY company_sales_subscriptions_admin_only ON public.company_sales_subscriptions
  TO authenticated USING (public.towersignal_is_admin()) WITH CHECK (public.towersignal_is_admin());

DROP POLICY IF EXISTS company_sales_renewals_admin_only ON public.company_sales_renewals;
CREATE POLICY company_sales_renewals_admin_only ON public.company_sales_renewals
  TO authenticated USING (public.towersignal_is_admin()) WITH CHECK (public.towersignal_is_admin());

GRANT SELECT,INSERT,UPDATE,DELETE ON public.company_sales_subscriptions TO authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.company_sales_renewals TO authenticated;

DROP TRIGGER IF EXISTS company_sales_subscriptions_audit ON public.company_sales_subscriptions;
CREATE TRIGGER company_sales_subscriptions_audit
AFTER INSERT OR UPDATE OR DELETE ON public.company_sales_subscriptions
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_sales_account('subscription','subscription_id');

DROP TRIGGER IF EXISTS company_sales_renewals_audit ON public.company_sales_renewals;
CREATE TRIGGER company_sales_renewals_audit
AFTER INSERT OR UPDATE OR DELETE ON public.company_sales_renewals
FOR EACH ROW EXECUTE FUNCTION public.towersignal_audit_sales_account('renewal','renewal_id');

CREATE OR REPLACE VIEW public.company_sales_customer_lifecycle_state
WITH (security_invoker=true)
AS
SELECT
  a.sales_account_id,
  (
    SELECT count(*)::integer
    FROM public.company_sales_subscriptions s
    WHERE s.sales_account_id=a.sales_account_id
      AND s.status IN ('onboarding','active','paused')
  ) AS live_subscription_count,
  (
    SELECT coalesce(sum(s.arr),0)::numeric
    FROM public.company_sales_subscriptions s
    WHERE s.sales_account_id=a.sales_account_id
      AND s.status IN ('onboarding','active','paused')
  ) AS live_arr,
  (
    SELECT min(s.renewal_date)
    FROM public.company_sales_subscriptions s
    WHERE s.sales_account_id=a.sales_account_id
      AND s.status IN ('onboarding','active','paused')
      AND s.renewal_date IS NOT NULL
  ) AS next_subscription_renewal_date,
  (
    SELECT count(*)::integer
    FROM public.company_sales_renewals r
    WHERE r.sales_account_id=a.sales_account_id
      AND r.status IN ('upcoming','contacted','negotiating')
  ) AS open_renewal_count,
  (
    SELECT min(r.renewal_date)
    FROM public.company_sales_renewals r
    WHERE r.sales_account_id=a.sales_account_id
      AND r.status IN ('upcoming','contacted','negotiating')
  ) AS next_open_renewal_date
FROM public.company_sales_accounts a
WHERE a.record_status='active';

GRANT SELECT ON public.company_sales_customer_lifecycle_state TO authenticated;

COMMIT;
