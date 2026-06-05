from datetime import datetime, timezone
from typing import Optional, List, Any, Coroutine, Sequence

from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, Row, RowMapping
from legacy_user_service.models.users import User
from legacy_user_service.users.schemas import UserCreate, UserUpdate
from legacy_user_service.users.security import get_password_hash


class UserCRUD:
    """用户CRUD操作类"""

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: EmailStr) -> Optional[User]:
        """根据邮箱获取用户"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_phone(db: AsyncSession, phone_number: str) -> Optional[User]:
        """根据手机号获取用户"""
        result = await db.execute(select(User).where(User.phone_number == phone_number))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(db: AsyncSession, user: UserCreate) -> User:
        """创建用户"""
        hashed_password = get_password_hash(user.password)
        db_user = User(
            email=user.email,
            name=user.name,
            phone_number=user.phone_number,
            bio=user.bio,
            hashed_password=hashed_password,
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user

    @staticmethod
    async def update_user(db: AsyncSession, user_id: int, user_update: UserUpdate) -> Optional[User]:
        """更新用户信息"""
        # 构建更新数据字典，排除None值
        update_data = {
            k: v for k, v in user_update.model_dump().items()
            if v is not None
        }

        if not update_data:
            return await UserCRUD.get_user_by_id(db, user_id)

        # 添加更新时间
        update_data["updated_at"] = datetime.now(timezone.utc)

        await db.execute(
            update(User).where(User.id == user_id).values(**update_data)
        )
        await db.commit()
        return await UserCRUD.get_user_by_id(db, user_id)

    @staticmethod
    async def update_login_info(db: AsyncSession, user: User) -> None:
        """更新登录信息"""
        user.login_count += 1
        user.last_login_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)

    @staticmethod
    async def get_users(
            db: AsyncSession,
            skip: int = 0,
            limit: int = 100,
            active_only: bool = True
    ) -> Sequence[User]:
        """获取用户列表"""
        query = select(User)
        if active_only:
            query = query.where(User.is_active == True)
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def deactivate_user(db: AsyncSession, user_id: int) -> Optional[User]:
        """停用用户账户"""
        return await UserCRUD.update_user(
            db, user_id, UserUpdate(is_active=False)
        )

    @staticmethod
    async def activate_user(db: AsyncSession, user_id: int) -> Optional[User]:
        """激活用户账户"""
        return await UserCRUD.update_user(
            db, user_id, UserUpdate(is_active=True)
        )

