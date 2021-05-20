from aiohttp.web import HTTPFound, Request, Response, RouteTableDef
from voxelbotutils import web as webutils
import aiohttp_session
import discord
from aiohttp_jinja2 import template

from cogs import utils as localutils


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
    valid_guilds = [
        i for i in all_guilds if i['owner'] or discord.Permissions(i['permissions']).manage_guild
    ]
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
    try:
        guild = await request.app['bots']['bot'].fetch_guild(guild_id)
    except discord.HTTPException:
        return HTTPFound(location="/")

    # Get the member object
    session = await aiohttp_session.get_session(request)
    try:
        member = await guild.fetch_member(session['user_id'])
    except discord.HTTPException:
        return HTTPFound(location="/")

    # Check the member has permissions to manage this guild
    if guild.owner_id == member.id or member.guild_permissions.manage_guild:
        pass
    else:
        return HTTPFound(location="/")

    # Grab their current settings
    async with request.app['database']() as db:
        guild_rows = await db("SELECT * FROM guild_settings WHERE guild_id=$1 OR guild_id=0 ORDER BY guild_id DESC", guild.id)
        guild_templates = await localutils.Template.fetch_all_templates_for_guild(db, guild.id, fetch_fields=True)

    # Return the guild data
    return {
        "guild": guild_rows[0],
        "templates": guild_templates,
        "CommandProcessor": localutils.CommandProcessor
    }
