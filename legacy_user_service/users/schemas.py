from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class UserBase(BaseModel):
    """用户基础模型"""
    email: str
    name: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None

class UserCreate(UserBase):
    """用户创建模型"""
    password: str = Field(..., min_length=6, description="密码至少6位")

class UserUpdate(BaseModel):
    """用户更新模型"""
    name: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None
    is_active: Optional[bool] = None

class UserLogin(BaseModel):
    """用户登录模型"""
    email: EmailStr
    password: str

class UserResponse(UserBase):
    """用户响应模型"""
    id: int
    is_active: bool
    login_count: int
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    """令牌模型"""
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    """令牌数据模型"""
    email: Optional[str] = None

