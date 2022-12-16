# Profile

Testing procedures for profile.

## Bot options

- [ ] Allow users to enable "advanced" mode.
    - [ ] This will increase the prompt limit to 1000 characters for fields.
    This will allow users to input commands, and multi-fields.
    - [ ] This will allow users to input text for their archive and
    verification channels; up to 1000 characters.
    This will allow users to input commands.

## Templates

### Creation and deletion

- [x] Users can create a template (/template create).
    - [x] The bot will check that the given name is not already in use.
    - [x] The bot will check that the maximum number of templates has not been
    exceeded.
- [x] Users can edit a template (/template edit).
- [x] Users can delete a template (/template delete).
    - [x] The template will be marked as deleted.
    - [x] All associated profiles will be marked as deleted.
- [x] Users can see the list of templates (/template list).

### Base editing

- [x] The name on a template can be changed.
- [x] The archive channel can be changed.
- [x] The archive channel can be removed.
- [x] The verification channel can be changed.
- [x] The verification channel can be removed.
- [x] The given role can be changed.
- [x] The given role can be removed.
- [x] A slash command can be added/updated.
    - [ ] If the max number of profiles is 0 when this is run, the slash
    command is deleted.
- [ ] A context menu command can be added/updated/removed.
- [x] A maximum number of profiles can be set.

### Field editing

- [x] A field can be added.
- [x] A field can be renamed.
    - [x] The name can be in use multiple times.
- [x] A field prompt can be set.
- [x] A field type can be set.
    - [x] Only one image field is allowed.
- [x] A field can be made optional/required.
- [x] A field can be deleted.

## Profiles

### Creation and deletion

- [x] Users can create a profile (/profile create).
    - [x] The bot will check that the given name is not already in use.
    - [x] The bot will check that the maximum number of profiles has not been
    exceeded.
- [x] Users can edit a profile (/profile edit).
- [x] Users can delete a profile (/profile delete).
- [x] Users can see profiles (/profile get).
    - [ ] The bot can only see profiles that they made,
    - [ ] or profiles that have been verified already.
    - [x] There should be an error message if the user pinged has no profiles.
    - [ ] The message will be ephemeral by default, but a button will be
    present for verified profiles to repost the profile publicly.
    - [ ] Multi-fields; https://canary.discord.com/channels/208895639164026880/1052974864513896478/1052994405184847943

### Base editing

- [x] A profile needs to be a draft to be edited.
    - [x] If a profile is not a draft, the user is asked to convert it to one.
    - [x] When a profile is converted to a draft, the sent messages (either to
    the verification or archive channel) are deleted.
- [x] The name on a profile can be changed.
    - [x] The bot will check that the given name is not already in use.
- [x] A profile can be submitted.
    - [x] The bot will check that the maximum number of profiles has not been
    exceeded.

### Field editing

- [x] All fields added to the template can be set.
    - [x] The fields must have valid values as per their type.
    - [x] Optional fields do not need to be filled, and can be cleared.
    - [x] Fields with a command set should not be filled.
    - [ ] If a multi-field is created, each line of the prompt should be added
    to a modal.

## Submission

- [x] If a template has a verification channel, a profile must be verified before
it is sent to the archive channel.
- [x] If there is no verification channel but there is an archive channel, the
profile is sent to the archive channel without being checked.
    - [x] The associated role (if present) is added to the user.
- [x] If there are neither, the profile is just marked as both submitted
and verified.
    - [x] The associated role (if present) is added to the user.

## Verification

- [x] When a profile is sent to the verification channel, an "approve" and "deny"
button are both added to the associated profile.
- [x] If the approve button is pressed,
    - [x] the message is deleted,
    - [x] the profile is sent to the archive channel (if one is set),
    - [x] and the user is sent a DM saying their profile was verified.
    - [x] The profile is marked as verified.
    - [x] The associated role (if present) is added to the user.
    - [ ] The moderator, profile JSON dump, and time are logged into
    the database.
- [x] If the deny button is pressed,
    - [ ] the moderator is asked for a reason.
    - [x] After a reason is given, the message is deleted,
    - [x] and the user is sent a DM saying their profile was denied,
    - [ ] along with the reason.
    - [x] The profile is converted back to a draft.
    - [ ] The moderator, profile JSON dump, time, and reason are logged into
    the database.
