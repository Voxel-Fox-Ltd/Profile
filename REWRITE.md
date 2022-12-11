# Rewrite

This doc is to keep track of changes between the live version and the stateless
version so I can seamlessly integrate them back together.

## SQL

I've added an `id` column to the `created_profile` table. `filled_fields` has
also been changed to accomodate said change.

The `created_profile` table also has a new `draft` field to indicate whether
the profile has been submitted or not. This lets us know if the profile is being
edited.
