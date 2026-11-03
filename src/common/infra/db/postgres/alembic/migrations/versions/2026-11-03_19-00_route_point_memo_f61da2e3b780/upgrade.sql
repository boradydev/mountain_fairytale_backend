ALTER TABLE points ADD COLUMN memo text NOT NULL DEFAULT '';

ALTER TABLE points ADD CONSTRAINT points_memo_length_check
    CHECK (length(memo) <= 1000);
