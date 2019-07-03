from typing import List
from logging import getLogger

from asyncpg import Connection, create_pool as _create_pool


LOGGER = getLogger('profilebot.db')


class DatabaseConnection(object):

    config = None
    pool = None

    def __init__(self, connection:Connection=None):
        self.conn = connection

    @classmethod
    async def create_pool(cls, config:dict):
        cls.config = config
        cls.pool = await _create_pool(**config)

    async def __aenter__(self):
        self.conn = await self.pool.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.pool.release(self.conn)
        self.conn = None
        del self

    async def __call__(self, sql:str, *args) -> List[dict]:
        '''Runs a line of SQL using the internal database'''

        # Runs the SQL
        LOGGER.debug(f"Running SQL: {sql} ({args!s})")
        x = await self.conn.fetch(sql, *args)

        # If it got something, return the dict, else None
        if x:
            return x
        if 'select' in sql.casefold() or 'returning' in sql.casefold():
            return []
        return None
