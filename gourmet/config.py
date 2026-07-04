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

    model_config = {"default_files": ["gourmet.yml"]}


config = Config()
