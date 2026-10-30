from typing import Any

from pydantic import BaseModel, Field


class ToolSource(BaseModel):
    url: str
    fetched_at: str | None = None
    cached: bool = False


class ToolOutput(BaseModel):
    """Validated envelope shared by every catalog tool result."""

    data: Any = None
    sources: list[ToolSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class ToolResult:
    """Resultado padrão de execução de ferramenta."""

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        sources: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
        error: str | None = None,
    ):
        self.data = data if data is not None else None
        self.sources = sources or []
        self.warnings = warnings or []
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário."""
        result = {
            "data": self.data,
            "sources": self.sources,
            "warnings": self.warnings
        }
        if self.error:
            result["error"] = self.error
        return result
