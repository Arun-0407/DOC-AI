from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = ""

    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 720

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024

    BTP_CLIENT_ID: str = ""
    BTP_CLIENT_SECRET: str = ""
    BTP_TOKEN_URL: str = ""
    BTP_AI_API_URL: str = ""
    BTP_RESOURCE_GROUP: str = "default"
    BTP_DEPLOYMENT_ID: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    SAP_DOC_API_URL: str = ""
    SAP_DOC_API_USER: str = ""
    SAP_DOC_API_PASSWORD: str = ""
    SAP_DOC_API_CLIENT: str = "120"
    SAP_DOC_API_VERIFY_SSL: bool = True
    SAP_DOC_API_TIMEOUT: int = 120
    SAP_CACHE_MINUTES: int = 30

    # Legacy RFC bridge, off by default
    SAP_RFC_ENABLED: bool = False
    SAP_HOST: str = ""
    SAP_SYSNR: str = "00"
    SAP_CLIENT: str = "120"
    SAP_USER: str = ""
    SAP_PASSWORD: str = ""
    SAP_LANG: str = "EN"
    SAPNWRFC_HOME: str = ""
    RFC_INI: str = ""
    SAP_BRIDGE_PORT: int = 5001
    SAP_BRIDGE_URL: str = "http://127.0.0.1:5001"

    # Legacy ADT connection, off by default
    SAP_ADT_ENABLED: bool = False
    SAP_S4_HOST: str = ""
    SAP_S4_CLIENT: str = "120"
    SAP_S4_AUTH_MODE: str = "basic"
    SAP_S4_BASIC_USER: str = ""
    SAP_S4_BASIC_PASS: str = ""
    SAP_S4_OAUTH_TOKEN_URL: str = ""
    SAP_S4_OAUTH_CLIENT_ID: str = ""
    SAP_S4_OAUTH_CLIENT_SECRET: str = ""
    SAP_S4_VERIFY_SSL: bool = True
    SAP_S4_TIMEOUT: int = 60
    SAP_S4_MAX_DEPTH: int = 3

    # ── NEW: BTP Destination Service (for connect-destination endpoint) ──────
    SAP_BTP_DESTINATION_NAME: str = ""
    SAP_BTP_DESTINATION_SERVICE_URL: str = ""

    @property
    def sap_doc_api_enabled(self) -> bool:
       
        return bool(self.SAP_DOC_API_URL)

    @property
    def btp_enabled(self) -> bool:
        return bool(self.BTP_CLIENT_ID and self.BTP_DEPLOYMENT_ID)

    @model_validator(mode="after")
    def validate_required(self) -> "Settings":
        missing = [name for name in ("DATABASE_URL", "JWT_SECRET") if not getattr(self, name)]
        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")
        if len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        if self.SAP_RFC_ENABLED and not self.SAPNWRFC_HOME:
            raise ValueError("SAPNWRFC_HOME is required when SAP_RFC_ENABLED is true")
        return self


settings = Settings()