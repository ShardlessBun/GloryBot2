from datetime import datetime, timedelta
from typing import List

import sqlalchemy as sa
from sqlalchemy import Column, Integer, BigInteger, String, ForeignKey, DateTime, null
from sqlalchemy.orm import declarative_base

db = declarative_base()
metadata = sa.MetaData()

card_ruling = sa.Table(
    "card_rulings",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("card_name", String(100)),
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
    Column("path2", String(30), default=null()),
)

# class CardRuling(db):
#     """A ruling on a card's effects written by a designer"""
#     __tablename__ = "card_rulings"
#
#     id = Column(Integer, primary_key=True, autoincrement='auto')
#     card_name = Column(String(100))
#     ruling_text = Column(String(4000))
#     author = Column(String(30))
#     created_ts = Column(DateTime, default=datetime.utcnow())
