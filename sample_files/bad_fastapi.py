# Sample FastAPI file with intentional violations
from fastapi import FastAPI
from typing import Dict

app = FastAPI()

# FAPI007: route on 'app' directly instead of APIRouter
# FAPI001: sync def instead of async def
# FAPI002: uppercase in path
@app.get("/GetUser/{userId}")
def get_user(userId: str) -> Dict:   # PY005: return type is too loose
    print(f"Getting user {userId}")  # PY003: print
    return {"userId": userId}

# FAPI005: CORS wildcard
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],             # FAPI005: wildcard origin
    allow_methods=["*"],
)

# FAPI006: non-HTTP exception raised in route
@app.post("/CreateUser")
def create_user(data: dict):         # FAPI004: plain dict instead of Pydantic
    if not data.get("name"):
        raise ValueError("Name required")  # FAPI006: use HTTPException
    return data
