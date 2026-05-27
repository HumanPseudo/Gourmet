from collections.abc import Callable

class BasicAuth:
    def __init__(
        self,
        app: Callable[..., object],
        realm: str = "Protected",
        users: dict[str, str] | None = None,
        exclude_paths: list[str] | None = None,
        include_paths: list[str] | None = None,
        env_prefix: str = "",
    ) -> None: ...
    def __call__(self, environ: dict[str, object], start_response: Callable[..., object]) -> list[bytes]: ...
