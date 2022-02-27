from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, null
from sqlalchemy.orm import declarative_base

db = declarative_base()
metadata = sa.MetaData()

card_ruling = sa.Table(
    "card_rulings",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("card_name", String(50)),
    Column("ruling_text", String(400)),
    Column("author", String(30)),
    Column("created_ts", DateTime, default=datetime.utcnow())
)

pick_table = sa.Table(
    "picks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("heirloom0", String(30)),
    Column("heirloom1", String(30)),
    Column("heirloom2", String(30)),
    Column("path0", String(30)),
    Column("path1", String(30)),
    Column("path2", String(30)),
    Column("creator_id", BigInteger),
    Column("guild_id", BigInteger),
    Column("channel_id", BigInteger),
    Column("message_id", BigInteger),
    Column("created_ts", DateTime, default=datetime.utcnow()),
    Column("end_ts", DateTime)
)

pick_submission_table = sa.Table(
    "pick_submissions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("pick_id", Integer, sa.ForeignKey("picks.id")),
    Column("user_id", BigInteger, nullable=False),
    Column("heirloom", String(30), nullable=False),
    Column("path1", String(30), nullable=False),
    Column("path2", String(30)),
    Column("path3", String(30), default=null()),
)
