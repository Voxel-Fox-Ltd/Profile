from aiohttp.web import HTTPFound, Request, Response, RouteTableDef
import voxelbotutils as botutils
from voxelbotutils import web as webutils
import aiohttp_session
import discord
from discord.ext import commands
from aiohttp_jinja2 import template

from cogs import utils as localutils
from website import utils as localwebutils


routes = RouteTableDef()


@routes.get("/")
@template("index.htm.j2")
@webutils.add_discord_arguments()
async def index(request: Request):
    """
    The index page for the website.
    """

    return {}


@routes.get("/guilds")
@webutils.requires_login()
@template("guilds.htm.j2")
@webutils.add_discord_arguments()
async def guilds(request: Request):
    """
    The guild picker page for the bot.
    """

    all_guilds = await webutils.get_user_guilds_from_session(request)
    valid_guilds = [i.guild for i in all_guilds if i.guild_permissions.manage_guild or i.guild.owner_id == i.id]
    return {
        "guilds": valid_guilds,
    }


@routes.get(r"/guilds/{guild_id:\d+}")
@webutils.requires_login()
@template("guild_settings.htm.j2")
@webutils.add_discord_arguments()
async def guild_settings(request: Request):
    """
    The guild settings page for a given bot.
    """

    # Get the guild object
    guild_id = int(request.match_info.get("guild_id"))
    bot: botutils.Bot = request.app['bots']['bot']
    user_can_moderate, guild, member = await localwebutils.user_can_moderate_guild(request, guild_id)
    if not user_can_moderate:
        return HTTPFound(location="/guilds")

    # Grab their current settings
    async with request.app['database']() as db:
        guild_rows = await db("SELECT * FROM guild_settings WHERE guild_id=$1 OR guild_id=0 ORDER BY guild_id DESC", guild_id)
        guild_templates = await localutils.Template.fetch_all_templates_for_guild(db, guild_id, fetch_fields=True)

    # See if we want to invite the bot
    if guild is None and not guild_templates:
        return HTTPFound(location=bot.get_invite_link(guild_id=guild_id))

    # Return the guild data
    return {
        "guild": guild_rows[0],
        "guild_object": guild,
        "templates": guild_templates,
        "CommandProcessor": localutils.CommandProcessor,  # Throw in this whole class so we can use it in the template
    }
