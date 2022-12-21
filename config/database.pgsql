CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


CREATE TABLE IF NOT EXISTS guild_settings(
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(30),
    max_template_count SMALLINT NOT NULL DEFAULT 0,
    max_template_field_count SMALLINT NOT NULL DEFAULT 0,
    max_template_profile_count SMALLINT NOT NULL DEFAULT 0,
    advanced BOOLEAN NOT NULL DEFAULT FALSE
);


CREATE TABLE IF NOT EXISTS user_settings(
    user_id BIGINT PRIMARY KEY
);


CREATE TABLE IF NOT EXISTS templates(
    id UUID NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    guild_id BIGINT NOT NULL,
    application_command_id BIGINT,
    colour INTEGER,
    verification_channel_id TEXT,
    archive_channel_id TEXT,
    role_id TEXT,
    max_profile_count SMALLINT NOT NULL DEFAULT 5,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    context_command_id BIGINT,
    archive_is_forum BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (guild_id, name)
);


DO $$ BEGIN
    CREATE TYPE field_type AS ENUM(
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


CREATE TABLE IF NOT EXISTS fields(
    id UUID NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT,
    index SMALLINT,
    prompt TEXT,
    field_type field_type NOT NULL DEFAULT '1000-CHAR',
    optional BOOLEAN DEFAULT FALSE,
    deleted BOOLEAN DEFAULT FALSE,
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS created_profiles(
    id UUID NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,
    posted_message_id BIGINT,
    posted_channel_id BIGINT,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    draft BOOLEAN NOT NULL DEFAULT TRUE,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (user_id, name, template_id)
);
-- A table describing an entire profile filled by a user
-- user_id - the user filling the profile
-- template_id - the profile being filled
-- verified - whether or not the profile is a verified one
-- draft - a flag to say that a given profile is in the process of being edited


CREATE TABLE IF NOT EXISTS filled_fields(
    profile_id UUID REFERENCES created_profiles(id) ON DELETE CASCADE,
    field_id UUID REFERENCES fields(id) ON DELETE CASCADE,
    value TEXT,
    PRIMARY KEY (profile_id, field_id)
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
