from fastapi import HTTPException, status

class UserAlreadyExistsError(HTTPException):
    """用户已存在异常"""
    def __init__(self, detail: str = "User already exists"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

class UserNotFoundError(HTTPException):
    """用户未找到异常"""
    def __init__(self, detail: str = "User not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )

class InvalidCredentialsError(HTTPException):
    """无效凭据异常"""
    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

class InactiveUserError(HTTPException):
    """用户未激活异常"""
    def __init__(self, detail: str = "User account is inactive"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
