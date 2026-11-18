-- Row-level security test for 0003_platform.sql. Runs on a local Postgres with stub auth (see README in this folder).
-- Each block acts as one person and checks what they can and can't see or do.
\set ON_ERROR_STOP 1
insert into auth.users values
 ('00000000-0000-0000-0000-00000000000a','gc@x.test'), ('00000000-0000-0000-0000-00000000000b','own@x.test'),
 ('00000000-0000-0000-0000-00000000000c','arch@x.test'), ('00000000-0000-0000-0000-00000000000d','suba@x.test'),
 ('00000000-0000-0000-0000-00000000000e','subb@x.test'), ('00000000-0000-0000-0000-00000000000f','stranger@x.test');
grant usage on schema public to authenticated, anon;
grant all on all tables in schema public to authenticated;
grant execute on all functions in schema public to authenticated;
create temp table ids (k text primary key, v uuid);
grant all on ids to authenticated;

create or replace function pg_temp.as_user(u text, mail text) returns void language plpgsql as $$
begin perform set_config('request.jwt.sub', u, false); perform set_config('request.jwt.email', mail, false); end $$;
create or replace function pg_temp.ok(cond boolean, what text) returns void language plpgsql as $$
begin if not cond then raise exception 'FAILED: %', what; end if; raise notice 'ok: %', what; end $$;

set role authenticated;
-- GC/CM starts the project and invites the others
select pg_temp.as_user('00000000-0000-0000-0000-00000000000a','gc@x.test');
insert into ids select 'p', start_project('Test HS', 'gccm', 'Acme Builders', 'gc');
insert into invites (project_id, email, company_name, role) select v, e, c, r::company_kind from ids,
  (values ('own@x.test','District','owner'),('arch@x.test','Arch Co','architect'),('suba@x.test','Sub A','sub'),('subb@x.test','Sub B','sub')) t(e,c,r) where k='p';
select pg_temp.as_user('00000000-0000-0000-0000-00000000000b','own@x.test'); select claim_invites();
select pg_temp.as_user('00000000-0000-0000-0000-00000000000c','arch@x.test'); select claim_invites();
select pg_temp.as_user('00000000-0000-0000-0000-00000000000d','suba@x.test'); select claim_invites();
select pg_temp.as_user('00000000-0000-0000-0000-00000000000e','subb@x.test'); select claim_invites();

-- company ids
select pg_temp.as_user('00000000-0000-0000-0000-00000000000a','gc@x.test');
insert into ids select 'gc', company_id from project_companies where role='gc';
insert into ids select 'own', company_id from project_companies where role='owner';
insert into ids select 'arch', company_id from project_companies where role='architect';
insert into ids select 'sa', c.id from companies c where c.name='Sub A';
insert into ids select 'sb', c.id from companies c where c.name='Sub B';
select pg_temp.ok((select count(*) from ids) = 6, 'GC sees every company on the project');

-- contracts: prime, design, two subcontracts
insert into contracts (project_id, kind, up_company, down_company, title) select (select v from ids where k='p'), 'prime', (select v from ids where k='own'), (select v from ids where k='gc'), 'Prime';
insert into ids select 'kp', id from contracts where kind='prime';
insert into contracts (project_id, kind, up_company, down_company, parent_id, title) select (select v from ids where k='p'), 'sub', (select v from ids where k='gc'), (select v from ids where k='sa'), (select v from ids where k='kp'), 'Sub A subcontract';
insert into contracts (project_id, kind, up_company, down_company, parent_id, title) select (select v from ids where k='p'), 'sub', (select v from ids where k='gc'), (select v from ids where k='sb'), (select v from ids where k='kp'), 'Sub B subcontract';
insert into ids select 'ka', id from contracts where title='Sub A subcontract';
insert into ids select 'kb', id from contracts where title='Sub B subcontract';
insert into sov_lines (project_id, contract_id, description, amount, general_conditions, basis) select (select v from ids where k='p'), (select v from ids where k='kp'), 'Superintendent', 100000, true, 'time';
-- documents with each visibility
insert into documents (project_id, kind, title, visibility) select v, 'rfi', 'RFI-1', 'project' from ids where k='p';
insert into documents (project_id, kind, title, visibility, contract_id, author_company) select (select v from ids where k='p'), 'contract', 'Sub A subcontract text', 'contract', (select v from ids where k='ka'), (select v from ids where k='gc');
insert into documents (project_id, kind, title, visibility, author_company) select (select v from ids where k='p'), 'other', 'GC internal estimate', 'company', (select v from ids where k='gc');

-- Sub A raises a request and sends it; Sub B keeps one as a draft
select pg_temp.as_user('00000000-0000-0000-0000-00000000000d','suba@x.test');
insert into changes (project_id, number, title, tier, contract_id, from_company, to_company, amount)
  select (select v from ids where k='p'), 'CR-A1', 'Extra drains', 'sub_request', (select v from ids where k='ka'), (select v from ids where k='sa'), (select v from ids where k='gc'), 6567;
insert into ids select 'ra', id from changes where number='CR-A1';
insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='ra'), (select v from ids where k='sa'), auth.uid(), 'submit';
select pg_temp.ok((select status from changes where number='CR-A1') = 'with_gc', 'submit moves a sub request to the GC/CM');
select pg_temp.as_user('00000000-0000-0000-0000-00000000000e','subb@x.test');
insert into changes (project_id, number, title, tier, contract_id, from_company, to_company, amount)
  select (select v from ids where k='p'), 'CR-B1', 'Draft only', 'sub_request', (select v from ids where k='kb'), (select v from ids where k='sb'), (select v from ids where k='gc'), 999;

-- What each party sees
select pg_temp.as_user('00000000-0000-0000-0000-00000000000d','suba@x.test');
select pg_temp.ok((select count(*) from changes) = 1, 'Sub A sees only its own request');
select pg_temp.ok((select count(*) from documents) = 2, 'Sub A sees the RFI and its own subcontract, not the GC estimate');
select pg_temp.ok((select count(*) from contracts) = 2, 'Sub A sees the prime contract and its own subcontract, not Sub B''s');
select pg_temp.ok((select count(*) from sov_lines) = 0, 'Sub A cannot see the prime schedule of values');
select pg_temp.as_user('00000000-0000-0000-0000-00000000000e','subb@x.test');
select pg_temp.ok((select count(*) from changes) = 1 and (select number from changes) = 'CR-B1', 'Sub B sees only its own draft');
select pg_temp.as_user('00000000-0000-0000-0000-00000000000a','gc@x.test');
select pg_temp.ok((select count(*) from changes) = 1, 'GC/CM sees the submitted request, not Sub B''s draft');
select pg_temp.ok((select count(*) from documents) = 3, 'GC/CM sees all three documents');
select pg_temp.ok((select count(*) from sov_lines) = 1, 'GC/CM sees the prime schedule of values');

-- GC/CM makes a proposal, bundles the request, and tries to send without checks
insert into changes (project_id, number, title, tier, contract_id, from_company, to_company, amount)
  select (select v from ids where k='p'), 'CP-1', 'Extra drains', 'proposal', (select v from ids where k='kp'), (select v from ids where k='gc'), (select v from ids where k='own'), 6895.35;
insert into ids select 'cp', id from changes where number='CP-1';
update changes set parent_id = (select v from ids where k='cp') where number='CR-A1';
insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='ra'), (select v from ids where k='gc'), auth.uid(), 'bundle';
insert into events (project_id, change_id, company_id, actor, kind, ai) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'draft', '{"model":"llama3.1:8b","citations":["FR-33"]}';
do $$ begin
  insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'submit';
  raise exception 'FAILED: send without checks was allowed';
exception when others then if sqlerrm like 'FAILED%' then raise; end if; raise notice 'ok: send is locked until the checks run (%)', sqlerrm; end $$;
insert into events (project_id, change_id, company_id, actor, kind, payload) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'check', '{"findings":1}';
do $$ begin
  insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'submit';
  raise exception 'FAILED: send with an unexplained finding was allowed';
exception when others then if sqlerrm like 'FAILED%' then raise; end if; raise notice 'ok: an open finding blocks sending (%)', sqlerrm; end $$;
insert into events (project_id, change_id, company_id, actor, kind, body) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'explain', 'NSS fee removed';
insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'submit';
select pg_temp.ok((select status from changes where number='CP-1') = 'with_architect', 'proposal goes to the architect');
do $$ begin
  update events set body = 'changed' where kind = 'submit';
  if found then raise exception 'FAILED: an event was edited'; end if; raise notice 'ok: events cannot be edited';
end $$;

select pg_temp.as_user('00000000-0000-0000-0000-00000000000b','own@x.test');
select pg_temp.ok((select count(*) from changes) = 1 and (select number from changes) = 'CP-1', 'Owner sees the proposal, not the sub request');
select pg_temp.ok((select count(*) from documents) = 1, 'Owner sees the RFI only');
select pg_temp.ok((select count(*) from events) = 4, 'Owner sees the proposal''s events only');
select pg_temp.as_user('00000000-0000-0000-0000-00000000000c','arch@x.test');
select pg_temp.ok((select count(*) from changes) = 1, 'Architect sees the proposal');
insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='arch'), auth.uid(), 'forward';
select pg_temp.as_user('00000000-0000-0000-0000-00000000000b','own@x.test');
do $$ begin
  insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'approve';
  raise exception 'FAILED: owner spoke for the GC/CM';
exception when others then if sqlerrm like 'FAILED%' then raise; end if; raise notice 'ok: you can only act for your own company'; end $$;
insert into events (project_id, change_id, company_id, actor, kind, reason) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='own'), auth.uid(), 'return', 'missing_backup';
select pg_temp.ok((select status from changes where number='CP-1') = 'with_architect', 'an owner return goes back one tier, to the architect');
select pg_temp.as_user('00000000-0000-0000-0000-00000000000c','arch@x.test');
insert into events (project_id, change_id, company_id, actor, kind, reason) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='arch'), auth.uid(), 'return', 'missing_backup';
select pg_temp.as_user('00000000-0000-0000-0000-00000000000a','gc@x.test');
select pg_temp.ok((select status from changes where number='CP-1') = 'returned', 'an architect return goes back to the GC/CM');
insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'confirm';
do $$ begin
  insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'submit';
  raise exception 'FAILED: resend without new checks was allowed';
exception when others then if sqlerrm like 'FAILED%' then raise; end if; raise notice 'ok: after a new confirmation, the checks must run again'; end $$;
insert into events (project_id, change_id, company_id, actor, kind, payload) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'check', '{"findings":0}';
insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='gc'), auth.uid(), 'submit';
select pg_temp.as_user('00000000-0000-0000-0000-00000000000c','arch@x.test');
insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='arch'), auth.uid(), 'forward';
select pg_temp.as_user('00000000-0000-0000-0000-00000000000b','own@x.test');
insert into events (project_id, change_id, company_id, actor, kind) select (select v from ids where k='p'), (select v from ids where k='cp'), (select v from ids where k='own'), auth.uid(), 'approve';
select pg_temp.as_user('00000000-0000-0000-0000-00000000000d','suba@x.test');
select pg_temp.ok((select status from changes where number='CR-A1') = 'approved', 'owner approval flows down to Sub A''s request');

-- A stranger sees nothing
select pg_temp.as_user('00000000-0000-0000-0000-00000000000f','stranger@x.test');
select pg_temp.ok((select count(*) from projects) + (select count(*) from changes) + (select count(*) from documents) = 0, 'a stranger sees nothing');

-- Field link: anyone with the token can add one unverified submission and read nothing
select pg_temp.as_user('00000000-0000-0000-0000-00000000000d','suba@x.test');
insert into field_links (project_id, company_id) select (select v from ids where k='p'), (select v from ids where k='sa');
insert into ids select 'tok', null; update ids set v = null where k='tok';
create temp table tok as select token from field_links; grant select on tok to anon;
reset role; set role anon; select pg_temp.as_user('', '');
select submit_field((select token from tok), 'Water coming in at the gym roof drain', 'Mo');
do $$ begin perform count(*) from field_submissions; raise exception 'FAILED: anon read submissions';
exception when insufficient_privilege then raise notice 'ok: a field link cannot read anything'; end $$;
do $$ begin perform submit_field('not-a-token', 'x x x', null); raise exception 'FAILED: bad token accepted';
exception when others then if sqlerrm like 'FAILED%' then raise; end if; raise notice 'ok: a bad token is refused'; end $$;
reset role; set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-00000000000d','suba@x.test');
select pg_temp.ok((select count(*) from field_submissions where status='unverified') = 1, 'Sub A sees the unverified submission');
select pg_temp.as_user('00000000-0000-0000-0000-00000000000a','gc@x.test');
select pg_temp.ok((select count(*) from field_submissions) = 0, 'the GC/CM does not see it until Sub A confirms it');
\echo ALL VISIBILITY TESTS PASSED
