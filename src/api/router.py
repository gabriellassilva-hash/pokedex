import uuid
from typing import Any

from fastapi import HTTPException, Path, Query

from src.agent.orchestrator import orchestrator
from src.client.chat_store import ChatStoreUnavailable, chat_store
from src.api.schemas import (
    ChatCreateRequest,
    ChatHistoryResponse,
    ChatListResponse,
    ChatRequest,
    ChatResponse,
    ChatSummary,
    ErrorResponse,
    HealthResponse,
    SourceInfo,
    ToolSchemaResponse,
    ToolsListResponse
)
from src.catalog.registry import tool_registry


async def get_health() -> HealthResponse:
    """
    Endpoint de health check.
    
    Retorna status do serviço sem consumir tokens OpenAI ou acessar PokéAPI.
    """
    return HealthResponse()


async def get_tools(query: str | None = Query(None, description="Termo de busca")) -> ToolsListResponse:
    """
    Lista ferramentas disponíveis no catálogo.
    
    Args:
        query: Termo opcional para filtrar ferramentas
        
    Returns:
        Lista de ferramentas habilitadas
    """
    if query:
        tools = tool_registry.search_tools(query)
    else:
        tools = tool_registry.get_all_enabled_tools()
    
    return ToolsListResponse(tools=tools)


async def get_tool_schema(name: str) -> ToolSchemaResponse:
    """
    Obtém o schema detalhado de uma ferramenta específica.
    
    Args:
        name: Nome da ferramenta
        
    Returns:
        Schema da ferramenta
        
    Raises:
        HTTPException: Se ferramenta não encontrada ou desabilitada
    """
    schema = tool_registry.get_tool_schema(name)
    
    if schema is None:
        raise HTTPException(
            status_code=404,
            detail=f"Ferramenta '{name}' não encontrada ou desabilitada"
        )
    
    return ToolSchemaResponse(**schema)


async def chat(request: ChatRequest) -> ChatResponse:
    """
    Endpoint de chat com o agente de Pokémon.
    
    Args:
        request: Requisição com mensagem do usuário
        
    Returns:
        Resposta do agente com sources, tools_used e warnings
    """
    request_id = f"req-{uuid.uuid4().hex[:8]}"
    
    try:
        # Executar orquestrador
        result = await orchestrator.chat(
            request.message,
            [message.model_dump() for message in request.history],
        )
        
        # Determinar status
        status = "ok"
        answer_lower = result["answer"].lower()
        if "não encontrado" in answer_lower or "não foi encontrado" in answer_lower:
            status = "not_found"
        elif "não disponível" in answer_lower or "desabilitada" in answer_lower or "não está disponível" in answer_lower:
            status = "unsupported"
        elif "erro" in answer_lower:
            status = "error"
        
        return ChatResponse(
            request_id=request_id,
            status=status,
            answer=result["answer"],
            sources=[SourceInfo(**s) for s in result["sources"]],
            tools_used=result["tools_used"],
            warnings=result["warnings"]
        )
        
    except Exception as e:
        return ChatResponse(
            request_id=request_id,
            status="error",
            answer=f"Erro interno ao processar requisição: {str(e)}",
            sources=[],
            tools_used=[],
            warnings=[f"Erro: {str(e)}"]
        )


async def create_chat(request: ChatCreateRequest) -> ChatSummary:
    try:
        metadata = await chat_store.create_chat(request.title or "Nova conversa")
    except ChatStoreUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return ChatSummary(**metadata)


async def list_chats() -> ChatListResponse:
    try:
        chats = await chat_store.list_chats()
    except ChatStoreUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return ChatListResponse(chats=[ChatSummary(**metadata) for metadata in chats])


async def get_chat(
    chat_id: str = Path(..., pattern=r"^[a-f0-9]{32}$"),
) -> ChatHistoryResponse:
    try:
        conversation = await chat_store.get_chat(chat_id)
    except ChatStoreUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return ChatHistoryResponse(**conversation)


async def send_chat_message(
    request: ChatRequest,
    chat_id: str = Path(..., pattern=r"^[a-f0-9]{32}$"),
) -> ChatResponse:
    try:
        conversation = await chat_store.get_chat(chat_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")

        history = [
            {"role": message["role"], "content": message["content"]}
            for message in conversation["messages"][-20:]
        ]
        await chat_store.add_message(chat_id, "user", request.message)
        result = await orchestrator.chat(request.message, history)
        await chat_store.add_message(chat_id, "assistant", result["answer"])
    except ChatStoreUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    answer_lower = result["answer"].lower()
    status = "ok"
    if "não encontrado" in answer_lower or "não foi encontrado" in answer_lower:
        status = "not_found"
    elif "não disponível" in answer_lower or "desabilitada" in answer_lower or "não está disponível" in answer_lower:
        status = "unsupported"
    elif "erro" in answer_lower:
        status = "error"

    return ChatResponse(
        request_id=f"req-{uuid.uuid4().hex[:8]}",
        chat_id=chat_id,
        status=status,
        answer=result["answer"],
        sources=[SourceInfo(**source) for source in result["sources"]],
        tools_used=result["tools_used"],
        warnings=result["warnings"],
    )
