from collections.abc import Callable
from typing import Any, ClassVar

from pydantic_settings import BaseSettings

class GoodConf(BaseSettings):
    model_config: ClassVar[Any] = {}
    def __init__(self, load: bool = False, config_file: str | None = None, **kwargs: Any) -> None: ...
    def load(self, filename: str | None = None) -> None: ...

def Field(
    *args: Any,
    initial: Callable[[], Any] | Any = None,
    json_schema_extra: dict[str, Any] | Callable[[dict[str, Any]], None] | None = None,
    **kwargs: Any,
) -> Any: ...
