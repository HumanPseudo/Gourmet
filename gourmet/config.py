import base64
import os
from pathlib import Path
from typing import Literal

from goodconf import Field, GoodConf

PROJECT_DIR = Path(__file__).parents[1].resolve()


class Config(GoodConf):
    """Configuration for gourmet."""

    DEBUG: bool = False
    ALLOWED_HOSTS: list[str] = Field(
        default=["*"],
        description="Hosts allowed to serve the site "
        "https://docs.djangoproject.com/en/6.0/ref/settings/#allowed-hosts",
    )
    DATABASE_URL: str = Field(
        default="sqlite:///./sqlite3.db",
        description="A string with the database URL as defined in "
        "https://github.com/jazzband/dj-database-url#url-schema",
    )
    DJANGO_ENV: Literal["development", "dev", "production"] = Field(
        default="production",
        description="Toggle deployment settings for local development or production",
    )
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Python logging level",
    )
    SECRET_KEY: str = Field(
        initial=lambda: base64.b64encode(os.urandom(60)).decode(),
        description="A long random string you keep secret "
        "https://docs.djangoproject.com/en/6.0/ref/settings/#secret-key",
    )
    ENVIRONMENT: str = Field(
        "development",
        description="Name of deployed environment (e.g. 'staging', 'production')",
    )
    BASIC_AUTH_CREDENTIALS: str = Field(
        default="",
        description=(
            "Basic Auth credentials for the site in the format 'username:password'"
        ),
    )
    SENTRY_DSN: str = Field(
        default="",
        description="Sentry DSN to enable error logging",
    )
    SENTRY_TRACES_SAMPLE_RATE: float = Field(
        default=0.25,
        description="Sentry trace sample rate "
        "https://docs.sentry.io/product/sentry-basics/concepts/tracing/trace-view/",
    )
    TEMPLATE_DEBUG: bool = Field(
        default=DEBUG,
        description="Enable to measure template coverage",
    )
    CORS_ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:5173"],
        description="Allowed origins for CORS (e.g. frontend dev server)",
    )
    CSRF_TRUSTED_ORIGINS: list[str] = Field(
        default=[],
        description="Trusted origins for CSRF (e.g. https://example.com)",
    )
    ADMIN_EMAIL: str = Field(
        default="",
        description="Email address for server error notifications",
    )
    EMAIL_HOST: str = Field(
        default="localhost",
        description="SMTP host for sending emails",
    )
    EMAIL_PORT: int = Field(
        default=25,
        description="SMTP port for sending emails",
    )
    EMAIL_HOST_USER: str = Field(
        default="",
        description="SMTP user for sending emails",
    )
    EMAIL_HOST_PASSWORD: str = Field(
        default="",
        description="SMTP password for sending emails",
    )
    EMAIL_USE_TLS: bool = Field(
        default=False,
        description="Enable TLS for SMTP",
    )
    EMAIL_USE_SSL: bool = Field(
        default=False,
        description="Enable SSL for SMTP",
    )
    DEFAULT_FROM_EMAIL: str = Field(
        default="webmaster@localhost",
        description="Default from address for emails",
    )
    SERVER_EMAIL: str = Field(
        default="root@localhost",
        description="Email address for system-generated error messages",
    )
    PEAR_API_URL: str = Field(
        default="http://localhost:9863/api/v1",
        description="URL for the Pear (Music Player Desktop) API",
    )
    BUSINESS_NAME: str = Field(
        default="Gourmet",
        description="Business name shown on receipts",
    )
    BUSINESS_NIT: str = Field(
        default="123.456.789-0",
        description="Business NIT shown on receipts",
    )

    # === Menu Images Storage (Supabase S3-compatible) ===
    MENU_IMAGE_BASE_URL: str = Field(
        default="/media/menu/",
        description=(
            "Base URL for menu images. In dev: /media/menu/. "
            "In prod: https://<project>.supabase.co/storage/v1/object/public/<bucket>/"
        ),
    )
    SUPABASE_STORAGE_ENDPOINT: str = Field(
        default="https://jnximziycwmcauyfilmy.supabase.co/storage/v1/s3",
        description=(
            "Supabase S3-compatible endpoint, e.g. "
            "https://jnximziycwmcauyfilmy.supabase.co/storage/v1/s3"
        ),
    )
    SUPABASE_STORAGE_REGION: str = Field(
        default="ca-central-1",
        description="Region for Supabase S3 storage (e.g. us-east-1)",
    )
    SUPABASE_STORAGE_ACCESS_KEY: str = Field(
        default="7d328887509450ccc3102af3e2a70fb7",
        description="Supabase S3 access key",
    )
    SUPABASE_STORAGE_SECRET_KEY: str = Field(
        default="e7af7f4de54cf69ee50423dd21c900b6047e22c044a44bebf4af4c39178eae82",
        description="Supabase S3 secret key",
    )
    SUPABASE_STORAGE_BUCKET: str = Field(
        default="Gourmet",
        description="Bucket name for menu images in Supabase",
    )
    SUPABASE_STORAGE_PUBLIC_URL: str = Field(
        default="https://jnximziycwmcauyfilmy.supabase.co/storage/v1/object/public/menu-images/",
        description=(
            "Public base URL for served images, e.g. "
            "https://jnximziycwmcauyfilmy.supabase.co/storage/v1/object/public/menu-images/"
        ),
    )

    model_config = {"default_files": ["gourmet.yml"]}


config = Config()
