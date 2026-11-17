-- ClauseStream, part 2: inviting people by email, and a demo rule for synthetic projects.
-- Run once in Supabase: SQL Editor -> New query -> paste -> Run. Safe to re-run.

-- Invites: an admin invites an email address as a party. When that person signs in, claim_invites() adds them.
create table if not exists invites (
  project_id  uuid not null references projects on delete cascade,
  email       text not null,
  party       party not null,
  is_admin    boolean not null default false,
  invited_by  uuid references auth.users default auth.uid(),
  created_at  timestamptz not null default now(),
  primary key (project_id, email)
);
alter table invites enable row level security;
drop policy if exists i_read on invites;  create policy i_read on invites for select using (is_member(project_id) or lower(email) = lower(auth.jwt() ->> 'email'));
drop policy if exists i_add on invites;   create policy i_add on invites for insert with check (is_admin(project_id));
drop policy if exists i_del on invites;   create policy i_del on invites for delete using (is_admin(project_id));

create or replace function claim_invites() returns int
language plpgsql security definer set search_path = public as $$
declare n int;
begin
  insert into members (project_id, user_id, party, is_admin)
    select project_id, auth.uid(), party, is_admin from invites where lower(email) = lower(auth.jwt() ->> 'email')
  on conflict (project_id, user_id) do nothing;
  get diagnostics n = row_count;
  delete from invites where lower(email) = lower(auth.jwt() ->> 'email');
  return n;
end $$;
grant execute on function claim_invites() to authenticated;

-- Members can see each other's emails on a shared project (to show who said what).
create or replace function project_people(p uuid) returns table (user_id uuid, email text, party party, is_admin boolean)
language sql stable security definer set search_path = public as $$
  select m.user_id, u.email::text, m.party, m.is_admin from members m join auth.users u on u.id = m.user_id
  where m.project_id = p and is_member(p);
$$;
grant execute on function project_people(uuid) to authenticated;

-- Demo rule: on a project marked synthetic, an admin may act for any party, so one person can walk a change
-- through sub, GC, architect and owner in a demo. Real projects keep the strict rule: you speak only for your party.
drop policy if exists e_add on events;
create policy e_add on events for insert with check (
  is_member(project_id) and actor = auth.uid() and (
    party = my_party(project_id)
    or (is_admin(project_id) and exists (select 1 from projects where id = project_id and synthetic))
  ));

-- Admins of a synthetic project may clear and re-import its record.
drop policy if exists d_del on documents; create policy d_del on documents for delete using (is_admin(project_id));
drop policy if exists l_del on links;     create policy l_del on links for delete using (is_admin(project_id));
drop policy if exists t_del on threads;   create policy t_del on threads for delete using (is_admin(project_id) and exists (select 1 from projects where id = project_id and synthetic));
