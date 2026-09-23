BEGIN;

CREATE OR REPLACE FUNCTION public.towersignal_audit_company_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
  old_row jsonb;
  new_row jsonb;
  field_name text;
  old_value jsonb;
  new_value jsonb;
  company_value text;
  entity_value text;
  source_value text;
  batch_value text;
BEGIN
  old_row := CASE WHEN TG_OP = 'INSERT' THEN '{}'::jsonb ELSE to_jsonb(OLD) END;
  new_row := CASE WHEN TG_OP = 'DELETE' THEN '{}'::jsonb ELSE to_jsonb(NEW) END;
  company_value := COALESCE(new_row->>'company_id', old_row->>'company_id', '');
  entity_value := COALESCE(new_row->>TG_ARGV[1], old_row->>TG_ARGV[1], company_value);
  source_value := COALESCE(new_row->>'last_change_source', old_row->>'last_change_source', 'database');
  batch_value := COALESCE(new_row->>'last_change_batch_id', old_row->>'last_change_batch_id');

  FOR field_name IN SELECT jsonb_object_keys(old_row || new_row)
  LOOP
    IF field_name IN (
      'created_at','updated_at','created_by','updated_by',
      'last_change_source','last_change_batch_id','queued_at'
    ) THEN
      CONTINUE;
    END IF;

    old_value := old_row->field_name;
    new_value := new_row->field_name;

    IF TG_OP = 'INSERT' AND (new_value IS NULL OR new_value = 'null'::jsonb) THEN
      CONTINUE;
    END IF;
    IF TG_OP = 'DELETE' AND (old_value IS NULL OR old_value = 'null'::jsonb) THEN
      CONTINUE;
    END IF;

    IF old_value IS DISTINCT FROM new_value THEN
      INSERT INTO public.company_private_change_log (
        company_id, entity_type, entity_id, operation, field_name,
        old_value, new_value, change_source, import_batch_id, changed_by
      ) VALUES (
        company_value, TG_ARGV[0], entity_value, TG_OP, field_name,
        old_value, new_value, source_value, batch_value, auth.user_id()
      );
    END IF;
  END LOOP;

  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.towersignal_audit_company_change() FROM PUBLIC;

COMMIT;
