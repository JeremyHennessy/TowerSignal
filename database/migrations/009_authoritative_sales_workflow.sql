BEGIN;

COMMENT ON COLUMN public.company_private_profiles.relationship_status IS
  'Legacy source-identity CRM field. Deprecated for active sales workflow; use company_sales_accounts.account_classification and company_private_opportunities.stage.';
COMMENT ON COLUMN public.company_private_profiles.account_owner IS
  'Legacy source-identity owner field. Deprecated for active sales workflow; use company_sales_accounts.account_owner.';
COMMENT ON COLUMN public.company_private_profiles.next_action_date IS
  'Legacy source-identity next-action field. Deprecated for active sales workflow; use company_private_tasks.due_at or company_private_opportunities.next_action_date.';
COMMENT ON COLUMN public.company_private_profiles.last_contacted_at IS
  'Legacy source-identity contact timestamp. Historical only; use company_private_activities.occurred_at for current activity history.';

CREATE OR REPLACE VIEW public.company_sales_pipeline_state
WITH (security_invoker=true)
AS
WITH opportunity_summary AS (
  SELECT
    sales_account_id,
    count(*) FILTER (WHERE stage IN ('lead','qualified','demo-scheduled','demo-complete','proposal','negotiation'))::integer AS open_opportunity_count,
    coalesce(sum(estimated_arr) FILTER (WHERE stage IN ('lead','qualified','demo-scheduled','demo-complete','proposal','negotiation')),0)::numeric AS open_pipeline_arr,
    max(CASE stage
      WHEN 'negotiation' THEN 60
      WHEN 'proposal' THEN 50
      WHEN 'demo-complete' THEN 40
      WHEN 'demo-scheduled' THEN 30
      WHEN 'qualified' THEN 20
      WHEN 'lead' THEN 10
      WHEN 'closed-won' THEN 70
      WHEN 'nurture' THEN 5
      ELSE 0 END) AS stage_rank,
    min(next_action_date) FILTER (
      WHERE stage IN ('lead','qualified','demo-scheduled','demo-complete','proposal','negotiation')
        AND next_action_date IS NOT NULL
    ) AS opportunity_next_action
  FROM public.company_private_opportunities
  WHERE sales_account_id IS NOT NULL
  GROUP BY sales_account_id
),
task_summary AS (
  SELECT
    sales_account_id,
    count(*) FILTER (WHERE status='open')::integer AS open_task_count,
    min(due_at) FILTER (WHERE status='open' AND due_at IS NOT NULL) AS next_task_due_at,
    count(*) FILTER (WHERE status='open' AND due_at < now())::integer AS overdue_task_count
  FROM public.company_private_tasks
  WHERE sales_account_id IS NOT NULL
  GROUP BY sales_account_id
),
activity_summary AS (
  SELECT
    sales_account_id,
    max(occurred_at) AS last_activity_at
  FROM public.company_private_activities
  WHERE sales_account_id IS NOT NULL
  GROUP BY sales_account_id
)
SELECT
  a.sales_account_id,
  a.display_name,
  a.account_classification,
  a.account_owner,
  coalesce(o.open_opportunity_count,0) AS open_opportunity_count,
  coalesce(o.open_pipeline_arr,0) AS open_pipeline_arr,
  coalesce(t.open_task_count,0) AS open_task_count,
  coalesce(t.overdue_task_count,0) AS overdue_task_count,
  o.opportunity_next_action,
  t.next_task_due_at,
  act.last_activity_at
FROM public.company_sales_accounts a
LEFT JOIN opportunity_summary o USING(sales_account_id)
LEFT JOIN task_summary t USING(sales_account_id)
LEFT JOIN activity_summary act USING(sales_account_id)
WHERE a.record_status='active';

GRANT SELECT ON public.company_sales_pipeline_state TO authenticated;

COMMIT;
