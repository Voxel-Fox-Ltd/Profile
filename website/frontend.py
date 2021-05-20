from aiohttp.web import HTTPFound, Request, Response, RouteTableDef
from voxelbotutils import web as webutils
import aiohttp_session
import discord
from aiohttp_jinja2 import template


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

