from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import dataclass

from typing_extensions import Self
import aiohttp

if TYPE_CHECKING:
    from discord.ext import vbu


@dataclass
class GuildPerks:
    """
    A class for the perks of a given guild.
    """

    guild_id: int
    max_template_count: int
    max_field_count: int
    max_profile_count: int
    is_premium: bool = False

    @classmethod
    async def fetch(cls, db: vbu.Database, guild_id: int) -> Self:
        """
        Fetches the perks of a given guild.
        """

        # Has overrides for settings
        guild_settings = await db.call(
            """
            SELECT
                *
            FROM
                guild_settings
            WHERE
                guild_id = $1
            OR
                guild_id = 0
            ORDER BY
                guild_id
            DESC
            """,
            guild_id,
        )

        # Contains premium subscriptions
        async with aiohttp.ClientSession() as session:
            try:
                resp = await session.get(
                    "https://voxelfox.co.uk/api/portal/check",
                    params={
                        "guild_id": guild_id,
                        "product_id": "ff547b6b-731c-4c5d-aff9-672ee628936c",
                    },
                    timeout=1.5,
                )
                data = await resp.json()
            except Exception:
                guild_subscription = False
            else:
                guild_subscription = data['result']
        perks = (
            SUBSCRIBED_GUILD_PERKS
            if guild_subscription
            else NO_GUILD_PERKS
        )
        return cls(
            guild_id=guild_id,
            max_template_count=max(
                guild_settings[0]['max_template_count'],
                perks.max_template_count,
                NO_GUILD_PERKS.max_template_count,
            ),
            max_field_count=max(
                guild_settings[0]['max_template_field_count'],
                perks.max_field_count,
                NO_GUILD_PERKS.max_field_count,
            ),
            max_profile_count=max(
                guild_settings[0]['max_template_profile_count'],
                perks.max_profile_count,
                NO_GUILD_PERKS.max_profile_count,
            ),
            is_premium=perks.is_premium,
        )


NO_GUILD_PERKS = GuildPerks(
    guild_id=0,
    max_template_count=3,
    max_field_count=10,
    max_profile_count=3,
    is_premium=False,
)
SUBSCRIBED_GUILD_PERKS = GuildPerks(
    guild_id=0,
    max_template_count=15,
    max_field_count=20,
    max_profile_count=30,
    is_premium=True,
)
