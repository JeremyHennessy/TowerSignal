BEGIN;

CREATE TABLE IF NOT EXISTS public.workflow_saved_views (
  user_id text DEFAULT auth.user_id() NOT NULL,
  view_id text NOT NULL,
  name text NOT NULL,
  filters jsonb DEFAULT '{}'::jsonb NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  CONSTRAINT workflow_saved_views_pkey PRIMARY KEY (user_id, view_id)
);

CREATE TABLE IF NOT EXISTS public.workflow_watchlists (
  user_id text DEFAULT auth.user_id() NOT NULL,
  watchlist_id text NOT NULL,
  name text NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  CONSTRAINT workflow_watchlists_pkey PRIMARY KEY (user_id, watchlist_id)
);

CREATE TABLE IF NOT EXISTS public.workflow_accounts (
  user_id text DEFAULT auth.user_id() NOT NULL,
  system_id text NOT NULL,
  status text DEFAULT 'new' NOT NULL,
  note text DEFAULT '' NOT NULL,
  next_action_date date,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  CONSTRAINT workflow_accounts_pkey PRIMARY KEY (user_id, system_id),
  CONSTRAINT workflow_accounts_status_check CHECK (status IN ('new','investigate','contacted','follow-up','monitor','dismissed'))
);

CREATE TABLE IF NOT EXISTS public.workflow_watchlist_members (
  user_id text DEFAULT auth.user_id() NOT NULL,
  watchlist_id text NOT NULL,
  system_id text NOT NULL,
  added_at timestamptz DEFAULT now() NOT NULL,
  CONSTRAINT workflow_watchlist_members_pkey PRIMARY KEY (user_id, watchlist_id, system_id),
  CONSTRAINT workflow_watchlist_members_watchlist_fk FOREIGN KEY (user_id, watchlist_id)
    REFERENCES public.workflow_watchlists(user_id, watchlist_id) ON DELETE CASCADE,
  CONSTRAINT workflow_watchlist_members_account_fk FOREIGN KEY (user_id, system_id)
    REFERENCES public.workflow_accounts(user_id, system_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS workflow_accounts_user_status_idx
  ON public.workflow_accounts (user_id, status);
CREATE INDEX IF NOT EXISTS workflow_accounts_user_next_action_idx
  ON public.workflow_accounts (user_id, next_action_date);

ALTER TABLE public.workflow_saved_views ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_watchlist_members ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='workflow_saved_views' AND policyname='workflow_saved_views_own_rows') THEN
    CREATE POLICY workflow_saved_views_own_rows ON public.workflow_saved_views
      TO authenticated USING (auth.user_id() = user_id) WITH CHECK (auth.user_id() = user_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='workflow_watchlists' AND policyname='workflow_watchlists_own_rows') THEN
    CREATE POLICY workflow_watchlists_own_rows ON public.workflow_watchlists
      TO authenticated USING (auth.user_id() = user_id) WITH CHECK (auth.user_id() = user_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='workflow_accounts' AND policyname='workflow_accounts_own_rows') THEN
    CREATE POLICY workflow_accounts_own_rows ON public.workflow_accounts
      TO authenticated USING (auth.user_id() = user_id) WITH CHECK (auth.user_id() = user_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='workflow_watchlist_members' AND policyname='workflow_watchlist_members_own_rows') THEN
    CREATE POLICY workflow_watchlist_members_own_rows ON public.workflow_watchlist_members
      TO authenticated USING (auth.user_id() = user_id) WITH CHECK (auth.user_id() = user_id);
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workflow_saved_views TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workflow_watchlists TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workflow_accounts TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workflow_watchlist_members TO authenticated;

COMMIT;
