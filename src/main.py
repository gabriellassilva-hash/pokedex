from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import (
    chat,
    create_chat,
    get_chat,
    get_health,
    get_tool_schema,
    get_tools,
    list_chats,
    send_chat_message,
)
from src.client.chat_store import chat_store
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciamento de ciclo de vida da aplicação."""
    # Startup
    print(f"Iniciando PokéGarden API v1.0.0")
    print(f"Configuração do catálogo: {settings.catalog_config}")
    print(f"Modelo OpenAI: {settings.openai_model}")
    
    try:
        yield
    finally:
        await chat_store.close()
        print("Encerrando PokéGarden API")


# Criar aplicação FastAPI
app = FastAPI(
    title="PokéGarden API",
    description="API de assistente de Pokémon usando OpenAI Agents SDK",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar origens permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rotas
app.add_api_route("/health", get_health, methods=["GET"], tags=["health"])
app.add_api_route("/tools", get_tools, methods=["GET"], tags=["catalog"])
app.add_api_route("/tools/{name}", get_tool_schema, methods=["GET"], tags=["catalog"])
app.add_api_route("/chat", chat, methods=["POST"], tags=["agent"])
app.add_api_route("/chats", create_chat, methods=["POST"], tags=["chats"])
app.add_api_route("/chats", list_chats, methods=["GET"], tags=["chats"])
app.add_api_route("/chats/{chat_id}", get_chat, methods=["GET"], tags=["chats"])
app.add_api_route(
    "/chats/{chat_id}/messages",
    send_chat_message,
    methods=["POST"],
    tags=["chats"],
)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
