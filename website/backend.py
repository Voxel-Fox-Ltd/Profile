from aiohttp.web import HTTPFound, Request, Response, RouteTableDef, json_response
from voxelbotutils import web as webutils
import aiohttp_session
import discord

from cogs import utils as localutils


routes = RouteTableDef()


@routes.get("/login_processor")
async def login_processor(request: Request):
    """
    Page the discord login redirects the user to when successfully logged in with Discord.
    """

    v = await webutils.process_discord_login(request)
    if isinstance(v, Response):
        return HTTPFound(location="/")
    session = await aiohttp_session.get_session(request)
    return HTTPFound(location=session.pop("redirect_on_login", "/"))


@routes.get("/logout")
async def logout(request: Request):
    """
    Destroy the user's login session.
    """

    session = await aiohttp_session.get_session(request)
    session.invalidate()
    return HTTPFound(location="/")


@routes.get("/login")
async def login(request: Request):
    """
    Direct the user to the bot's Oauth login page.
    """

    return HTTPFound(location=webutils.get_discord_login_url(request, "/login_processor"))


@routes.post("/api/update_template")
async def update_template(request: Request):
    """
    The route that handles the updating of the template metadata.
    """

    # Make sure the user is logged in
    session = await aiohttp_session.get_session(request)
    if not session.get("user_id"):
        return json_response({"error": "Not logged in."}, status=401)

    # Try and read the POST data from the user
    required_fields = {"template_id", "verification_channel_id", "archive_channel_id", "role_id", "max_profile_count"}
    field_converters = {"max_profile_count": int}
    try:
        data = await request.json()
        data = {i: o.strip() or None for i, o in data.items()}
        for f in required_fields:
            data.setdefault(f, None)
            if f in field_converters:
                data[f] = field_converters[f](data[f])
    except ValueError:
        return json_response({"error": "Couldn't validate the given POST data."}, status=400)
    except Exception:
        return json_response({"error": "Could not read POST data."}, status=400)

    # Now we want to check things with the database
    async with request.app['database']() as db:

        # Make sure the template exists
        template = await localutils.Template.fetch_template_by_id(db, data['template_id'], fetch_fields=False)
        if not template:
            return json_response({"error": "Template does not exist."}, status=400)

        # Make sure the user is editing a template that they have permission to edit
        try:
            guild = await request.app['bots']['bot'].fetch_guild(template.guild_id)
        except discord.HTTPException:
            return json_response({"error": "Bot not in guild."}, status=401)
        try:
            member = await guild.fetch_member(session.get("user_id"))
        except discord.HTTPException:
            return json_response({"error": "User not in guild."}, status=401)
        if not member.guild_permissions.manage_guild:
            return json_response({"error": "Member cannot manage guild."}, status=401)

        # Update the template
        updated_rows = await db(
            """UPDATE template SET verification_channel_id=$2, archive_channel_id=$3, role_id=$4,
            max_profile_count=$5 WHERE template_id=$1""",
            data['template_id'], data['verification_channel_id'], data['archive_channel_id'],
            data['role_id'], data['max_profile_count'],
        )

    # Return
    return json_response({"error": ""}, status=200)


@routes.post("/api/update_template_field")
async def update_template_field(request: Request):
    """
    The route that handles the updating of the template metadata.
    """

    # Make sure the user is logged in
    session = await aiohttp_session.get_session(request)
    if not session.get("user_id"):
        return json_response({"error": "Not logged in."}, status=401)

    # Try and read the POST data from the user
    required_fields = {"field_id", "name", "prompt", "timeout", "type", "optional"}
    field_converters = {"timeout": int, "optional": bool}
    try:
        data = await request.json()
        data = {i: o.strip() or None for i, o in data.items()}
        for f in required_fields:
            data.setdefault(f, None)
            if f in field_converters:
                data[f] = field_converters[f](data[f])
    except ValueError:
        return json_response({"error": "Couldn't validate the given POST data."}, status=400)
    except Exception:
        return json_response({"error": "Could not read POST data."}, status=400)

    # Now we want to check things with the database
    async with request.app['database']() as db:

        # Make sure the template exists
        field_rows = await db("""SELECT * FROM field WHERE field_id=$1""", data['field_id'])
        if not field_rows:
            return json_response({"error": "Field does not exist."}, status=400)
        field = localutils.Field(**field_rows[0])
        template = await localutils.Template.fetch_template_by_id(db, field.template_id, fetch_fields=False)
        if not template:
            return json_response({"error": "Template does not exist."}, status=400)

        # Make sure the user is editing a template that they have permission to edit
        try:
            guild = await request.app['bots']['bot'].fetch_guild(template.guild_id)
        except discord.HTTPException:
            return json_response({"error": "Bot not in guild."}, status=401)
        try:
            member = await guild.fetch_member(session.get("user_id"))
        except discord.HTTPException:
            return json_response({"error": "User not in guild."}, status=401)
        if not member.guild_permissions.manage_guild:
            return json_response({"error": "Member cannot manage guild."}, status=401)

        # Update the template
        updated_rows = await db(
            """UPDATE field SET name=$2, prompt=$3, timeout=$4, field_type=$5,
            optional=$6 WHERE field_id=$1""",
            data['field_id'], data['name'], data['prompt'], data['timeout'],
            data['type'], data['optional'],
        )

    # Return
    return json_response({"error": ""}, status=200)
