from fastapi import APIRouter
from legacy_user_service.users import api as user_api

api_router = APIRouter()

api_router.include_router(user_api.router)


