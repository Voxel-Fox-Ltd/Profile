from typing import TYPE_CHECKING, Optional
import discord
from discord.ext import vbu

from . import utils
from .utils import UserProfile, Template

if TYPE_CHECKING:
    from .profile_commands import ProfileCommands


class ProfileEdit(vbu.Cog[vbu.Bot]):

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n("profile")
    async def profile_set_draft(
            self,
            interaction: discord.ComponentInteraction):
        """
        Set a profile to a draft.
        """

        # Make sure we're looking at the right component
        if not interaction.custom_id.startswith("PROFILE CONFIRM_EDIT "):
            return

        # Get the profile ID
        short_profile_id = interaction.custom_id.split(" ")[2]
        profile_id = utils.uuid.decode(short_profile_id)

        # Get the profile object
        async with vbu.Database() as db:
            profile = await utils.UserProfile.fetch_profile_by_id(
                db,
                profile_id,
            )
            if not profile:
                return await interaction.response.send_message(
                    "That profile doesn't exist.",
                    ephemeral=True,
                )

            # Set the draft flag
            await profile.update(db, draft=True)

        # Tell them it's done
        await interaction.response.send_message(
            _(
                "Your profile has been converted to a draft. "
                "You can now edit it."
            ),
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n("profile")
    async def profile_edit_selector(
            self,
            interaction: discord.ComponentInteraction):
        """
        The profile edit selector.
        """

        # Check the interaction is from a profile edit selector
        if not interaction.custom_id.startswith("PROFILE EDIT "):
            return

        # Get the profile they're trying to edit
        short_profile_id = interaction.custom_id.split(" ")[2]
        profile_id = utils.uuid.decode(short_profile_id)
        short_field_id = interaction.custom_id.split(" ")[3]
        field_id = utils.uuid.decode(short_field_id)

        # Get the profile, template, and current field value
        async with vbu.Database() as db:

            # Get profile
            profile = await UserProfile.fetch_profile_by_id(db, profile_id)
            assert profile, "Profile does not exist."

            # Get template
            template = await Template.fetch_template_by_id(db, profile.template_id)
            assert template, "Template does not exist."
            profile.template = template

            # Get field
            field = profile.template.fields.get(field_id)
            assert field, "Field does not exist."
            filled_fields = await profile.fetch_filled_fields(db)

        # Ask the user to fill in the field
        try:
            current_value = filled_fields[field_id].value
        except:
            current_value = None
        modal = discord.ui.Modal(
            title=field.name,
            custom_id=f"PROFILE SET {short_profile_id} {short_field_id}",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        label=field.prompt,
                        value=current_value,
                        # min_length=1,
                        max_length=1_000,
                        # required=True,
                    ),
                ),
            ],
        )
        await interaction.response.send_modal(modal)

    @vbu.Cog.listener("on_modal_submit")
    @vbu.i18n("profile")
    async def profile_edit_set(
            self,
            interaction: discord.ModalInteraction):
        """
        Set a profile field, saving in database and editing the original
        message to show an updated embed.
        """

        # Check the interaction is from a profile edit selector
        if not interaction.custom_id.startswith("PROFILE SET "):
            return

        # Get the profile they're trying to edit
        short_profile_id = interaction.custom_id.split(" ")[2]
        profile_id = utils.uuid.decode(short_profile_id)
        short_field_id = interaction.custom_id.split(" ")[3]
        field_id = utils.uuid.decode(short_field_id)

        # Get the profile, template, and current field value
        async with vbu.Database() as db:

            # Get profile
            profile = await UserProfile.fetch_profile_by_id(db, profile_id)
            assert profile, "Profile has been deleted."

            # Get template
            template = await Template.fetch_template_by_id(db, profile.template_id)
            assert template, "Template has been deleted."
            profile.template = template

            # Get all relevant fields
            await template.fetch_fields(db)
            await profile.fetch_filled_fields(db)

            # Get field
            field = profile.template.fields.get(field_id)
            assert field, "Field has been deleted."

        # Get the value
        given_value: str = interaction.components[0].components[0].value

        # Validate the value
        if given_value:
            try:
                field.field_type.check(given_value)
                given_value = await field.field_type.fix(given_value)
            except utils.FieldCheckFailure:
                # TRANSLATORS: Catch all error message that shouldn't be shown
                message: str = _("I encountered an error.")
                match field.field_type:
                    case utils.TextField:
                        message = _(
                            "The length of your input must be between 1 "
                            "and 1000 characters."
                        )
                    case utils.NumberField:
                        message = _(
                            "You did not give a valid number."
                        )
                    case utils.ImageField:
                        message = _(
                            "The image URL you gave isn't valid. "
                            "Please give a direct link to an image."
                        )
                return await interaction.response.send_message(
                    message,
                    ephemeral=True,
                )

        # Save the value
        async with vbu.Database() as db:
            filled_field = await utils.FilledField.update_by_id(
                db,
                profile_id,
                field_id,
                given_value or None,
            )
        if filled_field:
            profile.all_filled_fields[field_id] = filled_field
            filled_field.field = field
        else:
            profile.all_filled_fields.pop(field_id, None)

        # Edit the original message
        cog: Optional[ProfileCommands] = self.bot.get_cog("ProfileCommands")
        assert cog, "Cog not loaded."
        await interaction.response.defer_update()
        await cog.profile_edit(
            interaction,
            template,
            profile,
            edit_original=True,
        )


def setup(bot: vbu.Bot):
    x = ProfileEdit(bot)
    bot.add_cog(x)
