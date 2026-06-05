# models.py

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship, declared_attr, backref
from sqlalchemy.sql import func

from legacy_user_service.extensions.db_extension import Base


class User(Base):
    """
    User 模型，对应数据库中的 'users' 表。
    包含用户的基本信息、认证信息、登录统计和时间戳。
    """
    __tablename__ = "ab_user" # 定义表名为 'users'

    id = Column(Integer, primary_key=True, index=True, comment='用户唯一ID')
    email = Column(String, unique=True, index=True, nullable=False, comment='用户邮箱，唯一且非空，作为登录凭证')
    phone_number = Column(String, unique=True, index=True, nullable=True, comment='用户手机号，可选，唯一')
    name = Column(String, index=True, nullable=True, comment='用户名称，可选')
    hashed_password = Column(String, nullable=False, comment='用户密码的哈希值')
    is_active = Column(Boolean, default=True, comment='用户账户是否活跃状态')
    login_count = Column(Integer, default=0, nullable=False, comment='用户登录次数')
    last_login_at = Column(DateTime, nullable=True, comment='用户上次登录时间')
    created_at = Column(DateTime, default=func.now(), nullable=False, comment='用户创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False, comment='用户最后更新时间')
    bio = Column(Text, nullable=True, comment='用户个人介绍或简介')


    # 如果用户可以有其他关联的实体，可以在这里使用 relationship 定义关系。
    # 例如：
    # items = relationship("Item", back_populates="owner")

    def __repr__(self):
        """
        定义对象的字符串表示，方便调试。
        """
        return f"<User(id={self.id}, email='{self.email}', name='{self.name if self.name else 'N/A'})>"

