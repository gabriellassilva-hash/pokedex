from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Resposta do endpoint de health check."""
    status: str = "ok"
    version: str = "1.0.0"


class ToolMetadataResponse(BaseModel):
    """Metadados de uma ferramenta."""
    name: str
    version: str
    description: str
    tags: list[str]


class ToolsListResponse(BaseModel):
    """Lista de ferramentas disponíveis."""
    tools: list[ToolMetadataResponse]


class ToolSchemaResponse(BaseModel):
    """Schema detalhado de uma ferramenta."""
    name: str
    version: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class ChatRequest(BaseModel):
    """Requisição para o endpoint de chat."""
    message: str = Field(..., min_length=1, max_length=4000, description="Mensagem do usuário")
    history: list["ConversationMessage"] = Field(default_factory=list, max_length=20)


class ConversationMessage(BaseModel):
    """Mensagem anterior enviada como contexto da conversa."""
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=80)


class ChatSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ChatListResponse(BaseModel):
    chats: list[ChatSummary]


class ChatHistoryResponse(ChatSummary):
    messages: list[ConversationMessage]


class SourceInfo(BaseModel):
    """Informações de fonte de dados."""
    url: str
    fetched_at: str | None = None
    cached: bool = False


class ChatResponse(BaseModel):
    """Resposta do endpoint de chat."""
    request_id: str
    chat_id: str | None = None
    status: str = Field(..., description="ok | partial | not_found | unsupported | error")
    answer: str
    sources: list[SourceInfo] = []
    tools_used: list[str] = []
    warnings: list[str] = []


class ErrorResponse(BaseModel):
    """Resposta de erro padrão."""
    error: str
    detail: str | None = None
