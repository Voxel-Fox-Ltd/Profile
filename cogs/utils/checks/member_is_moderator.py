def member_is_moderator(bot, member) -> bool:
    """Returns whether or not a given discord.Member object is a moderator"""

    # Make sure they're an actual member
    if member.guild is None:
        return False

    # And return checks
    return any([
        member.guild_permissions.manage_roles,
        member.id in bot.config['owners'],
        member.guild.owner == member,
    ])
