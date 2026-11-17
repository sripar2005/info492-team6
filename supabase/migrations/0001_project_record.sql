-- ClauseStream: the shared project record and change threads.
-- Run once in Supabase: SQL Editor -> New query -> paste -> Run. Safe to re-run (uses IF NOT EXISTS / OR REPLACE).
--
-- Model
--   projects   one construction project
--   members    who is on it, and which party they speak for (sub, gc, architect, owner)
--   documents  every source document (contract, spec, RFI, ASI, submittal, schedule, daily report, approved minutes, change order)
--   pieces     the small citable units a document is split into (a clause, an RFI answer, a daily report entry...)
--   links      how pieces and documents relate (RFI-112 answered_by ASI-7, CP-0201 caused_by RFI-112)
--   threads    one per change, shared by all parties
--   events     append-only log of everything that happens on a thread (draft, check, submit, return with reason, decision)
-- Access: row-level security. You only see projects you are a member of. Events cannot be edited or deleted.

create extension if not exists pgcrypto;

do $$ begin
  create type party as enum ('sub', 'gc', 'architect', 'owner');
exception when duplicate_object then null; end $$;
do $$ begin
  create type doc_kind as enum ('contract', 'spec', 'drawing_index', 'rfi', 'asi', 'submittal', 'schedule', 'daily_report', 'minutes', 'change_order', 'other');
exception when duplicate_object then null; end $$;
do $$ begin
  create type doc_source as enum ('upload', 'procore', 'synthetic');
exception when duplicate_object then null; end $$;
do $$ begin
  create type thread_status as enum ('draft', 'with_gc', 'with_architect', 'with_owner', 'returned', 'approved', 'rejected', 'withdrawn');
exception when duplicate_object then null; end $$;
do $$ begin
  create type event_kind as enum ('note', 'draft', 'check', 'submit', 'return', 'approve', 'reject', 'comment', 'link', 'attach', 'evidence');
exception when duplicate_object then null; end $$;

create table if not exists projects (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  owner_org   text,
  synthetic   boolean not null default false,
  created_by  uuid references auth.users default auth.uid(),
  created_at  timestamptz not null default now()
);

create table if not exists members (
  project_id  uuid not null references projects on delete cascade,
  user_id     uuid not null references auth.users on delete cascade,
  party       party not null,
  is_admin    boolean not null default false,
  added_at    timestamptz not null default now(),
  primary key (project_id, user_id)
);

create table if not exists documents (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects on delete cascade,
  kind         doc_kind not null,
  number       text,                 -- e.g. RFI-112, ASI-7, CP-0201, Section 01 26 00
  title        text not null,
  issued_on    date,
  author_party party,
  source       doc_source not null default 'upload',
  external_id  text,                 -- e.g. the Procore id, so a re-sync updates instead of duplicating
  file_path    text,                 -- path in the 'documents' storage bucket, if a file was uploaded
  meta         jsonb not null default '{}',
  created_by   uuid references auth.users default auth.uid(),
  created_at   timestamptz not null default now(),
  unique (project_id, source, external_id)
);

create table if not exists pieces (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects on delete cascade,
  document_id  uuid not null references documents on delete cascade,
  ordinal      int not null,         -- order within the document
  section      text,                 -- clause or paragraph number, activity id, report date...
  body         text not null,        -- the exact text that gets quoted
  piece_date   date,
  party        party,
  meta         jsonb not null default '{}',
  search       tsvector generated always as (to_tsvector('english', coalesce(section, '') || ' ' || body)) stored
);
create index if not exists pieces_search on pieces using gin (search);
create index if not exists pieces_doc on pieces (document_id, ordinal);

create table if not exists links (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects on delete cascade,
  from_doc     uuid references documents on delete cascade,
  from_piece   uuid references pieces on delete cascade,
  to_doc       uuid references documents on delete cascade,
  to_piece     uuid references pieces on delete cascade,
  relation     text not null,        -- answered_by, caused_by, priced_in, supersedes, cites ...
  created_by   uuid references auth.users default auth.uid(),
  created_at   timestamptz not null default now(),
  check (coalesce(from_doc, from_piece) is not null and coalesce(to_doc, to_piece) is not null)
);

create table if not exists threads (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects on delete cascade,
  number       text not null,        -- CP-0201
  title        text not null,
  status       thread_status not null default 'draft',
  holder       party not null default 'sub',
  document_id  uuid references documents,  -- the change order document once it exists
  created_by   uuid references auth.users default auth.uid(),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (project_id, number)
);

create table if not exists events (
  id           bigint generated always as identity primary key,
  thread_id    uuid not null references threads on delete cascade,
  project_id   uuid not null references projects on delete cascade,
  actor        uuid references auth.users default auth.uid(),
  party        party not null,
  kind         event_kind not null,
  body         text,
  reason       text,                 -- for returns: a short reason code, e.g. fee_on_excluded, late_notice, missing_backup
  payload      jsonb not null default '{}',  -- checksheet rows, drafted proposal, citations (piece ids), AI model used...
  created_at   timestamptz not null default now()
);
create index if not exists events_thread on events (thread_id, id);

-- Membership helpers (security definer so policies can call them without recursion)
create or replace function is_member(p uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from members where project_id = p and user_id = auth.uid());
$$;
create or replace function my_party(p uuid) returns party
language sql stable security definer set search_path = public as $$
  select party from members where project_id = p and user_id = auth.uid();
$$;
create or replace function is_admin(p uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from members where project_id = p and user_id = auth.uid() and is_admin);
$$;

-- Whoever creates a project becomes its admin member (as GC by default; change in members).
create or replace function add_creator() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into members (project_id, user_id, party, is_admin) values (new.id, auth.uid(), 'gc', true)
  on conflict do nothing;
  return new;
end $$;
drop trigger if exists projects_add_creator on projects;
create trigger projects_add_creator after insert on projects for each row execute function add_creator();

-- A new event moves the thread along.
create or replace function advance_thread() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  update threads set updated_at = now(),
    status = case new.kind
      when 'submit'  then (case new.party when 'sub' then 'with_gc' when 'gc' then 'with_architect' when 'architect' then 'with_owner' else status end)::thread_status
      when 'return'  then 'returned'::thread_status
      when 'approve' then (case when new.party = 'owner' then 'approved' else status end)::thread_status
      when 'reject'  then 'rejected'::thread_status
      else status end,
    holder = case new.kind
      when 'submit'  then (case new.party when 'sub' then 'gc' when 'gc' then 'architect' when 'architect' then 'owner' else holder end)::party
      when 'return'  then (case new.party when 'owner' then 'architect' when 'architect' then 'gc' when 'gc' then 'sub' else holder end)::party
      else holder end
  where id = new.thread_id;
  return new;
end $$;
drop trigger if exists events_advance on events;
create trigger events_advance after insert on events for each row execute function advance_thread();

-- Row-level security
alter table projects  enable row level security;
alter table members   enable row level security;
alter table documents enable row level security;
alter table pieces    enable row level security;
alter table links     enable row level security;
alter table threads   enable row level security;
alter table events    enable row level security;

drop policy if exists p_read on projects;   create policy p_read on projects for select using (is_member(id) or created_by = auth.uid());
drop policy if exists p_new on projects;    create policy p_new on projects for insert with check (auth.uid() is not null);
drop policy if exists p_edit on projects;   create policy p_edit on projects for update using (is_admin(id));

drop policy if exists m_read on members;    create policy m_read on members for select using (is_member(project_id));
drop policy if exists m_add on members;     create policy m_add on members for insert with check (is_admin(project_id));
drop policy if exists m_edit on members;    create policy m_edit on members for update using (is_admin(project_id));
drop policy if exists m_del on members;     create policy m_del on members for delete using (is_admin(project_id));

drop policy if exists d_read on documents;  create policy d_read on documents for select using (is_member(project_id));
drop policy if exists d_add on documents;   create policy d_add on documents for insert with check (is_member(project_id));
drop policy if exists d_edit on documents;  create policy d_edit on documents for update using (is_admin(project_id) or created_by = auth.uid());

drop policy if exists pc_read on pieces;    create policy pc_read on pieces for select using (is_member(project_id));
drop policy if exists pc_add on pieces;     create policy pc_add on pieces for insert with check (is_member(project_id));
drop policy if exists pc_del on pieces;     create policy pc_del on pieces for delete using (is_admin(project_id));

drop policy if exists l_read on links;      create policy l_read on links for select using (is_member(project_id));
drop policy if exists l_add on links;       create policy l_add on links for insert with check (is_member(project_id));

drop policy if exists t_read on threads;    create policy t_read on threads for select using (is_member(project_id));
drop policy if exists t_add on threads;     create policy t_add on threads for insert with check (is_member(project_id));
-- threads change only through events (the trigger), so no update policy for users

-- Events: append-only, and you can only speak for your own party.
drop policy if exists e_read on events;     create policy e_read on events for select using (is_member(project_id));
drop policy if exists e_add on events;      create policy e_add on events for insert with check (is_member(project_id) and party = my_party(project_id) and actor = auth.uid());

-- File storage for uploaded documents: private bucket, files under <project_id>/...
insert into storage.buckets (id, name, public) values ('documents', 'documents', false) on conflict (id) do nothing;
drop policy if exists s_read on storage.objects;
create policy s_read on storage.objects for select using (bucket_id = 'documents' and is_member((split_part(name, '/', 1))::uuid));
drop policy if exists s_add on storage.objects;
create policy s_add on storage.objects for insert with check (bucket_id = 'documents' and is_member((split_part(name, '/', 1))::uuid));
