from typing import Any, AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from legacy_user_service.extensions.db_extension import AsyncSQLAlchemyExtension
from legacy_user_service.models.users import User
from legacy_user_service.users.security import verify_token
from legacy_user_service.users.crud import UserCRUD
from legacy_user_service.config import settings

# 初始化数据库扩展
print(settings.SQLALCHEMY_DATABASE_URI)
async_db = AsyncSQLAlchemyExtension(str(settings.SQLALCHEMY_DATABASE_URI))

# JWT安全
security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, Any]:
    """获取数据库会话"""
    async for session in async_db.get_db():
        yield session


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
) -> User:
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    email = verify_token(token)
    if email is None:
        raise credentials_exception

    user = await UserCRUD.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
        current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

