from fastapi import APIRouter
from listening_ripples.users import api as user_api

api_router = APIRouter()

api_router.include_router(user_api.router)
