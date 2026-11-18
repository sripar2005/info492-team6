-- ClauseStream platform: companies, the contract chain, visibility that follows it, changes in tiers,
-- an append-only activity log with AI receipts, schedule versions, the schedule of values, and field links.
--
-- FRESH START: this drops the tables from 0001 and 0002 (and everything in them) and builds the new model.
-- Safe to re-run (it starts over each time). Run in Supabase: SQL Editor -> New query -> paste the whole file -> Run.
--
-- Model
--   companies          an owner, architect, GC/CM or sub; people belong to companies
--   company_people     who works for which company
--   projects           one construction project, with its contract type
--   project_companies  which companies are on a project, and their role
--   invites            an email invited to join a project for a company
--   contracts          the chain: prime (owner-GC/CM), design (owner-architect), sub (GC/CM-sub), with flow-down parent
--   contract_terms     the terms read from a contract, each with its clause and sentence, confirmed by a person
--   documents, pieces, links   the project record; each document has a visibility
--   changes            sub change requests and GC/CM change proposals; requests roll up into a proposal
--   events             append-only log of every action, including what the AI drafted and what it cited
--   schedule_versions  baseline and updates; an update can name the changes that caused it
--   sov_lines          schedule of values lines; time-based general conditions give the cost per day
--   field_links, field_submissions   a no-account link for foremen; submissions arrive unverified
--
-- Visibility (enforced here by row-level security, mirrored in assets/visibility.js for the in-browser sample)
--   documents: 'project' = every company on the project; 'contract' = the two parties to that contract; 'company' = the author only
--   changes:   the company that raised it, and the company it was sent to once it's no longer a draft;
--              owner and architect also see GC/CM proposals once submitted; sub requests stay between the sub and the GC/CM
--   contracts: their two parties; the prime contract is visible to everyone on the project (its terms flow down)
--   schedule of values: the parties to its contract

-- ---------- clear the old model (and this one, so the file can be re-run) ----------
drop table if exists field_submissions, field_links, sov_lines, schedule_versions, events, changes, links, pieces,
  documents, contract_terms, contracts, invites, project_companies, projects, company_people, companies, threads, members cascade;
drop type if exists company_kind, contract_type, contract_kind, visibility, change_tier, change_status cascade;
drop function if exists is_member(uuid), my_party(uuid), is_admin(uuid), add_creator(), advance_thread(),
  claim_invites(), project_people(uuid) cascade;
drop type if exists party, doc_kind, doc_source, thread_status, event_kind cascade;
drop function if exists my_companies(uuid), is_project_admin(uuid), in_company(uuid), project_role_of(uuid, uuid), my_roles(uuid),
  start_project(text, contract_type, text, company_kind, boolean), add_sample_company(uuid, text, company_kind, text),
  can_see_contract(uuid), can_see_doc(uuid), can_see_change(uuid), before_event(), after_event(),
  submit_field(text, text, text, text[]), field_link_info(text), storage_path_member(text), storage_field_ok(text, boolean) cascade;

create extension if not exists pgcrypto;

create type company_kind as enum ('owner', 'architect', 'gc', 'sub');
create type contract_type as enum ('gccm', 'hard_bid', 'design_build');
create type contract_kind as enum ('prime', 'design', 'sub');
create type doc_kind as enum ('contract', 'spec', 'drawing_index', 'rfi', 'asi', 'submittal', 'schedule', 'daily_report', 'minutes', 'change_order', 'notice', 'other');
create type doc_source as enum ('upload', 'procore', 'synthetic', 'field');
create type visibility as enum ('project', 'contract', 'company');
create type change_tier as enum ('sub_request', 'proposal');
create type change_status as enum ('draft', 'with_gc', 'with_architect', 'with_owner', 'returned', 'bundled', 'approved', 'rejected', 'withdrawn');
create type event_kind as enum ('note', 'draft', 'confirm', 'check', 'explain', 'submit', 'forward', 'return', 'approve', 'reject', 'comment', 'bundle', 'notice', 'schedule', 'link');

-- ---------- companies and people ----------
create table companies (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  kind        company_kind not null,
  trade       text,
  synthetic   boolean not null default false,
  created_by  uuid references auth.users default auth.uid(),
  created_at  timestamptz not null default now()
);
create table company_people (
  company_id  uuid not null references companies on delete cascade,
  user_id     uuid not null references auth.users on delete cascade,
  is_admin    boolean not null default false,
  primary key (company_id, user_id)
);

-- ---------- projects ----------
create table projects (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  contract_type contract_type not null default 'gccm',
  synthetic     boolean not null default false,
  created_by    uuid references auth.users default auth.uid(),
  created_at    timestamptz not null default now()
);
create table project_companies (
  project_id  uuid not null references projects on delete cascade,
  company_id  uuid not null references companies on delete cascade,
  role        company_kind not null,
  is_admin    boolean not null default false,   -- this company runs the project setup (usually the GC/CM)
  primary key (project_id, company_id)
);
create table invites (
  project_id    uuid not null references projects on delete cascade,
  email         text not null,
  company_name  text not null,
  role          company_kind not null,
  invited_by    uuid references auth.users default auth.uid(),
  created_at    timestamptz not null default now(),
  primary key (project_id, email)
);

-- ---------- membership helpers (security definer so policies can call them without recursion) ----------
create function my_companies(p uuid) returns setof uuid
language sql stable security definer set search_path = public as $$
  select pc.company_id from project_companies pc join company_people cp on cp.company_id = pc.company_id
  where pc.project_id = p and cp.user_id = auth.uid();
$$;
create function is_member(p uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from my_companies(p));
$$;
create function is_project_admin(p uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from project_companies pc join company_people cp on cp.company_id = pc.company_id
                 where pc.project_id = p and pc.is_admin and cp.user_id = auth.uid())
      or exists (select 1 from projects where id = p and created_by = auth.uid());
$$;
create function in_company(c uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from company_people where company_id = c and user_id = auth.uid());
$$;
create function project_role_of(p uuid, c uuid) returns company_kind
language sql stable security definer set search_path = public as $$
  select role from project_companies where project_id = p and company_id = c;
$$;
create function my_roles(p uuid) returns setof company_kind
language sql stable security definer set search_path = public as $$
  select pc.role from project_companies pc join company_people cp on cp.company_id = pc.company_id
  where pc.project_id = p and cp.user_id = auth.uid();
$$;

-- Whoever creates a project gets a company for it (named by the app) and runs its setup.
-- The app calls start_project(name, type, company_name, role) instead of inserting directly.
create function start_project(p_name text, p_type contract_type, p_company text, p_role company_kind, p_synthetic boolean default false)
returns uuid language plpgsql security definer set search_path = public as $$
declare pid uuid; cid uuid;
begin
  if auth.uid() is null then raise exception 'Sign in first.'; end if;
  insert into projects (name, contract_type, synthetic) values (p_name, p_type, p_synthetic) returning id into pid;
  select c.id into cid from companies c join company_people cp on cp.company_id = c.id
    where cp.user_id = auth.uid() and lower(c.name) = lower(p_company) and c.kind = p_role limit 1;
  if cid is null then
    insert into companies (name, kind, synthetic) values (p_company, p_role, p_synthetic) returning id into cid;
    insert into company_people (company_id, user_id, is_admin) values (cid, auth.uid(), true);
  end if;
  insert into project_companies (project_id, company_id, role, is_admin) values (pid, cid, p_role, true);
  return pid;
end $$;
grant execute on function start_project(text, contract_type, text, company_kind, boolean) to authenticated;

-- A synthetic sample: the admin may add made-up companies and belongs to all of them,
-- so one person can walk a change through every party. The app then filters by "Viewing as" with the same rules.
create function add_sample_company(p uuid, p_name text, p_kind company_kind, p_trade text default null)
returns uuid language plpgsql security definer set search_path = public as $$
declare cid uuid;
begin
  if not exists (select 1 from projects where id = p and synthetic) then raise exception 'Only on a synthetic project.'; end if;
  if not is_project_admin(p) then raise exception 'Only the project admin can do this.'; end if;
  insert into companies (name, kind, trade, synthetic) values (p_name, p_kind, p_trade, true) returning id into cid;
  insert into company_people (company_id, user_id, is_admin) values (cid, auth.uid(), true);
  insert into project_companies (project_id, company_id, role) values (p, cid, p_kind);
  return cid;
end $$;
grant execute on function add_sample_company(uuid, text, company_kind, text) to authenticated;

-- Invites: when the invited person signs in, they join (creating their company if needed).
create function claim_invites() returns int
language plpgsql security definer set search_path = public as $$
declare r record; cid uuid; n int := 0; mail text := lower(auth.jwt() ->> 'email');
begin
  for r in select * from invites where lower(email) = mail loop
    select c.id into cid from companies c join company_people cp on cp.company_id = c.id
      where cp.user_id = auth.uid() and lower(c.name) = lower(r.company_name) limit 1;
    if cid is null then
      insert into companies (name, kind) values (r.company_name, r.role) returning id into cid;
      insert into company_people (company_id, user_id, is_admin) values (cid, auth.uid(), true);
    end if;
    insert into project_companies (project_id, company_id, role) values (r.project_id, cid, r.role) on conflict do nothing;
    n := n + 1;
  end loop;
  delete from invites where lower(email) = mail;
  return n;
end $$;
grant execute on function claim_invites() to authenticated;

-- People on a project, with their company (to show who did what).
create function project_people(p uuid) returns table (user_id uuid, email text, company_id uuid, company text, role company_kind)
language sql stable security definer set search_path = public as $$
  select cp.user_id, u.email::text, c.id, c.name, pc.role
  from project_companies pc join companies c on c.id = pc.company_id
  join company_people cp on cp.company_id = c.id join auth.users u on u.id = cp.user_id
  where pc.project_id = p and is_member(p);
$$;
grant execute on function project_people(uuid) to authenticated;

-- ---------- contracts ----------
create table contracts (
  id            uuid primary key default gen_random_uuid(),
  project_id    uuid not null references projects on delete cascade,
  kind          contract_kind not null,
  up_company    uuid not null references companies,   -- the party that pays (owner, or the GC/CM on a subcontract)
  down_company  uuid not null references companies,   -- the party that performs
  parent_id     uuid references contracts on delete set null,  -- a subcontract's prime contract (flow-down)
  title         text not null,
  document_id   uuid,                                 -- the contract document in the record, set after import
  meta          jsonb not null default '{}',
  created_at    timestamptz not null default now()
);
create table contract_terms (
  id            uuid primary key default gen_random_uuid(),
  project_id    uuid not null references projects on delete cascade,
  contract_id   uuid not null references contracts on delete cascade,
  key           text not null,          -- notice_days, markup_own, fee_pct, delay_rate ...
  value         jsonb,
  clause        text,                   -- § 6.2
  sentence      text,                   -- the exact sentence the value came from
  confirmed_by  uuid references auth.users,
  confirmed_at  timestamptz,
  unique (contract_id, key)
);

create function can_see_contract(k uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from contracts c where c.id = k and is_member(c.project_id) and (
    c.kind = 'prime' or in_company(c.up_company) or in_company(c.down_company)));
$$;

-- ---------- the record ----------
create table documents (
  id             uuid primary key default gen_random_uuid(),
  project_id     uuid not null references projects on delete cascade,
  kind           doc_kind not null,
  number         text,
  title          text not null,
  issued_on      date,
  author_company uuid references companies,
  visibility     visibility not null default 'project',
  contract_id    uuid references contracts on delete set null,   -- for visibility 'contract'
  source         doc_source not null default 'upload',
  external_id    text,
  file_path      text,
  meta           jsonb not null default '{}',
  created_by     uuid references auth.users default auth.uid(),
  created_at     timestamptz not null default now(),
  unique (project_id, source, external_id)
);
alter table contracts add foreign key (document_id) references documents on delete set null;

create function can_see_doc(d uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from documents x where x.id = d and is_member(x.project_id) and (
    x.visibility = 'project'
    or (x.visibility = 'company' and in_company(x.author_company))
    or (x.visibility = 'contract' and exists (select 1 from contracts c where c.id = x.contract_id
          and (in_company(c.up_company) or in_company(c.down_company))))));
$$;

create table pieces (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects on delete cascade,
  document_id  uuid not null references documents on delete cascade,
  ordinal      int not null,
  section      text,
  body         text not null,
  piece_date   date,
  company_id   uuid references companies,
  meta         jsonb not null default '{}',
  search       tsvector generated always as (to_tsvector('english', coalesce(section, '') || ' ' || body)) stored
);
create index pieces_search on pieces using gin (search);
create index pieces_doc on pieces (document_id, ordinal);

create table links (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects on delete cascade,
  from_doc     uuid references documents on delete cascade,
  from_piece   uuid references pieces on delete cascade,
  to_doc       uuid references documents on delete cascade,
  to_piece     uuid references pieces on delete cascade,
  relation     text not null,
  created_by   uuid references auth.users default auth.uid(),
  created_at   timestamptz not null default now(),
  check (coalesce(from_doc, from_piece) is not null and coalesce(to_doc, to_piece) is not null)
);

-- ---------- changes ----------
create table changes (
  id            uuid primary key default gen_random_uuid(),
  project_id    uuid not null references projects on delete cascade,
  number        text not null,          -- CP-0212 for a proposal, CR-... for a sub request
  title         text not null,
  tier          change_tier not null,
  contract_id   uuid references contracts,   -- the contract it is priced under
  from_company  uuid not null references companies,
  to_company    uuid not null references companies,
  parent_id     uuid references changes on delete set null,   -- a sub request's proposal
  status        change_status not null default 'draft',
  holder        uuid references companies,
  amount        numeric(14, 2),
  days          int,
  cause         jsonb not null default '{}',   -- {type, reference, event_date}
  document_id   uuid references documents on delete set null,
  meta          jsonb not null default '{}',
  created_by    uuid references auth.users default auth.uid(),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (project_id, number)
);

create function can_see_change(x uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from changes c where c.id = x and is_member(c.project_id) and (
    in_company(c.from_company)
    or (c.status <> 'draft' and in_company(c.to_company))
    or (c.tier = 'proposal' and c.status <> 'draft' and exists (
          select 1 from my_roles(c.project_id) r where r in ('owner', 'architect')))));
$$;

-- ---------- the activity log ----------
create table events (
  id           bigint generated always as identity primary key,
  project_id   uuid not null references projects on delete cascade,
  change_id    uuid references changes on delete cascade,   -- null for project-level actions (uploads, schedule updates)
  company_id   uuid not null references companies,
  actor        uuid references auth.users default auth.uid(),
  kind         event_kind not null,
  body         text,
  reason       text,                    -- a return's reason code
  payload      jsonb not null default '{}',
  ai           jsonb,                   -- when the AI drafted it: {model, where, inputs:[ids], citations:[ids], output, saved_run, edited}
  created_at   timestamptz not null default now()
);
create index events_change on events (change_id, id);
create index events_project on events (project_id, id);

-- Moving a change along, and the rule that a GC/CM proposal can't go up until the checks have run
-- and every finding is fixed or explained.
create function before_event() returns trigger
language plpgsql security definer set search_path = public as $$
declare c changes; last_draft bigint; last_check events; explained int;
begin
  if new.change_id is null then return new; end if;
  select * into c from changes where id = new.change_id;
  if new.kind = 'submit' and c.tier = 'proposal' then
    select max(id) into last_draft from events where change_id = c.id and kind in ('draft', 'confirm');
    select * into last_check from events where change_id = c.id and kind = 'check' and id > coalesce(last_draft, 0)
      order by id desc limit 1;
    if last_check.id is null then raise exception 'Run the contract checks before sending this up.'; end if;
    select count(*) into explained from events where change_id = c.id and kind = 'explain' and id > last_check.id;
    if coalesce((last_check.payload ->> 'findings')::int, 0) > 0 and explained = 0 then
      raise exception 'Fix or explain each finding before sending.';
    end if;
  end if;
  return new;
end $$;
create trigger events_before before insert on events for each row execute function before_event();

create function after_event() returns trigger
language plpgsql security definer set search_path = public as $$
declare c changes; arch uuid;
begin
  if new.change_id is null then return new; end if;
  select * into c from changes where id = new.change_id;
  select company_id into arch from project_companies where project_id = c.project_id and role = 'architect' limit 1;
  if c.tier = 'sub_request' then
    update changes set updated_at = now(),
      status = case new.kind when 'submit' then 'with_gc' when 'return' then 'returned'
                             when 'bundle' then 'bundled' else status end::change_status,
      holder = case new.kind when 'submit' then to_company when 'return' then from_company else holder end
    where id = c.id;
  else
    update changes set updated_at = now(),
      status = case
        when new.kind = 'submit' then (case when arch is null then 'with_owner' else 'with_architect' end)
        when new.kind = 'forward' then 'with_owner'
        when new.kind = 'return' and c.status = 'with_owner' and arch is not null then 'with_architect'
        when new.kind = 'return' then 'returned'
        when new.kind = 'approve' then 'approved'
        when new.kind = 'reject' then 'rejected'
        else status::text end::change_status,
      holder = case
        when new.kind = 'submit' then coalesce(arch, to_company)
        when new.kind = 'forward' then to_company
        when new.kind = 'return' and c.status = 'with_owner' and arch is not null then arch
        when new.kind = 'return' then from_company
        else holder end
    where id = c.id;
    -- An owner decision flows back down to every sub request in the proposal.
    if new.kind in ('approve', 'reject') then
      update changes set status = (case new.kind when 'approve' then 'approved' else 'rejected' end)::change_status,
        holder = null, updated_at = now() where parent_id = c.id;
    end if;
  end if;
  return new;
end $$;
create trigger events_after after insert on events for each row execute function after_event();

-- ---------- schedule and money ----------
create table schedule_versions (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects on delete cascade,
  label        text not null,
  data_date    date,
  data         jsonb not null,          -- activities, relationships, calendar (same shape the app reads)
  caused_by    text[] not null default '{}',   -- change numbers that this update absorbs
  is_baseline  boolean not null default false,
  accepted_by  uuid references auth.users default auth.uid(),
  created_at   timestamptz not null default now()
);
create table sov_lines (
  id                 uuid primary key default gen_random_uuid(),
  project_id         uuid not null references projects on delete cascade,
  contract_id        uuid not null references contracts on delete cascade,
  code               text,
  description        text not null,
  amount             numeric(14, 2) not null,
  general_conditions boolean not null default false,
  basis              text                 -- 'time' for time-based general conditions
);

-- ---------- field links (no account) ----------
create table field_links (
  token        text primary key default encode(gen_random_bytes(18), 'hex'),
  project_id   uuid not null references projects on delete cascade,
  company_id   uuid not null references companies on delete cascade,   -- the sub whose PM receives it
  active       boolean not null default true,
  created_by   uuid references auth.users default auth.uid(),
  created_at   timestamptz not null default now()
);
create table field_submissions (
  id           uuid primary key default gen_random_uuid(),
  token        text not null references field_links on delete cascade,
  project_id   uuid not null references projects on delete cascade,
  company_id   uuid not null references companies on delete cascade,
  body         text not null check (length(body) between 3 and 4000),
  sender_name  text check (length(sender_name) <= 80),
  photos       text[] not null default '{}',
  status       text not null default 'unverified' check (status in ('unverified', 'confirmed', 'discarded')),
  change_id    uuid references changes on delete set null,
  created_at   timestamptz not null default now()
);

-- The only thing a field link can do: add one unverified submission. It can't read anything.
create function submit_field(p_token text, p_body text, p_name text, p_photos text[] default '{}')
returns uuid language plpgsql security definer set search_path = public as $$
declare l field_links; sid uuid; recent int;
begin
  select * into l from field_links where token = p_token and active;
  if l.token is null then raise exception 'This link is no longer active.'; end if;
  select count(*) into recent from field_submissions where token = p_token and created_at > now() - interval '1 hour';
  if recent >= 30 then raise exception 'Too many submissions from this link in the last hour. Try again later.'; end if;
  insert into field_submissions (token, project_id, company_id, body, sender_name, photos)
    values (p_token, l.project_id, l.company_id, p_body, nullif(trim(p_name), ''), coalesce(p_photos, '{}'))
    returning id into sid;
  insert into events (project_id, company_id, actor, kind, body, payload)
    values (l.project_id, l.company_id, null, 'note', 'Field submission received (unverified)', jsonb_build_object('field_submission', sid));
  return sid;
end $$;
grant execute on function submit_field(text, text, text, text[]) to anon, authenticated;

-- What the field page shows before sending: the project and company names only.
create function field_link_info(p_token text) returns table (project text, company text)
language sql stable security definer set search_path = public as $$
  select p.name, c.name from field_links l join projects p on p.id = l.project_id join companies c on c.id = l.company_id
  where l.token = p_token and l.active;
$$;
grant execute on function field_link_info(text) to anon, authenticated;

-- ---------- row-level security ----------
alter table companies          enable row level security;
alter table company_people     enable row level security;
alter table projects           enable row level security;
alter table project_companies  enable row level security;
alter table invites            enable row level security;
alter table contracts          enable row level security;
alter table contract_terms     enable row level security;
alter table documents          enable row level security;
alter table pieces             enable row level security;
alter table links              enable row level security;
alter table changes            enable row level security;
alter table events             enable row level security;
alter table schedule_versions  enable row level security;
alter table sov_lines          enable row level security;
alter table field_links        enable row level security;
alter table field_submissions  enable row level security;

-- Companies: you see your own, and every company on a project you're on.
create policy co_read on companies for select using (
  in_company(id) or exists (select 1 from project_companies pc where pc.company_id = id and is_member(pc.project_id)));
create policy co_edit on companies for update using (
  exists (select 1 from company_people where company_id = id and user_id = auth.uid() and is_admin));
create policy cp_read on company_people for select using (in_company(company_id));
create policy cp_add on company_people for insert with check (
  exists (select 1 from company_people x where x.company_id = company_id and x.user_id = auth.uid() and x.is_admin));

create policy p_read on projects for select using (is_member(id) or created_by = auth.uid());
create policy p_edit on projects for update using (is_project_admin(id));
create policy p_del on projects for delete using (is_project_admin(id));

create policy pc_read on project_companies for select using (is_member(project_id));
create policy pc_edit on project_companies for update using (is_project_admin(project_id));
create policy pc_del on project_companies for delete using (is_project_admin(project_id));

create policy i_read on invites for select using (is_project_admin(project_id) or lower(email) = lower(auth.jwt() ->> 'email'));
create policy i_add on invites for insert with check (is_project_admin(project_id));
create policy i_del on invites for delete using (is_project_admin(project_id));

create policy k_read on contracts for select using (can_see_contract(id));
create policy k_add on contracts for insert with check (is_project_admin(project_id));
create policy k_edit on contracts for update using (is_project_admin(project_id));
create policy kt_read on contract_terms for select using (can_see_contract(contract_id));
create policy kt_add on contract_terms for insert with check (can_see_contract(contract_id) and is_member(project_id));
create policy kt_edit on contract_terms for update using (can_see_contract(contract_id) and is_member(project_id));

create policy d_read on documents for select using (can_see_doc(id));
create policy d_add on documents for insert with check (is_member(project_id) and (author_company is null or in_company(author_company)));
create policy d_edit on documents for update using (is_project_admin(project_id) or created_by = auth.uid());
create policy d_del on documents for delete using (is_project_admin(project_id));

create policy pc2_read on pieces for select using (can_see_doc(document_id));
create policy pc2_add on pieces for insert with check (is_member(project_id));
create policy pc2_del on pieces for delete using (is_project_admin(project_id));

create policy l_read on links for select using (is_member(project_id));
create policy l_add on links for insert with check (is_member(project_id));
create policy l_del on links for delete using (is_project_admin(project_id));

create policy ch_read on changes for select using (can_see_change(id));
create policy ch_add on changes for insert with check (is_member(project_id) and in_company(from_company));
-- Changes move only through events (the triggers), except linking a request into a proposal and editing a draft's numbers.
create policy ch_edit on changes for update using (in_company(from_company) or in_company(to_company));

-- Events: append-only (no update or delete policy), and you speak only for a company you belong to.
create policy e_read on events for select using (
  is_member(project_id) and (change_id is null or can_see_change(change_id)));
create policy e_add on events for insert with check (
  is_member(project_id) and actor = auth.uid() and in_company(company_id));

create policy sv_read on schedule_versions for select using (is_member(project_id));
create policy sv_add on schedule_versions for insert with check (is_member(project_id));

create policy sov_read on sov_lines for select using (
  exists (select 1 from contracts c where c.id = contract_id and is_member(c.project_id) and (in_company(c.up_company) or in_company(c.down_company))));
create policy sov_add on sov_lines for insert with check (is_project_admin(project_id));

create policy fl_read on field_links for select using (in_company(company_id) or is_project_admin(project_id));
create policy fl_add on field_links for insert with check (in_company(company_id) or is_project_admin(project_id));
create policy fl_edit on field_links for update using (in_company(company_id) or is_project_admin(project_id));
create policy fs_read on field_submissions for select using (in_company(company_id));
create policy fs_edit on field_submissions for update using (in_company(company_id));

-- ---------- file storage ----------
-- Files live under <project_id>/... ; field photos under field/<token>/... (checked without casting a non-uuid).
create function storage_path_member(path text) returns boolean
language plpgsql stable security definer set search_path = public as $$
declare head text := split_part(path, '/', 1);
begin
  if head !~ '^[0-9a-f-]{36}$' then return false; end if;
  return is_member(head::uuid);
end $$;
create function storage_field_ok(path text, reading boolean) returns boolean
language sql stable security definer set search_path = public as $$
  select split_part(path, '/', 1) = 'field' and exists (
    select 1 from field_links l where l.token = split_part(path, '/', 2) and l.active and (not reading or in_company(l.company_id)));
$$;
grant execute on function storage_field_ok(text, boolean) to anon, authenticated;
insert into storage.buckets (id, name, public) values ('documents', 'documents', false) on conflict (id) do nothing;
drop policy if exists s_read on storage.objects;
create policy s_read on storage.objects for select using (bucket_id = 'documents' and (storage_path_member(name) or storage_field_ok(name, true)));
drop policy if exists s_add on storage.objects;
create policy s_add on storage.objects for insert with check (bucket_id = 'documents' and storage_path_member(name));
drop policy if exists s_field_add on storage.objects;
create policy s_field_add on storage.objects for insert to anon, authenticated with check (bucket_id = 'documents' and storage_field_ok(name, false));
drop policy if exists s_field_read on storage.objects;
