import asyncio
import os
import sys
from timeit import default_timer as timer

import aiopg.sa
from aiopg.sa import create_engine
from discord.ext import commands
from sqlalchemy.schema import CreateTable

from models.db import CardRuling


async def create_table(engine: aiopg.sa.Engine):
    async with engine.acquire() as conn:
        conn: aiopg.sa.SAConnection
        await conn.execute(CreateTable(CardRuling.__table__, if_not_exists=True))


class GloryBot(commands.Bot):
    db: aiopg.sa.Engine

    def __init__(self, *args, **kwargs):
        super(GloryBot, self).__init__(*args, **kwargs)

    async def on_ready(self):
        start = timer()
        self.db = await create_engine(os.environ["DATABASE_URL"])
        print(CardRuling.__table__)
        end = timer()

        print(f"Time to create db engine: {end - start}")
        # await create_table(self.db)
        # async with self.db.acquire() as conn:
        #     print(f"Acquired test db connection {conn}")
        #     await conn.close()

        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")


# Because Windows is terrible
if sys.version_info >= (3, 8) and sys.platform.lower().startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# bot = GloryBot(debug_guilds=[912427268339560528])
bot = GloryBot()
for ext in ['cogs.cards']:
    bot.load_extension(ext)

bot.run(os.environ["BOT_TOKEN"])
