from datetime import timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from legacy_user_service.users.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    Token
)
from legacy_user_service.users.crud import UserCRUD
from legacy_user_service.users.security import verify_password, create_access_token
from legacy_user_service.users.dependencies import get_db, get_current_active_user
from legacy_user_service.models.users import User
from legacy_user_service.config import settings

# 创建路由器
router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
        user: UserCreate,
        db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    # 检查邮箱是否已存在
    existing_user = await UserCRUD.get_user_by_email(db, email=user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # 检查手机号是否已存在（如果提供了手机号）
    if user.phone_number:
        existing_phone = await UserCRUD.get_user_by_phone(db, phone_number=user.phone_number)
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )

    # 创建用户
    db_user = await UserCRUD.create_user(db, user)
    return db_user


@router.post("/login", response_model=Token)
async def login_user(
        user_credentials: UserLogin,
        db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    user = await UserCRUD.get_user_by_email(db, email=user_credentials.email)
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is inactive"
        )

    # 更新登录信息
    await UserCRUD.update_login_info(db, user)

    # 创建访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
        current_user: User = Depends(get_current_active_user)
):
    """获取当前用户信息"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
        user_update: UserUpdate,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
):
    """更新当前用户信息"""
    # 如果更新手机号，检查是否已存在
    if user_update.phone_number:
        existing_phone = await UserCRUD.get_user_by_phone(db, phone_number=user_update.phone_number)
        if existing_phone and existing_phone.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )

    updated_user = await UserCRUD.update_user(db, current_user.id, user_update)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return updated_user


@router.get("/", response_model=List[UserResponse])
async def get_users(
        skip: int = Query(0, ge=0, description="跳过的记录数"),
        limit: int = Query(100, ge=1, le=1000, description="返回的记录数"),
        active_only: bool = Query(True, description="只返回活跃用户"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
):
    """获取用户列表（需要认证）"""
    users = await UserCRUD.get_users(db, skip=skip, limit=limit, active_only=active_only)
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
        user_id: int,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
):
    """根据ID获取用户信息"""
    user = await UserCRUD.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
        user_id: int,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
):
    """停用用户账户"""
    user = await UserCRUD.deactivate_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.patch("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
        user_id: int,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
):
    """激活用户账户"""
    user = await UserCRUD.activate_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


