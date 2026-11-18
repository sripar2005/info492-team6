create schema auth; create table auth.users(id uuid primary key, email text);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.sub', true),'')::uuid $$;
create function auth.jwt() returns jsonb language sql stable as $$ select jsonb_build_object('email', current_setting('request.jwt.email', true)) $$;
create schema storage; create table storage.buckets(id text primary key, name text, public boolean);
create table storage.objects(id serial primary key, bucket_id text, name text); alter table storage.objects enable row level security;
do $$ begin create role authenticated; exception when duplicate_object then null; end $$; do $$ begin create role anon; exception when duplicate_object then null; end $$;
grant usage on schema auth, storage to authenticated, anon; grant select on auth.users to authenticated;
grant execute on all functions in schema auth to authenticated, anon;
