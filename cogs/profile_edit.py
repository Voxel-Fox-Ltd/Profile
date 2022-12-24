from typing import TYPE_CHECKING, Optional, cast
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
        self.logger.info("Setting profile %s to a draft", profile_id)

        # Get the profile object
        partial_message = None
        async with vbu.Database() as db:
            profile = await utils.UserProfile.fetch_profile_by_id(
                db,
                profile_id,
            )
            if not profile:
                return await interaction.response.edit_message(
                    content=_("That profile doesn't exist."),
                    components=None,
                    embeds=[],
                )

            # See if it's already a draft
            if profile.draft:
                return await interaction.response.edit_message(
                    content=_("That profile is already a draft."),
                    components=None,
                    embeds=[],
                )

            # Get a partial message if there's one posted already
            if profile.posted_channel_id:
                partial_channel = discord.PartialMessageable(
                    state=self.bot._connection,
                    id=profile.posted_channel_id,
                    type=discord.ChannelType.text,
                )
                if profile.posted_message_id:
                    partial_message = partial_channel.get_partial_message(
                        profile.posted_message_id,
                    )

            # Set the draft flag
            await profile.update(
                db,
                verified=False,
                draft=True,
                posted_message_id=None,
                posted_channel_id=None,
            )

        # Delete message if applicable
        if partial_message:
            try:
                await partial_message.delete()
            except discord.HTTPException:
                pass

        # Tell them it's done
        await interaction.response.edit_message(
            content=_(
                "Your profile has been converted to a draft. "
                "You can now edit it."
            ),
            components=None,
            embeds=[],
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
        self.logger.info(
            "Sending modal for profile %s, field %s",
            profile_id, field_id,
        )

        # Get the profile, template, and current field value
        async with vbu.Database() as db:

            # Get profile
            profile = await UserProfile.fetch_profile_by_id(db, profile_id)
            assert profile, "Profile does not exist."

            # Only allow editing of draft profiles
            if not profile.draft:
                return await interaction.response.edit_message(
                    content=_(
                        "You can only edit draft profiles. "
                        "Convert this profile to a draft to proceed."
                    ),
                    components=None,
                )

            # Get template
            template = await Template.fetch_template_by_id(db, profile.template_id)
            assert template, "Template does not exist."
            profile.template = template
            profile = cast(utils.UserProfile[utils.Template], profile)

            # Get field
            field = profile.template.fields.get(field_id)
            assert field, "Field does not exist."
            filled_fields = await profile.fetch_filled_fields(db)

            # Only allow editing if a newly generated embed is the same as the
            # one attached to the message they clicked on
            past_embed = interaction.message.embeds[0]
            assert isinstance(interaction.user, discord.Member)
            new_embed = profile.build_embed(
                self.bot,
                interaction,
                (
                    interaction.user
                    if
                        interaction.user.id == profile.user_id
                    else
                        await interaction.guild.fetch_member(profile.user_id)  # pyright: ignore
                ),
            )
            if not utils.compare_embeds(past_embed, new_embed):
                return await interaction.response.edit_message(
                    content=_(
                        "This is not the most recent version of your profile. "
                        "Please re-run the edit command to continue."
                    ),
                    components=None,
                )

        # Work out what we want to fill the modal with
        try:
            current_value = filled_fields[field_id].value.strip()
        except:
            current_value = ""
        prompt_split, value_split = utils.pad_field_prompt_value(
            field.prompt,
            current_value,
        )

        # Ask the user to fill in the field
        modal = discord.ui.Modal(
            title=field.name[:45],
            custom_id=f"PROFILE SET {short_profile_id} {short_field_id}",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        label=p[:45] or str(index),
                        value=v,
                        style=(
                            discord.TextStyle.long
                            if len(prompt_split) == 1
                            else discord.TextStyle.short
                        ),
                        max_length=1_000,
                        required=False,
                    ),
                )
                for index, (p, v) in enumerate(zip(prompt_split, value_split))
            ],
        )
        await interaction.response.send_modal(modal)

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n("profile")
    async def profile_name_change(
            self,
            interaction: discord.ComponentInteraction):
        """
        Allow people to change the name of their profiles.
        """

        # Check the interaction is from a profile edit selector
        if not interaction.custom_id.startswith("PROFILE EDIT_NAME"):
            return

        # Get the profile they're trying to edit
        short_profile_id = interaction.custom_id.split(" ")[2]
        profile_id = utils.uuid.decode(short_profile_id)
        self.logger.info("Sending modal for profile name %s", profile_id)

        # Get the profile, template, and current field value
        async with vbu.Database() as db:

            # Get profile
            profile = await UserProfile.fetch_profile_by_id(db, profile_id)
            assert profile, "Profile does not exist."

            # Get template
            template = await profile.fetch_template(db)
            assert template, "Template does not exist."

        # Ask the user to fill in the field
        current_value = profile.name
        modal = discord.ui.Modal(
            title=template.name[:45],
            custom_id=f"PROFILE SET_NAME {short_profile_id}",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        label=_("Set the name of your profile")[:45],
                        value=current_value,
                        min_length=1,
                        max_length=32,
                        required=True,
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
        self.logger.info(
            "Setting profile value for profile %s, field %s",
            profile_id, field_id,
        )

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
        given_value: str = "\n".join(
            action_row.components[0].value  # pyright: ignore
            for action_row in interaction.components
        ).strip()

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
            filled_field.field = field  # pyright: ignore - about to reassign
            filled_field = cast(utils.FilledField[utils.Field], filled_field)
        else:
            profile.all_filled_fields.pop(field_id, None)

        # Edit the original message
        cog: Optional[ProfileCommands]
        cog = self.bot.get_cog("ProfileCommands")  # pyright: ignore
        assert cog, "Cog not loaded."
        await interaction.response.defer_update()
        await cog.profile_edit(
            interaction,
            template,
            profile,
            edit_original=True,
        )

    @vbu.Cog.listener("on_modal_submit")
    @vbu.i18n("profile")
    async def profile_name_set(
            self,
            interaction: discord.ModalInteraction):
        """
        Set a profile field, saving in database and editing the original
        message to show an updated embed.
        """

        # Check the interaction is from a profile edit selector
        if not interaction.custom_id.startswith("PROFILE SET_NAME "):
            return

        # Get the profile they're trying to edit
        short_profile_id = interaction.custom_id.split(" ")[2]
        profile_id = utils.uuid.decode(short_profile_id)
        self.logger.info(
            "Setting profile name for profile %s",
            profile_id
        )

        # Get the profile, template, and current field value
        async with vbu.Database() as db:

            # Get profile
            profile = await UserProfile.fetch_profile_by_id(db, profile_id)
            assert profile, "Profile has been deleted."

            # Get template
            template = await profile.fetch_template(db)
            assert template, "Template does not exist."

            # Get all of user's profiles
            assert profile.user_id, "Profile not assigned to a user."
            all_profiles = await template.fetch_all_profiles_for_user(
                db,
                profile.user_id,
            )

            # Get the value
            given_value: str = (
                interaction
                .components[0]  # pyright: ignore
                .components[0]
                .value
            )  # pyright: ignore

            # Make sure they don't have a profile existing with that
            # name already
            profiles_with_name = [
                i
                for i in all_profiles
                if
                    i.name
                and
                    i.name.casefold() == given_value.casefold()
                and
                    i.id != profile.id
            ]
            if profiles_with_name:
                return await interaction.response.send_message(
                    _("You already have a profile with that name."),
                    ephemeral=True,
                )

            # Edit the profile name
            await profile.update(db, name=given_value)

            # Get filled fields so we can pass it straight back to edit
            await profile.fetch_filled_fields(db)

        # Edit the original message
        cog: Optional[ProfileCommands]
        cog = self.bot.get_cog("ProfileCommands")  # pyright: ignore
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
