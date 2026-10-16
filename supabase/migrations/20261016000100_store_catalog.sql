-- Backend-only inventory. Apply with the Supabase SQL editor or psql admin connection.
BEGIN;
CREATE TABLE IF NOT EXISTS public.stores (
 id text PRIMARY KEY, retailer text NOT NULL, name text NOT NULL,
 address text, borough text, zip_code text, verified boolean NOT NULL DEFAULT false,
 active boolean NOT NULL DEFAULT false, metadata jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS public.store_inventory_versions (
 id text PRIMARY KEY, store_id text NOT NULL REFERENCES public.stores(id),
 scraped_at timestamptz, source_version text NOT NULL, product_count integer NOT NULL CHECK(product_count>=0),
 active boolean NOT NULL DEFAULT false, feature_version text NOT NULL,
 UNIQUE(store_id,source_version,feature_version), UNIQUE(store_id,id)
);
CREATE UNIQUE INDEX IF NOT EXISTS inventory_one_active ON public.store_inventory_versions(store_id) WHERE active;
CREATE TABLE IF NOT EXISTS public.store_products (
 id text PRIMARY KEY, store_id text NOT NULL REFERENCES public.stores(id),
 inventory_version_id text NOT NULL, source_product_id text NOT NULL,
 name text NOT NULL, normalized_name text NOT NULL, brand text, category text, subcategory text,
 family text, subfamily text, semantic_head text,
 price numeric, regular_price numeric, sale_price numeric, effective_current_price numeric,
 price_basis text, raw_size_text text, package_quantity numeric, package_unit text,
 availability jsonb, snap_eligible boolean, source_url text,
 feature_json jsonb NOT NULL, identity_json jsonb NOT NULL, source_json jsonb NOT NULL, source_position integer NOT NULL,
 FOREIGN KEY(store_id,inventory_version_id) REFERENCES public.store_inventory_versions(store_id,id),
 UNIQUE(store_id,inventory_version_id,source_product_id)
);
CREATE INDEX IF NOT EXISTS products_store_family ON public.store_products(store_id,inventory_version_id,family,source_position);
CREATE INDEX IF NOT EXISTS products_store_head ON public.store_products(store_id,inventory_version_id,semantic_head,source_position);
CREATE INDEX IF NOT EXISTS products_version ON public.store_products(inventory_version_id);
CREATE INDEX IF NOT EXISTS products_family ON public.store_products(family);
CREATE INDEX IF NOT EXISTS products_subfamily ON public.store_products(subfamily);
CREATE INDEX IF NOT EXISTS products_head ON public.store_products(semantic_head);
CREATE INDEX IF NOT EXISTS products_name ON public.store_products(normalized_name);
-- Recursive null-preserving merge for structural features/provenance as well as scalar fields.
CREATE OR REPLACE FUNCTION public.catalog_merge(old_value jsonb,new_value jsonb) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path=public,pg_temp AS $$
DECLARE result jsonb := coalesce(old_value,'{}'::jsonb); k text; v jsonb;
BEGIN
 IF jsonb_typeof(new_value) <> 'object' THEN RETURN coalesce(nullif(new_value,'null'::jsonb),old_value); END IF;
 IF jsonb_typeof(result) <> 'object' THEN result := '{}'::jsonb; END IF;
 FOR k,v IN SELECT * FROM jsonb_each(new_value) LOOP
  IF v <> 'null'::jsonb THEN
   result := jsonb_set(result,ARRAY[k], CASE WHEN jsonb_typeof(v)='object' THEN public.catalog_merge(result->k,v) ELSE v END,true);
  END IF;
 END LOOP;
 RETURN result;
END $$;
CREATE OR REPLACE FUNCTION public.catalog_preserve_rich_data() RETURNS trigger
LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
 NEW := jsonb_populate_record(NEW,public.catalog_merge(to_jsonb(OLD),to_jsonb(NEW)));
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS catalog_preserve_rich_data ON public.store_products;
CREATE TRIGGER catalog_preserve_rich_data BEFORE UPDATE ON public.store_products
 FOR EACH ROW EXECUTE FUNCTION public.catalog_preserve_rich_data();
DROP TRIGGER IF EXISTS catalog_preserve_rich_data ON public.stores;
CREATE TRIGGER catalog_preserve_rich_data BEFORE UPDATE ON public.stores
 FOR EACH ROW EXECUTE FUNCTION public.catalog_preserve_rich_data();
-- Activate only after a complete import; readers continue using the previous version until then.
CREATE OR REPLACE FUNCTION public.activate_store_inventory(target_store text,target_version text) RETURNS integer
LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
DECLARE expected integer; actual integer;
BEGIN
 PERFORM 1 FROM public.stores WHERE id=target_store AND verified FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Store is not verified'; END IF;
 SELECT product_count INTO expected FROM public.store_inventory_versions WHERE id=target_version AND store_id=target_store;
 SELECT count(*) INTO actual FROM public.store_products WHERE store_id=target_store AND inventory_version_id=target_version;
 IF expected IS NULL OR expected <> actual THEN RAISE EXCEPTION 'Inventory count mismatch'; END IF;
 UPDATE public.store_inventory_versions SET active=false WHERE store_id=target_store AND active AND id<>target_version;
 UPDATE public.store_inventory_versions SET active=true WHERE store_id=target_store AND id=target_version;
 UPDATE public.stores SET active=true WHERE id=target_store;
 RETURN actual;
END $$;
ALTER TABLE public.stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.store_inventory_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.store_products ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.stores,public.store_inventory_versions,public.store_products FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.stores,public.store_inventory_versions,public.store_products TO service_role;
REVOKE ALL ON FUNCTION public.catalog_merge(jsonb,jsonb),public.catalog_preserve_rich_data(),public.activate_store_inventory(text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.catalog_merge(jsonb,jsonb),public.catalog_preserve_rich_data(),public.activate_store_inventory(text,text) TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;
