-- Read-only: run in the actual project's SQL Editor before reviewing migrations.
-- No user rows, keys, credentials, or tokens are selected.
select n.nspname as schema_name, c.relname as table_name,
       c.relrowsecurity as rls_enabled, c.relforcerowsecurity as rls_forced
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind in ('r','p')
order by c.relname;

select schemaname, tablename, policyname, permissive, roles, cmd,
       qual as using_expression, with_check
from pg_policies where schemaname = 'public'
order by tablename, policyname;

select table_schema, table_name, grantee, privilege_type
from information_schema.table_privileges
where table_schema = 'public' and grantee in ('anon','authenticated','PUBLIC')
order by table_name, grantee, privilege_type;

-- Find every user-linked table, including tables absent from repository migrations.
select con.conrelid::regclass as user_linked_table,
       a.attname as ownership_candidate, pg_get_constraintdef(con.oid) as foreign_key
from pg_constraint con
join pg_attribute a on a.attrelid = con.conrelid and a.attnum = any(con.conkey)
where con.contype = 'f' and con.confrelid = 'auth.users'::regclass
order by 1, 2;

-- Also inventory conventionally named ownership fields without FK constraints.
select table_schema, table_name, column_name
from information_schema.columns
where table_schema = 'public' and column_name in ('user_id','owner_id','profile_id','created_by')
order by table_name, column_name;
