import asyncio
import os
import sys
from timeit import default_timer as timer
from datetime import datetime

import aiopg.sa
import discord
import sqlalchemy as sa
from aiopg.sa import create_engine
from discord.ext import commands
from sqlalchemy import Column, Integer, BigInteger, String, DateTime
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql import Insert

from models.db import card_ruling, pick_table, pick_submission_table


async def create_tables(conn: aiopg.sa.SAConnection):
    await conn.execute(CreateTable(card_ruling, if_not_exists=True))
    await conn.execute(CreateTable(pick_table, if_not_exists=True))
    await conn.execute(CreateTable(pick_submission_table, if_not_exists=True))


class GloryBot(commands.Bot):
    db: aiopg.sa.Engine

    def __init__(self, *args, **kwargs):
        super(GloryBot, self).__init__(*args, **kwargs)

    async def on_ready(self):
        start = timer()
        self.db = await create_engine(os.environ["DATABASE_URL"])
        end = timer()

        print(f"Time to create db engine: {end - start}")
        async with self.db.acquire() as conn:
            await create_tables(conn)

        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")


# Because Windows is terrible
if sys.version_info >= (3, 8) and sys.platform.lower().startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

bot = GloryBot(debug_guilds=[912427268339560528])
# bot = GloryBot()
for ext in ['cogs.cards']:
    bot.load_extension(ext)

# bot.register_command(discord.SlashCommand())

bot.run(os.environ["BOT_TOKEN"])
