-- Run after the migration using the database admin connection. Read-only assertions.
DO $$
DECLARE table_name text; role_name text; privilege_name text;
BEGIN
 FOREACH table_name IN ARRAY ARRAY['stores','store_inventory_versions','store_products'] LOOP
  IF NOT (SELECT relrowsecurity FROM pg_class WHERE oid=('public.'||table_name)::regclass) THEN
   RAISE EXCEPTION 'RLS missing on %',table_name;
  END IF;
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
   FOREACH privilege_name IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'] LOOP
    IF has_table_privilege(role_name,'public.'||table_name,privilege_name) THEN
     RAISE EXCEPTION 'Unexpected % permission for % on %',privilege_name,role_name,table_name;
    END IF;
   END LOOP;
   IF has_function_privilege(role_name,'public.activate_store_inventory(text,text)','EXECUTE') THEN
    RAISE EXCEPTION 'Unexpected inventory activation permission for %',role_name;
   END IF;
  END LOOP;
 END LOOP;
END $$;
