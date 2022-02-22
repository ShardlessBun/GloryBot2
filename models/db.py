from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base

db = declarative_base()


class CardRuling(db):
    """A ruling on a card's effects written by a designer"""
    __tablename__ = "card_rulings"

    id = Column(Integer, primary_key=True, autoincrement='auto')
    card_name = Column(String(100))
    ruling_text = Column(String(1000))
    author = Column(String(30))
    created_ts = Column(DateTime, default=datetime.utcnow())

