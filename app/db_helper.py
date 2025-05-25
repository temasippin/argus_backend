import asyncio
from asyncio.exceptions import TimeoutError

import asyncpg


class Database:
    def __init__(self):
        self.pool: asyncpg.Pool = None

    async def connect(self, dsn: str):
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=dsn,
                )
            except Exception as e:
                print(dsn, repr(e), flush=True)

    async def disconnect(self):
        if self.pool:
            try:
                await asyncio.wait_for(self.pool.close(), timeout=5)
            except TimeoutError:
                print("TimeoutError")
            self.pool = None
