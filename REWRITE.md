# Rewrite

This doc is to keep track of changes between the live version and the stateless
version so I can seamlessly integrate them back together.

## Tables

### Templates

- `template` -> `templates`.
- `.template_id` -> `.id`.
- `.id` now has a `NOT NULL` constraint.
- `.name` now has type `TEXT`.
- `.max_profile_count` now has a `NOT NULL` constraint.
- Add `.deleted`.
- Add `.context_command_id`.

### Field type

- `FIELDTYPE` -> `field_type`

### Fields

- `field` -> `fields`.
- `.field_id` -> `.id`.
- `.name` now has type `TEXT`.
- `.field_type` now has a `NOT NULL` constraint, and defaults to `1000-CHAR`.

### Created profiles

- `created_profile` -> `created_profiles`.
- Add `.id` as the new primary key.
- `.name` now has type `TEXT`.
- Add `.draft`.
- Add `.deleted`.
- Remove the previous primary key, and instead make it into a `UNIQUE` constraint.

### Filled fields

- `filled_field` -> `filled_fields`.
- Remove `.user_id` and `.name`.
- Add `.profile_id`.
- `.value` now has type `TEXT`.



