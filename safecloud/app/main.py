from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import alarms, commands, dashboard, devices, telemetry
from app.core.config import get_settings
from app.db.init_db import init_db


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Industrial environment monitoring and control cloud prototype.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "service": settings.app_name}


app.include_router(devices.router, prefix=settings.api_prefix)
app.include_router(telemetry.router, prefix=settings.api_prefix)
app.include_router(alarms.router, prefix=settings.api_prefix)
app.include_router(commands.router, prefix=settings.api_prefix)
app.include_router(dashboard.router, prefix=settings.api_prefix)
