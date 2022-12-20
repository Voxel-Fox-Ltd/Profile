from aiohttp.web import HTTPFound, Request, Response, RouteTableDef, json_response
from voxelbotutils import web as webutils
import aiohttp_session
import discord

from cogs import utils as localutils


routes = RouteTableDef()


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
    required_fields = {"verification_channel_id", "archive_channel_id", "role_id", "max_profile_count"}
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
        template = None
        if data.get("template_id"):
            template = await localutils.Template.fetch_template_by_id(db, data['template_id'], fetch_fields=False)
            if not template:
                return json_response({"error": "Template does not exist."}, status=400)

        # Make sure the user is editing a template that they have permission to edit
        try:
            assert template is not None
        except AssertionError:
            return json_response({"error": "Failed to get template for whatever reason."}, status=401)
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
        if template:
            updated_rows = await db(
                """UPDATE template SET verification_channel_id=$2, archive_channel_id=$3, role_id=$4,
                max_profile_count=$5 WHERE template_id=$1 RETURNING *""",
                data['template_id'], data['verification_channel_id'], data['archive_channel_id'],
                data['role_id'], data['max_profile_count'],
            )
        else:
            updated_rows = await db(
                """INSERT INTO template (template_id) VALUES (GEN_RANDOM_UUID()) RETURNING *""",
            )

    # Return
    ret_data = dict(updated_rows[0])
    ret_data['template_id'] = str(ret_data['template_id'])
    return json_response({"error": "", "data": ret_data}, status=200)


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
    required_fields = {"template_id", "name", "prompt", "timeout", "type", "optional"}
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
        field = None
        if data.get('field_id'):
            field_rows = await db("""SELECT * FROM fields WHERE field_id=$1""", data['field_id'])
            if not field_rows:
                return json_response({"error": "Field does not exist."}, status=400)
            field = localutils.Field(**field_rows[0])
        template = await localutils.Template.fetch_template_by_id(db, field.template_id if field else data['template_id'], fetch_fields=False)
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
        if field:
            updated_rows = await db(
                """UPDATE field SET name=$2, prompt=$3, timeout=$4, field_type=$5,
                optional=$6 WHERE field_id=$1 RETURNING *""",
                data['field_id'], data['name'], data['prompt'], data['timeout'],
                data['type'], data['optional'],
            )
        else:
            updated_rows = await db(
                """INSERT INTO field (field_id, name, prompt, timeout, field_type, optional,
                template_id, index) VALUES (GEN_RANDOM_UUID(), $1, $2, $3, $4, $5, $6,
                COALESCE((SELECT MAX(index) FROM fields WHERE template_id=$6) + 1, 0))
                RETURNING *""",
                data['name'], data['prompt'], data['timeout'],
                data['type'], data['optional'], template.template_id,
            )

    # Return
    ret_data = dict(updated_rows[0])
    ret_data['field_id'] = str(ret_data['field_id'])
    ret_data['template_id'] = str(ret_data['template_id'])
    return json_response({"error": "", "data": ret_data}, status=200)


@routes.delete("/api/update_template")
async def update_template_delete(request: Request):
    """
    A route for handling deleting a template.
    """

    # Make sure the user is logged in
    session = await aiohttp_session.get_session(request)
    if not session.get("user_id"):
        return json_response({"error": "Not logged in."}, status=401)

    # Try and read the POST data from the user
    try:
        data = await request.json()
        template_id = data['template_id']
    except ValueError:
        return json_response({"error": "Couldn't validate the given POST data."}, status=400)
    except Exception:
        return json_response({"error": "Could not read POST data."}, status=400)

    # Now we want to check things with the database
    async with request.app['database']() as db:

        # Make sure the template exists
        template = await localutils.Template.fetch_template_by_id(db, template_id, fetch_fields=False)
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

        # Delete the template
        await db("""DELETE FROM template WHERE template_id=$1""", template.template_id)

    # Return
    return json_response({"error": ""}, status=200)


@routes.delete("/api/update_template_field")
async def update_template_field_delete(request: Request):
    """
    The route that handles the updating of the template metadata.
    """

    # Make sure the user is logged in
    session = await aiohttp_session.get_session(request)
    if not session.get("user_id"):
        return json_response({"error": "Not logged in."}, status=401)

    # Try and read the POST data from the user
    try:
        data = await request.json()
        field_id = data['field_id']
    except ValueError:
        return json_response({"error": "Couldn't validate the given POST data."}, status=400)
    except Exception:
        return json_response({"error": "Could not read POST data."}, status=400)

    # Now we want to check things with the database
    async with request.app['database']() as db:

        # Make sure the template exists
        field_rows = await db("""SELECT * FROM fields WHERE field_id=$1""", field_id)
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
            """UPDATE field SET deleted=true WHERE field_id=$1""",
            field_id,
        )

    # Return
    return json_response({"error": ""}, status=200)
