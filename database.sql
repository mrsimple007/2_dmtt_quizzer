-- ============================================================================
--  DMTT attestat bot (Hulkar Ibragimova): separate tables in the SAME Supabase
--  project. Every table is prefixed  dmtt_  so nothing mixes with your own bot.
--
--  Run once:  Supabase -> SQL Editor -> New query -> paste -> Run
--  Safe to re-run (IF NOT EXISTS everywhere).
--
--  Columns were taken from what the code reads/writes. After running, run the
--  CHECK query at the bottom: it lists any column your live tables have that
--  these new ones are missing.
-- ============================================================================

-- 1) USERS ------------------------------------------------------------------
create table if not exists public.dmtt_users (
  user_id               bigint primary key,
  username              text        default '',
  first_name            text        default '',
  last_name             text        default '',
  language              text        default 'uz',
  quiz_type             text        default 'mc',
  quiz_time             integer     default 30,
  quiz_questions        integer     default 5,
  total_quizzes         integer     default 0,
  correct_answers       integer     default 0,
  total_correct_answers integer     default 0,
  is_premium            boolean     default false,
  balance               bigint      default 0,      -- in kopecks (UZS * 100)
  total_payments        bigint      default 0,
  daily_free_quizzes_used integer   default 0,
  last_free_quiz_reset  timestamptz,
  subscription_type     text,
  subscription_start    timestamptz,
  subscription_end      timestamptz,
  invited_by            bigint,                      -- referral: inviter's user_id
  created_at            timestamptz default now(),
  last_interaction      timestamptz default now()
);
create index if not exists dmtt_users_invited_by_idx on public.dmtt_users (invited_by);
create index if not exists dmtt_users_last_interaction_idx on public.dmtt_users (last_interaction);

-- 2) QUIZZES ----------------------------------------------------------------
create table if not exists public.dmtt_quizzes (
  id             uuid primary key,
  user_id        bigint not null,
  quiz_data      jsonb  not null,
  title          text,
  summary        text,
  language       text default 'uz',
  quiz_time      integer,
  num_questions  integer,
  question_count integer generated always as (num_questions) stored,  -- read by "My quizzes"
  author         text,
  created_at     timestamptz default now()
);
create index if not exists dmtt_quizzes_user_idx on public.dmtt_quizzes (user_id, created_at desc);

-- 3) QUIZ ATTEMPTS (results / leaderboard) -----------------------------------
create table if not exists public.dmtt_quiz_attempts (
  id              bigserial primary key,
  quiz_id         uuid   not null,
  user_id         bigint not null,
  username        text   default '',
  first_name      text   default 'Anonymous',
  score           integer,
  total_questions integer,
  time_spent      double precision,
  created_at      timestamptz default now()
);
create index if not exists dmtt_attempts_quiz_idx on public.dmtt_quiz_attempts (quiz_id);
create index if not exists dmtt_attempts_user_idx on public.dmtt_quiz_attempts (user_id);

-- 4) GROUPS -----------------------------------------------------------------
create table if not exists public.dmtt_groups (
  id                  bigint primary key,            -- Telegram group chat id
  title               text,
  username            text,
  type                text,
  added_by_user_id    bigint,
  added_by_first_name text,
  added_by_last_name  text,
  added_by_username   text,
  total_members       integer,
  added_at            timestamptz default now(),
  created_at          timestamptz default now(),
  last_interaction    timestamptz default now()
);

-- 5) UPLOADED FILES (processing log) ----------------------------------------
create table if not exists public.dmtt_files (
  id            uuid default gen_random_uuid() primary key,
  user_id       bigint not null references public.dmtt_users(user_id) on delete cascade,
  file_name     text,
  file_type     text,
  file_size     integer,
  content_type  text,
  status        text default 'pending',
  error_message text,
  quiz_type     text default 'mc',
  quiz_time     integer default 30,
  quiz_questions integer default 5,
  created_at    timestamptz default now(),
  processed_at  timestamptz
);
create index if not exists dmtt_files_user_idx    on public.dmtt_files (user_id);
create index if not exists dmtt_files_status_idx  on public.dmtt_files (status);
create index if not exists dmtt_files_created_idx on public.dmtt_files (created_at);

-- 6) PAYMENTS ---------------------------------------------------------------
create table if not exists public.dmtt_payment_history (
  id             bigserial primary key,
  user_id        bigint not null,
  amount         bigint,                              -- kopecks
  payment_type   text,                                -- balance_topup / quiz_generation / subscription
  payment_method text,                                -- manual / balance_deduction / ...
  transaction_id text,
  status         text default 'completed',
  metadata       jsonb,
  created_at     timestamptz default now()
);
create index if not exists dmtt_payment_history_user_idx   on public.dmtt_payment_history (user_id);
create index if not exists dmtt_payment_history_status_idx on public.dmtt_payment_history (status, created_at);

create table if not exists public.dmtt_payment_tokens (   -- only used by automatic (GlobalPay) payments
  id            bigserial primary key,
  user_id       text,
  service_token text unique,
  amount_uzs    integer,
  is_custom     boolean default false,
  status        text default 'PENDING',
  check_count   integer default 0,
  created_at    timestamptz default now(),
  updated_at    timestamptz
);

create table if not exists public.dmtt_subscription_history (
  id                bigserial primary key,
  user_id           bigint not null,
  subscription_type text,
  amount            bigint,
  payment_method    text,
  start_date        timestamptz,
  end_date          timestamptz,
  status            text default 'active',
  created_at        timestamptz default now()
);
create index if not exists dmtt_subscription_history_user_idx on public.dmtt_subscription_history (user_id);

-- 7) ADMIN SETTINGS (manual / auto payment mode) -----------------------------
create table if not exists public.dmtt_admin_settings (
  admin_id     bigint primary key,
  bot_id       text default 'dmtt_quiz',
  payment_mode text default 'manual',
  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);
-- Start in MANUAL mode (users pay to your card, you confirm). Change the id if
-- your ADMIN_CHAT_ID is different.
insert into public.dmtt_admin_settings (admin_id, bot_id, payment_mode)
values (8437026582, 'dmtt_quiz', 'manual')
on conflict (admin_id) do nothing;

-- 8) SECURITY: the bot uses the service_role key, which bypasses RLS.
--    Turning RLS on (with no policies) blocks anyone using the public anon key.
alter table public.dmtt_users              enable row level security;
alter table public.dmtt_quizzes            enable row level security;
alter table public.dmtt_quiz_attempts      enable row level security;
alter table public.dmtt_groups             enable row level security;
alter table public.dmtt_files              enable row level security;
alter table public.dmtt_payment_history    enable row level security;
alter table public.dmtt_payment_tokens     enable row level security;
alter table public.dmtt_subscription_history enable row level security;
alter table public.dmtt_admin_settings     enable row level security;

-- ============================================================================
-- CHECK (run separately, after the above): columns that exist in your CURRENT
-- tables but are missing in the new dmtt_ ones. An empty result = all good.
-- If it returns rows, add them:  alter table public.dmtt_xxx add column <name> <type>;
-- ============================================================================
-- select m.old_t as old_table, o.column_name, o.data_type
-- from (values
--   ('simplequizzer_users','dmtt_users'),
--   ('quizzes_simplequiz','dmtt_quizzes'),
--   ('quiz_attempts','dmtt_quiz_attempts'),
--   ('groups_simplequiz','dmtt_groups'),
--   ('simplequizzer_files','dmtt_files'),
--   ('quiz_payments_history','dmtt_payment_history'),
--   ('payment_tokens','dmtt_payment_tokens'),
--   ('subscription_history','dmtt_subscription_history'),
--   ('admin_settings','dmtt_admin_settings')
-- ) as m(old_t, new_t)
-- join information_schema.columns o
--   on o.table_schema = 'public' and o.table_name = m.old_t
-- left join information_schema.columns n
--   on n.table_schema = 'public' and n.table_name = m.new_t and n.column_name = o.column_name
-- where n.column_name is null
-- order by 1, 2;