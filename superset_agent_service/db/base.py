"""Shared SQLAlchemy declarative base for future persistent models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
