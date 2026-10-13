-- Execute only against an isolated Supabase test database after migrations.
-- This is a rollback-only adversarial DB test, NOT a claim of live validation.
begin;
insert into auth.users(id) values
 ('a0000000-0000-0000-0000-000000000001'),('b0000000-0000-0000-0000-000000000002');
insert into public.user_info(id,username) values ('a0000000-0000-0000-0000-000000000001','security_a'),('b0000000-0000-0000-0000-000000000002','security_b');
insert into public.user_pantry_items(user_id,name,quantity) values ('a0000000-0000-0000-0000-000000000001','owner fixture','1 item'),('b0000000-0000-0000-0000-000000000002','owner fixture','1 item');
insert into public.user_stores(user_id,store_key,name) values ('a0000000-0000-0000-0000-000000000001','owner_fixture','fixture'),('b0000000-0000-0000-0000-000000000002','owner_fixture','fixture');
insert into public.user_scheduled_meals(user_id,meal_name,scheduled_day,meal_data) values ('a0000000-0000-0000-0000-000000000001','fixture','Unscheduled','{}'),('b0000000-0000-0000-0000-000000000002','fixture','Unscheduled','{}');
insert into public.user_favorite_recipes(user_id,recipe_key,recipe_name,recipe_data) values ('a0000000-0000-0000-0000-000000000001','owner_fixture','fixture','{}'),('b0000000-0000-0000-0000-000000000002','owner_fixture','fixture','{}');
set local role authenticated;
select set_config('request.jwt.claim.sub','a0000000-0000-0000-0000-000000000001',true);
do $$
declare t text; owner_col text; n integer;
begin
 foreach t in array array['user_info','user_pantry_items','user_stores','user_scheduled_meals','user_favorite_recipes'] loop
  owner_col:=case when t='user_info' then 'id' else 'user_id' end;
  execute format('select count(*) from public.%I where %I = $1',t,owner_col) into n using 'b0000000-0000-0000-0000-000000000002'::uuid;
  if n<>0 then raise exception 'cross-user read allowed on %',t;end if;
  execute format('update public.%I set %I=%I where %I=$1',t,owner_col,owner_col,owner_col) using 'b0000000-0000-0000-0000-000000000002'::uuid;
  get diagnostics n=row_count;if n<>0 then raise exception 'cross-user update allowed on %',t;end if;
  execute format('delete from public.%I where %I=$1',t,owner_col) using 'b0000000-0000-0000-0000-000000000002'::uuid;
  get diagnostics n=row_count;if n<>0 then raise exception 'cross-user delete allowed on %',t;end if;
  if t<>'user_info' then
   begin
    execute format('update public.%I set user_id=$1 where user_id=$2',t) using 'b0000000-0000-0000-0000-000000000002'::uuid,'a0000000-0000-0000-0000-000000000001'::uuid;
    raise exception 'ownership reassignment allowed on %',t;
   exception when insufficient_privilege then null;end;
  end if;
 end loop;
 begin
  insert into public.user_pantry_items(user_id,name,quantity) values ('b0000000-0000-0000-0000-000000000002','spoofed','1 item');
  raise exception 'ownership insert spoof accepted';
 exception when insufficient_privilege then null;end;
end $$;
set local role anon;
do $$
begin
 begin
  perform * from public.user_pantry_items;
  raise exception 'anonymous private-table access accepted';
 exception when insufficient_privilege then null;end;
end $$;
rollback;
