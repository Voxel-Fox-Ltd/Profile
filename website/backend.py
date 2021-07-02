from datetime import datetime as dt

import aiohttp
from aiohttp.web import HTTPFound, Request, Response, RouteTableDef
from voxelbotutils import web as webutils
import aiohttp_session


routes = RouteTableDef()


def verify_vfl_auth_header(request: Request):
    """
    Verifies that the given VFL auth header is correct.
    """

    auth = request.headers['Authorization']
    return auth.strip() == request.app['config']['payments']['authorization']


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


@routes.post('/unsubscribe')
async def unsubscribe(request: Request):
    """
    Handles incomming webhooks from Voxel Fox for the PayPal purchase IPN
    """

    # Get our data
    data = await request.json()
    product_name = data['product_name']
    user_session = await aiohttp_session.get_session(request)

    # Process subscription
    if product_name != "Profile Premium":
        raise Exception("Invalid product_name")

    # Grab the cancel url
    async with request.app['database']() as db:
        rows = await db("SELECT * FROM guild_subscriptions WHERE guild_id=$1", int(data['guild_id']))

    # See if we're the right user
    if user_session['user_id'] != rows[0]['user_id']:
        raise Exception("Invalid user ID")

    # Send the POST request
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": request.app['config']['payments']['authorization']}
        cancel_url = rows[0]['cancel_url']
        json = {
            "product_name": product_name,
            "cancel_url": cancel_url,
        }
        async with session.post("https://voxelfox.co.uk/webhooks/cancel_subscription", json=json, headers=headers) as r:
            body = await r.read()
            return Response(body=body)

    # And done
    return Response(status=200)


@routes.post('/webhooks/voxelfox/payment')
async def purchase_complete(request: Request):
    """
    Handles incomming webhooks from Voxel Fox for the PayPal purchase IPN
    """

    # Verify the header
    if not verify_vfl_auth_header(request):
        return Response(status=401)

    # Get our data
    data = await request.json()
    product_name = data['product_name']
    user_id = int(data['discord_user_id'])
    guild_id = int(data['discord_guild_id'])
    discord_channel_send_text = None
    bot = request.app['bots']['bot']

    # Process subscription
    if product_name == "Profile Premium":
        if data['refund']:
            expiry_time = dt.utcnow()
            premium_subscription_delete_url = None
        else:
            expiry_time = data['subscription_expiry_time']
            premium_subscription_delete_url = data['subscription_delete_url']
            if expiry_time:
                expiry_time = dt.fromtimestamp(expiry_time)
        async with request.app['database']() as db:
            await db(
                """INSERT INTO guild_subscriptions (guild_id, user_id, cancel_url, expiry_time)
                VALUES ($1, $2, $3, $4) ON CONFLICT (guild_id) DO UPDATE SET
                cancel_url=excluded.cancel_url, expiry_time=excluded.expiry_time""",
                guild_id, user_id, premium_subscription_delete_url, expiry_time,
            )

        # Work out what to send to Discord
        if data['refund']:
            discord_channel_send_text = f"<@{user_id}>'s subscription to Profile Premium was refunded."
        elif expiry_time:
            discord_channel_send_text = f"<@{user_id}> cancelled their subscription to Profile Premium. It will expire on {expiry_time.strftime('%c')}."
        else:
            discord_channel_send_text = f"<@{user_id}> subscribed to Profile Premium."

    # Send data to channel
    channel_id = request.app['config']['payments']['notification_channel_id']
    if channel_id and discord_channel_send_text:
        try:
            channel = await bot.fetch_channel(channel_id)
            await channel.send(discord_channel_send_text)
        except Exception:
            pass

    # And done
    return Response(status=200)
