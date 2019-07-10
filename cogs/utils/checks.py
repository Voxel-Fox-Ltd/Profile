from discord import Member

from cogs.utils.custom_bot import CustomBot


def member_is_moderator(bot:CustomBot, member:Member) -> bool:
    return any([
        member.guild_permissions.manage_roles,
        member.id in bot.config['owners'],
        member.guild.owner == member,
    ])
