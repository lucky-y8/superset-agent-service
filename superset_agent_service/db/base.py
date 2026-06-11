"""Shared SQLAlchemy declarative base for future persistent models.

供未来持久化模型共享的 SQLAlchemy 声明式基类。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class inherited by all future ORM models.

    所有未来 ORM 模型共同继承的基类。
    """

    pass
