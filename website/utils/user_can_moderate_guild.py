from aiohttp.web import Request
import voxelbotutils as botutils
from voxelbotutils import web as webutils
import collections

import aiohttp_session
import discord
from discord.ext import commands


async def user_can_moderate_guild(request: Request, guild_id: int):
    """
    Returns whether or not the logged in user is making a valid request to the given
    guild.

    Args:
        request (Request): Description
        guild_id (int): Description

    Returns:
        bool: Description
    """

    # Grab the bot object - we'll be needing this
    bot: botutils.Bot = request.app['bots']['bot']

    # Fetch the guild they're trying to access
    oauth_members = await webutils.get_user_guilds_from_session(request)
    try:
        member = [i for i in oauth_members if i.guild.id == guild_id][0]
        guild = member.guild
    except IndexError:
        member = None
        guild = None

    # Check the member has permissions to manage this guild
    if member and guild and (guild.owner_id == member.id or member.guild_permissions.manage_guild):
        pass
    else:
        # See if they're bot support
        try:
            user_id = oauth_members[0].id
        except IndexError:
            session = await aiohttp_session.get_session(request)
            user_id = session['user_id']
        ctx = webutils.WebContext(bot, user_id)
        try:
            await botutils.checks.is_bot_support().predicate(ctx)
        except commands.CheckFailure as e:
            return False, guild, member
    return True, guild, member
