from datetime import datetime as dt

from aiohttp.web import HTTPFound, Request, RouteTableDef
import voxelbotutils as vbu
import discord
from aiohttp_jinja2 import template
import humanize

from cogs import utils
from website import utils as webutils


routes = RouteTableDef()


@routes.get("/")
@template("index.htm.j2")
@vbu.web.add_discord_arguments()
async def index(request: Request):
    """
    The index page for the website.
    """

    return {}


@routes.get(r"/guilds/{guild_id:\d+}/premium")
@template("premium.htm.j2")
@vbu.web.add_discord_arguments()
@vbu.web.requires_login()
async def premium(request: Request):
    """
    The premium page for the website.
    """

    # Get the guild object
    guild_id = int(request.match_info.get("guild_id"))
    bot: vbu.Bot = request.app['bots']['bot']
    user_can_moderate, guild, member = await webutils.user_can_moderate_guild(request, guild_id)
    if guild is None or not user_can_moderate:
        raise HTTPFound(location="/")

    # Grab their current settings
    async with request.app['database']() as db:
        guild_rows = await db("SELECT * FROM guild_settings WHERE guild_id=$1", guild_id)
        guild_subscriptions = await db(
            """SELECT * FROM guild_subscriptions WHERE guild_id=$1 AND
            (expiry_time IS NULL OR expiry_time > TIMEZONE('UTC', NOW()))""",
            guild_id,
        )

    # Upgrade the guild so we can see if the bot's in it
    upgraded_guild = await guild.fetch_guild()
    guild_rows = None if not guild_rows else guild_rows[0]
    guild_subscriptions = None if not guild_subscriptions else guild_subscriptions[0]
    currently_expiring = None
    if guild_subscriptions:
        if guild_subscriptions['expiry_time']:
            currently_expiring = humanize.naturaldelta(guild_subscriptions['expiry_time'] - dt.utcnow())

    # See if we want to invite the bot
    if upgraded_guild is None:
        raise HTTPFound(location=bot.get_invite_link(guild_id=guild_id))

    # Return the guild data
    return {
        "guild": upgraded_guild,
        "guild_settings": guild_rows,
        "premium_data": guild_subscriptions,
        "currently_expiring": currently_expiring,

        "non_premium_perks": utils.perks_handler.NO_GUILD_PERKS,
        "premium_perks": utils.perks_handler.SUBSCRIBED_GUILD_PERKS,
    }


@routes.get("/guilds")
@vbu.web.requires_login()
@template("guilds.htm.j2")
@vbu.web.add_discord_arguments()
async def guilds(request: Request):
    """
    The guild picker page for the bot.
    """

    all_guilds = await vbu.web.get_user_guilds_from_session(request)
    valid_guilds = [i.guild for i in all_guilds if i.guild_permissions.manage_guild or i.guild.owner_id == i.id]
    async with request.app['database']() as db:
        rows = await db(
            """SELECT * FROM guild_subscriptions WHERE guild_id=ANY($1::BIGINT[])""",
            [i.id for i in valid_guilds],
        )
    for i in valid_guilds:
        i.premium = None
    if rows:
        for i in valid_guilds:
            for r in rows:
                if r['expiry_time'] is not None and r['expiry_time'] < dt.utcnow():
                    continue
                if i.id == r['guild_id']:
                    i.premium = dict(r)
                    break
    return {
        "guilds": valid_guilds,
    }


@routes.get(r"/guilds/{guild_id:\d+}")
@vbu.web.requires_login()
@template("guild_settings.htm.j2")
@vbu.web.add_discord_arguments()
async def guild_settings(request: Request):
    """
    The guild settings page for a given bot.
    """

    # Get the guild object
    guild_id = int(request.match_info.get("guild_id"))
    bot: vbu.Bot = request.app['bots']['bot']
    user_can_moderate, guild, member = await webutils.user_can_moderate_guild(request, guild_id)
    if not user_can_moderate:
        raise HTTPFound(location="/guilds")

    # Grab their current settings
    async with request.app['database']() as db:
        guild_rows = await db("SELECT * FROM guild_settings WHERE guild_id=$1 OR guild_id=0 ORDER BY guild_id DESC", guild_id)
        guild_subscriptions = await db("SELECT * FROM guild_subscriptions WHERE guild_id=$1", guild_id)
        guild_templates = await utils.Template.fetch_all_templates_for_guild(db, guild_id, fetch_fields=True)

    # Upgrade the guild so we can see if the bot's in it
    try:
        upgraded_guild = await guild.fetch_guild()
    except AttributeError:
        upgraded_guild = None

    # See if we want to invite the bot
    if upgraded_guild is None and not guild_templates:
        raise HTTPFound(location=bot.get_invite_link(guild_id=guild_id))

    # Return the guild data
    return {
        "guild": guild,
        "bot_in_guild": upgraded_guild,
        "guild_settings": guild_rows[0],
        "templates": guild_templates,
        "has_premium": guild_subscriptions,
        "CommandProcessor": utils.CommandProcessor,  # Throw in this whole class so we can use it in the template
    }


@routes.get(r"/guilds/{guild_id:\d+}/templates/{template_id:[a-zA-Z0-9\-]+?}")
@vbu.web.requires_login()
@template("template_edit.htm.j2")
@vbu.web.add_discord_arguments()
async def template_edit(request: Request):
    """
    The edit template page for the bot.
    """

    return await get_template_data(request)


# @routes.get(r"/guilds/{guild_id:\d+}/templates/{template_id:[a-zA-Z0-9\-]+?}/advanced")
# @vbu.web.requires_login()
# @template("advanced_template_edit.htm.j2")
# @vbu.web.add_discord_arguments()
# async def advanced_template_edit(request: Request):
#     """
#     The edit template page for the bot.
#     """

#     return await get_template_data(request)


async def get_template_data(request: Request):

    # Get the template object
    template_id = request.match_info.get("template_id")
    async with request.app['database']() as db:
        template = await utils.Template.fetch_template_by_id(db, template_id, fetch_fields=True)
        if template:
            guild_rows = await db("SELECT * FROM guild_settings WHERE guild_id=$1 OR guild_id=0 ORDER BY guild_id DESC", template.guild_id)
    if not template:
        raise HTTPFound(location="/guilds")

    # See if they can moderate this template
    guild_id = template.guild_id
    bot: vbu.Bot = request.app['bots']['bot']
    user_can_moderate, guild, member = await webutils.user_can_moderate_guild(request, guild_id)
    if not user_can_moderate:
        raise HTTPFound(location=f"/guilds/{template.guild_id}")

    # Grab the guild object
    try:
        guild_object = await bot.fetch_guild(guild_id)
    except discord.HTTPException:
        raise HTTPFound(location=bot.get_invite_link(guild_id=guild_id))
    channels = await guild_object.fetch_channels()
    guild_object._channels = {i.id: i for i in channels}
    roles = await guild_object.fetch_roles()
    guild_object._roles = {i.id: i for i in roles}

    # Return the guild data
    return {
        "template": template,
        "guild": guild_object,
        "guild_settings": guild_rows[0],
        "CommandProcessor": utils.CommandProcessor,  # Throw in this whole class so we can use it in the template
    }
