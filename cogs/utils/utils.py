from typing import Any, Tuple
import random
from urllib.parse import urlparse, parse_qs, urlencode
import logging

import discord
from discord.ext import commands, vbu


__all__ = (
    'mention_command',
    'compare_embeds',
    'get_animal_name',
    'is_guild_advanced',
    'pad_field_prompt_value',
)


log = logging.getLogger("embed_utils")


def mention_command(command: commands.Command) -> str:
    """
    A function that returns a string that mentions a command.
    """

    command_id: int | None
    if (command_id := getattr(command, "id", None)) is None:
        return f"/{command.qualified_name}"
    return f"</{command.qualified_name}:{command_id}>"


def normalize_discord_cdn_url(url: str) -> str:
    """
    Remove Discord's dumb new em ex ih query params from a url.
    """

    parsed = urlparse(url)
    DISCORD_URLS = [
        "media.discordapp.net",
        "media.discordapp.com",
        "media.discord.com",
        "cdn.discordapp.net",
        "cdn.discordapp.com",
        "cdn.discord.com",
        "discordapp.net",
        "discordapp.com",
        "discord.com",
    ]
    if parsed.netloc.casefold() not in DISCORD_URLS:
        return url  # unchanged
    params: dict[str, list[str]] = parse_qs(parsed.query)
    params.pop("ex", None)
    params.pop("is", None)
    params.pop("hm", None)
    new_parsed = parsed._replace(query=urlencode(params))
    return new_parsed.geturl()


def compare_embeds(
        embed1: discord.Embed | Any, 
        embed2: discord.Embed | Any) -> bool:
    """
    Return whether or not two embeds share the same values.

    This will compare fields, the image, the description, and the title.
    """

    # Make sure both items are actually embeds first
    if not isinstance(embed1, discord.Embed) or not isinstance(embed2, discord.Embed):
        return False

    # Convert both to dicts to make comparison easier
    embed1_dict = embed1.to_dict()
    embed2_dict = embed2.to_dict()

    # Compare the title
    if (
            embed1_dict.get("title", "").strip()
            != embed2_dict.get("title", "").strip()):
        return False

    # Compare the description
    if (
            embed1_dict.get("description", "").strip()
            != embed2_dict.get("description", "").strip()):
        return False

    # Compare the image URL - we're not gonna compare the image
    # size etc becuase Novus doesn't set it but the API does
    if (
            (a := normalize_discord_cdn_url(embed1_dict.get("image", {}).get("url", "")).strip())
            != (b := normalize_discord_cdn_url(embed2_dict.get("image", {}).get("url", "")).strip())):
        log.info(f"{a} {b}")
        return False

    # Iterate through the fields and make sure each of the value,
    # inline, and name are the same
    field_zip = zip(
        embed1_dict.get("fields", list()),
        embed2_dict.get("fields", list())
    )
    for field1, field2 in field_zip:
        if field1["name"].strip() != field2["name"].strip():
            return False
        if field1["value"].strip() != field2["value"].strip():
            return False
        if field1.get("inline", True) != field2.get("inline", True):
            return False

    # If we got here, then the embeds are the same
    return True


def get_animal_name() -> str:
    """
    Get a random name from the animals file.
    """

    with open("config/animals.txt") as f:
        animals = f.read().strip().splitlines()
    return random.choice(animals)


async def is_guild_advanced(db: vbu.Database, guild_id: int | None) -> bool:
    """
    Returns whether or not the guild associated with the given ID is set to
    advanced.
    """

    if guild_id is None:
        return False
    rows = await db.call(
        """
        SELECT
            advanced
        FROM
            guild_settings
        WHERE
            guild_id = $1
        """,
        guild_id,
    )
    return bool(rows[0]["advanced"]) if rows else False


def pad_field_prompt_value(
        prompt: str,
        value: str) -> Tuple[list[str], list[str]]:
    """
    Pad a prompt and value to lists of equal length, where the value is resized
    down to fit the size of the prompt.

    The prompt will be hard limited to 5 values. Anything given AFTER those
    5 values will be ignored.
    """

    prompt_split = prompt.strip().split("\n")
    value_split = value.strip().split("\n")

    # Truncate the prompt list to 5 values
    prompt_split = prompt_split[:5]

    # Change the length of the prompt and current value until they
    # work together
    while len(prompt_split) > len(value_split):
        # Pad out list
        value_split.append("")
    while len(prompt_split) < len(value_split):
        # Combine the last elements in the current_value list until it
        # matches the length of prompt_split
        value_split[-2] = f"{value_split[-2]}\n{value_split[-1]}"
        value_split.pop(-1)

    return prompt_split, value_split
