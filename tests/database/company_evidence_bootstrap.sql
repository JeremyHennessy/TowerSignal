CREATE ROLE authenticated;
CREATE SCHEMA auth;
CREATE SCHEMA neon_auth;
CREATE TABLE neon_auth."user"(id text PRIMARY KEY,role text);
INSERT INTO neon_auth."user" VALUES('admin-test','admin'),('reader-test','user');
CREATE FUNCTION auth.user_id() RETURNS text LANGUAGE sql STABLE AS $$ SELECT current_setting('test.user_id',true) $$;
GRANT USAGE ON SCHEMA auth TO authenticated;
GRANT EXECUTE ON FUNCTION auth.user_id() TO authenticated;
