CREATE TABLE guild_settings(
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(30)
);


CREATE TABLE command_log(
    guild_id BIGINT,
    channel_id BIGINT,
    user_id BIGINT,
    message_id BIGINT PRIMARY KEY,
    content VARCHAR(2000),
    command_name VARCHAR(100),
    invoked_with VARCHAR(100),
    command_prefix VARCHAR(2000),
    timestamp TIMESTAMP,
    command_failed BOOLEAN,
    valid BOOLEAN,
    shard_id SMALLINT
);


CREATE TABLE profile(
    profile_id UUID PRIMARY KEY,
    name VARCHAR(30),
    colour INTEGER,
    guild_id BIGINT NOT NULL,
    verification_channel_id BIGINT,
    archive_channel_id BIGINT
);
-- A table to describe a profile in its entirety
-- profile_id - the general ID of the profile
-- name - the name of the profile used in commands
-- colour - the colour of the embed field
-- guild_id - the guild that the profile is made for
-- verification_channel_id - the channel that profiles are sent to for approval; if null then no approval needed


CREATE TYPE FIELDTYPE AS ENUM(
    '1000-CHAR',
    '200-CHAR',
    '50-CHAR',
    'INT',
    'IMAGE',
    'BOOLEAN'
);
-- the different types that a field can contain


CREATE TABLE field(
    field_id UUID PRIMARY KEY,
    name VARCHAR(256),
    index SMALLINT,
    prompt TEXT,
    timeout SMALLINT,
    field_type FIELDTYPE,
    optional BOOLEAN DEFAULT FALSE,
    profile_id UUID REFERENCES profile(profile_id)
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


CREATE TABLE created_profile(
    user_id BIGINT,
    profile_id UUID REFERENCES profile(profile_id),
    verified BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (user_id, profile_id)
);
-- A table describing an entire profile filled by a user
-- user_id - the user filling the profile
-- profile_id - the profile being filled
-- verified - whether or not the profile is a verified one


CREATE TABLE filled_field(
    user_id BIGINT,
    field_id UUID REFERENCES field(field_id),
    value VARCHAR(1000),
    PRIMARY KEY (user_id, field_id)
);
-- A table for stored field data for a user
-- user_id - the user that filled in the field
-- field_id - the field that's being filled in
-- value - the value that the field was filled with (must be converted)
