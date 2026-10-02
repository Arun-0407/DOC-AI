"""
Settings API — save & test SAP BTP AI Core credentials at runtime.
Credentials are persisted to the .env file so they survive restarts.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os, httpx
from pathlib import Path

router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class AiConfig(BaseModel):
    btp_client_id: str = ""
    btp_client_secret: str = ""
    btp_token_url: str = ""
    btp_ai_api_url: str = ""
    btp_resource_group: str = "default"
    btp_deployment_id: str = ""


def _read_env() -> dict:
    """Parse .env file into a dict."""
    env: dict = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _write_env(env: dict):
    """Write dict back to .env file."""
    lines = [f"{k}={v}" for k, v in env.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


@router.get("/ai-config")
async def get_ai_config():
    """Return current AI config (secrets masked)."""
    env = _read_env()
    return {
        "btp_client_id": env.get("BTP_CLIENT_ID", ""),
        "btp_client_secret": "••••••••" if env.get("BTP_CLIENT_SECRET") else "",
        "btp_token_url": env.get("BTP_TOKEN_URL", ""),
        "btp_ai_api_url": env.get("BTP_AI_API_URL", ""),
        "btp_resource_group": env.get("BTP_RESOURCE_GROUP", "default"),
        "btp_deployment_id": env.get("BTP_DEPLOYMENT_ID", ""),
    }


@router.post("/ai-config")
async def save_ai_config(config: AiConfig):
    """Save AI credentials to .env file and update live settings."""
    env = _read_env()

    if config.btp_client_id:
        env["BTP_CLIENT_ID"] = config.btp_client_id
    if config.btp_client_secret and config.btp_client_secret != "••••••••":
        env["BTP_CLIENT_SECRET"] = config.btp_client_secret
    if config.btp_token_url:
        env["BTP_TOKEN_URL"] = config.btp_token_url
    if config.btp_ai_api_url:
        env["BTP_AI_API_URL"] = config.btp_ai_api_url
    if config.btp_resource_group:
        env["BTP_RESOURCE_GROUP"] = config.btp_resource_group
    if config.btp_deployment_id:
        env["BTP_DEPLOYMENT_ID"] = config.btp_deployment_id

    _write_env(env)

    # Also update live settings so no restart is needed
    from app.config import settings
    if config.btp_client_id:
        settings.BTP_CLIENT_ID = config.btp_client_id
    if config.btp_client_secret and config.btp_client_secret != "••••••••":
        settings.BTP_CLIENT_SECRET = config.btp_client_secret
    if config.btp_token_url:
        settings.BTP_TOKEN_URL = config.btp_token_url
    if config.btp_ai_api_url:
        settings.BTP_AI_API_URL = config.btp_ai_api_url
    if config.btp_resource_group:
        settings.BTP_RESOURCE_GROUP = config.btp_resource_group
    if config.btp_deployment_id:
        settings.BTP_DEPLOYMENT_ID = config.btp_deployment_id

    return {"success": True, "message": "AI configuration saved successfully."}


@router.post("/ai-test")
async def test_ai_config(config: AiConfig):
    """Test the AI connection by fetching an OAuth token from BTP."""
    client_id = config.btp_client_id
    client_secret = config.btp_client_secret
    token_url = config.btp_token_url

    # Fall back to saved .env values if fields are empty/masked
    env = _read_env()
    if not client_id:
        client_id = env.get("BTP_CLIENT_ID", "")
    if not client_secret or client_secret == "••••••••":
        client_secret = env.get("BTP_CLIENT_SECRET", "")
    if not token_url:
        token_url = env.get("BTP_TOKEN_URL", "")

    if not all([client_id, client_secret, token_url]):
        raise HTTPException(status_code=400, detail="Please provide Client ID, Client Secret, and Token URL.")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                token_url,
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code == 200 and "access_token" in resp.json():
            return {"success": True, "message": "Connection successful! Token obtained from BTP."}
        else:
            return {"success": False, "message": f"BTP returned HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"success": False, "message": f"Connection error: {str(e)}"}
