# Profile

Testing procedures for profile.

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
    - [ ] Fields with a command set should not be filled.

## Submission

- [x] If a template has a verification channel, a profile must be verified before
it is sent to the archive channel.
- [x] If there is no verification channel but there is an archive channel, the
profile is sent to the archive channel without being checked.
- [x] If there are neither, the profile is just marked as both submitted
and verified.

## Verification

- [x] When a profile is sent to the verification channel, an "approve" and "deny"
button are both added to the associated profile.
- [ ] If the approve button is pressed,
    - [ ] the message is deleted,
    - [ ] the profile is sent to the archive channel (if one is set),
    - [ ] and the user is sent a DM saying their profile was verified.
- [ ] If the deny button is pressed,
    - [ ] the moderator is asked for a reason.
    - [ ] After a reason is given, the message is deleted,
    - [ ] and the user is sent a DM saying their profile was denied,
    - [ ] along with the reason.
