import discord
from discord.ext import vbu

from . import utils
from .utils import UserProfile, Template


class ProfileEdit(vbu.Cog[vbu.Bot]):

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n(__name__)
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
                (
                    "Your profile has been converted to a draft. "
                    "You can now edit it."
                )
            ),
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n(__name__)
    async def profile_edit_selector(
            self,
            interaction: discord.ComponentInteraction):
        """
        The profile edit selector.
        """

        # Check the interaction is from a profile edit selector
        if not interaction.custom_id.startswith("PROFILE EDIT"):
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
            if profile is None:
                return await interaction.response.send_message(
                    "That profile doesn't exist.",  # Error message, shouldn't need translating
                    ephemeral=True
                )

            # Get template
            template = await Template.fetch_template_by_id(db, profile.template_id)
            if template is None:
                return await interaction.response.send_message(
                    "That template doesn't exist.",  # Error message, shouldn't need translating
                    ephemeral=True
                )

            # Get field
            profile.template = template
            field = profile.template.fields.get(field_id)
            if field is None:
                return await interaction.response.send_message(
                    "That field doesn't exist.",  # Error message, shouldn't need translating
                    ephemeral=True
                )
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
                        min_length=1,
                        max_length=1_000,
                        required=True,
                    ),
                ),
            ],
        )
        await interaction.response.send_modal(modal)


def setup(bot: vbu.Bot):
    x = ProfileEdit(bot)
    bot.add_cog(x)
