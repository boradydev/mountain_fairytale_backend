DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM points WHERE client_id IS NULL) THEN
        RAISE EXCEPTION 'Cannot restore required client_id while anonymous purchases exist. Restore a pre-upgrade backup or resolve these records explicitly.';
    END IF;
END $$;

ALTER TABLE points ALTER COLUMN client_id SET NOT NULL;
