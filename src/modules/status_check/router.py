from fastapi import APIRouter

router = APIRouter(
    prefix="/status",
    tags=["Status Check"],
)

@router.get(
    ""
)
async def health_check():
    return { "status": "ok" }