import discord
from discord.ext import vbu

from cogs import utils


class MessageUtils(vbu.Cog[utils.types.Bot]):

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n("profile")
    async def message_edit_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        A listener for the message edit component.
        """

        # Make sure we're listening for something we care about
        if not interaction.custom_id.startswith("MESSAGE_EDIT RESEND "):
            return

        # Get the message items we want to resend
        kwargs = {
            "content": (
                _("Message requested by {user}.").format(user=interaction.user.mention)
                + "\n" + interaction.message.content
            ),
            "embeds": interaction.message.embeds,
            "files": interaction.message.attachments,
            "components": interaction.message.components,
            "ephemeral": True,
        }
        for key, value in kwargs.items():
            if not value:
                del kwargs[key]

        # See what we want to remove via the custom ID
        to_remove: list[str] = interaction.custom_id.split(" ")[2:]
        for key in to_remove:
            if key.startswith("-"):
                del kwargs[key.lstrip("-")]

        # See if the user has permission to send messages
        if not interaction.permissions.send_messages:
            return await interaction.response.send_message(
                _("You don't have permission to send messages in this channel."),
                ephemeral=True,
            )

        # Remove the components from the original message
        await interaction.response.edit_message(components=None)

        # Try and send our kwargs through the API, falling back to followup if
        # we're missing permissions
        try:
            assert isinstance(interaction.channel, discord.abc.Messageable)
            await interaction.channel.send(**kwargs)
        except (discord.Forbidden, AssertionError):
            await interaction.followup.send(**kwargs)


def setup(bot: utils.types.Bot):
    x = MessageUtils(bot)
    bot.add_cog(x)
