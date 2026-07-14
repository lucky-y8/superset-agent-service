"""Shared SQLAlchemy declarative base for persistent models.

为项目中的持久化模型提供共享的 SQLAlchemy 声明式基类。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class inherited by all ORM models.

    所有 ORM 模型共同继承的声明式基类。
    """

    pass
