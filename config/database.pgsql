CREATE TABLE IF NOT EXISTS guild_settings(
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(30),
    max_template_count SMALLINT DEFAULT 0,
    max_template_field_count SMALLINT DEFAULT 0,
    max_template_profile_count SMALLINT DEFAULT 0
);


CREATE TABLE IF NOT EXISTS user_settings(
    user_id BIGINT PRIMARY KEY
);


CREATE TABLE IF NOT EXISTS role_list(
    guild_id BIGINT,
    role_id BIGINT,
    key VARCHAR(50),
    value VARCHAR(50),
    PRIMARY KEY (guild_id, role_id, key)
);


CREATE TABLE IF NOT EXISTS channel_list(
    guild_id BIGINT,
    channel_id BIGINT,
    key VARCHAR(50),
    value VARCHAR(50),
    PRIMARY KEY (guild_id, channel_id, key)
);


CREATE TABLE IF NOT EXISTS template(
    template_id UUID PRIMARY KEY,
    name VARCHAR(30),
    colour INTEGER,
    guild_id BIGINT NOT NULL,
    verification_channel_id TEXT,
    archive_channel_id TEXT,
    role_id TEXT,
    -- max_field_count SMALLINT DEFAULT 10,
    max_profile_count SMALLINT DEFAULT 5,
    UNIQUE (guild_id, name)
);
-- A table to describe a profile in its entirety
-- template_id - the general ID of the profile
-- name - the name of the profile used in commands
-- colour - the colour of the embed field
-- guild_id - the guild that the profile is made for
-- verification_channel_id - the channel that profiles are sent to for approval; if null then no approval needed


DO $$ BEGIN
    CREATE TYPE FIELDTYPE AS ENUM(
        '1000-CHAR',
        '200-CHAR',
        '50-CHAR',
        'INT',
        'IMAGE',
        'BOOLEAN'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
-- the different types that a field can contain


CREATE TABLE IF NOT EXISTS field(
    field_id UUID PRIMARY KEY,
    name VARCHAR(256),
    index SMALLINT,
    prompt TEXT,
    timeout SMALLINT,
    field_type FIELDTYPE,
    optional BOOLEAN DEFAULT FALSE,
    deleted BOOLEAN DEFAULT FALSE,
    template_id UUID REFERENCES template(template_id) ON DELETE CASCADE
);
-- A table to describe each individual field in a profile
-- field_id - general ID of the field
-- name - the name of the field to show in the embed
-- index - the index of the field in the profile to be used
-- prompt - the prompt given to the user when filling out this field
-- timeout - the timeout that will be given to the user when filling in this field
-- field_type - the datatype of the field to be converted to
-- optional - whether or not the field is optional
-- profile - the profile that this field is a part of


CREATE TABLE IF NOT EXISTS created_profile(
    user_id BIGINT,
    name VARCHAR(1000),
    template_id UUID REFERENCES template(template_id) ON DELETE CASCADE,
    verified BOOLEAN DEFAULT FALSE,
    posted_message_id BIGINT,
    posted_channel_id BIGINT,
    PRIMARY KEY (user_id, name, template_id)
);
-- A table describing an entire profile filled by a user
-- user_id - the user filling the profile
-- template_id - the profile being filled
-- verified - whether or not the profile is a verified one


CREATE TABLE IF NOT EXISTS filled_field(
    user_id BIGINT,
    name VARCHAR(1000),
    field_id UUID REFERENCES field(field_id) ON DELETE CASCADE,
    value VARCHAR(1000),
    PRIMARY KEY (user_id, name, field_id)
);
-- A table for stored field data for a user
-- user_id - the user that filled in the field
-- field_id - the field that's being filled in
-- value - the value that the field was filled with (must be converted)


CREATE TABLE IF NOT EXISTS guild_subscriptions(
    guild_id BIGINT,
    user_id BIGINT,
    cancel_url TEXT,
    expiry_time TIMESTAMP,
    PRIMARY KEY (guild_id)
);
-- A table for the users who are subcribing to the premium features
