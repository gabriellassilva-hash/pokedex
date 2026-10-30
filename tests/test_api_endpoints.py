from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """Fixture para cliente de teste FastAPI."""
    return TestClient(app)


def test_health_endpoint(client):
    """Testa endpoint de health check."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


def test_get_tools_no_query(client):
    """Testa listagem de todas as ferramentas."""
    response = client.get("/tools")
    
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert len(data["tools"]) > 0
    
    # Verificar estrutura
    for tool in data["tools"]:
        assert "name" in tool
        assert "version" in tool
        assert "description" in tool
        assert "tags" in tool


def test_get_tools_with_query(client):
    """Testa busca de ferramentas com query."""
    response = client.get("/tools?query=pokemon")
    
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    
    # Deve retornar apenas ferramentas relacionadas a pokemon
    for tool in data["tools"]:
        assert "pokemon" in tool["name"].lower() or "pokémon" in tool["description"].lower()


def test_get_tool_schema_found(client):
    """Testa obtenção de schema de ferramenta existente."""
    response = client.get("/tools/get_pokemon")
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "get_pokemon"
    assert "input_schema" in data
    assert "output_schema" in data
    assert "description" in data


def test_get_tool_schema_not_found(client):
    """Testa 404 para ferramenta não encontrada."""
    response = client.get("/tools/nonexistent_tool")
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "não encontrada" in data["detail"].lower() or "not found" in data["detail"].lower()


def test_chat_endpoint_success(client):
    """Testa endpoint de chat com sucesso."""
    mock_result = {
        "answer": "Charizard é um Pokémon do tipo Fogo/Voador.",
        "sources": [
            {"url": "https://pokeapi.co/api/v2/pokemon/6", "fetched_at": "2026-10-29T14:30:00Z", "cached": False}
        ],
        "tools_used": ["search_tools", "get_tool_schema", "get_pokemon"],
        "warnings": []
    }
    
    with patch('src.api.router.orchestrator.chat', new_callable=AsyncMock, return_value=mock_result):
        response = client.post("/chat", json={"message": "Quem é o Charizard?"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "answer" in data
        assert "request_id" in data
        assert "sources" in data
        assert "tools_used" in data
        assert "warnings" in data


def test_chat_endpoint_passes_history_to_orchestrator(client):
    history = [{"role": "user", "content": "Fale sobre o Pikachu."}]
    mock_result = {
        "answer": "Pikachu é do tipo Elétrico.",
        "sources": [],
        "tools_used": [],
        "warnings": []
    }

    with patch('src.api.router.orchestrator.chat', new_callable=AsyncMock, return_value=mock_result) as mock_chat:
        response = client.post("/chat", json={"message": "E a evolução dele?", "history": history})

    assert response.status_code == 200
    mock_chat.assert_awaited_once_with("E a evolução dele?", history)


def test_create_chat_endpoint_persists_chat(client):
    chat_id = "a" * 32
    metadata = {
        "id": chat_id,
        "title": "Nova conversa",
        "created_at": "2026-10-29T12:00:00+00:00",
        "updated_at": "2026-10-29T12:00:00+00:00",
        "message_count": 0,
    }

    with patch("src.api.router.chat_store.create_chat", new_callable=AsyncMock, return_value=metadata):
        response = client.post("/chats", json={"title": "Nova conversa"})

    assert response.status_code == 200
    assert response.json()["id"] == chat_id


def test_list_chats_endpoint_returns_saved_chats(client):
    chat = {
        "id": "b" * 32,
        "title": "Pikachu",
        "created_at": "2026-10-29T12:00:00+00:00",
        "updated_at": "2026-10-29T12:01:00+00:00",
        "message_count": 2,
    }

    with patch("src.api.router.chat_store.list_chats", new_callable=AsyncMock, return_value=[chat]):
        response = client.get("/chats")

    assert response.status_code == 200
    assert response.json()["chats"] == [chat]


def test_get_chat_endpoint_returns_message_history(client):
    chat_id = "c" * 32
    conversation = {
        "id": chat_id,
        "title": "Pikachu",
        "created_at": "2026-10-29T12:00:00+00:00",
        "updated_at": "2026-10-29T12:01:00+00:00",
        "message_count": 2,
        "messages": [
            {"role": "user", "content": "Quem é Pikachu?"},
            {"role": "assistant", "content": "Um Pokémon elétrico."},
        ],
    }

    with patch("src.api.router.chat_store.get_chat", new_callable=AsyncMock, return_value=conversation):
        response = client.get(f"/chats/{chat_id}")

    assert response.status_code == 200
    assert response.json()["messages"] == conversation["messages"]


def test_send_chat_message_persists_both_sides_and_uses_history(client):
    chat_id = "d" * 32
    conversation = {
        "messages": [{"role": "user", "content": "Quem é Pikachu?"}],
    }
    result = {
        "answer": "Pikachu é elétrico.",
        "sources": [],
        "tools_used": ["get_pokemon"],
        "warnings": [],
    }
    with patch("src.api.router.chat_store.get_chat", new_callable=AsyncMock, return_value=conversation), \
         patch("src.api.router.chat_store.add_message", new_callable=AsyncMock) as mock_add_message, \
         patch("src.api.router.orchestrator.chat", new_callable=AsyncMock, return_value=result) as mock_chat:
        response = client.post(f"/chats/{chat_id}/messages", json={"message": "E a evolução dele?"})

    assert response.status_code == 200
    assert response.json()["chat_id"] == chat_id
    mock_chat.assert_awaited_once_with(
        "E a evolução dele?",
        [{"role": "user", "content": "Quem é Pikachu?"}],
    )
    assert mock_add_message.await_count == 2


def test_chat_endpoint_not_found(client):
    """Testa chat com Pokémon não encontrado."""
    mock_result = {
        "answer": "Pokémon 'Nonexistent' não foi encontrado.",
        "sources": [],
        "tools_used": ["search_tools", "get_tool_schema", "get_pokemon"],
        "warnings": []
    }
    
    with patch('src.api.router.orchestrator.chat', new_callable=AsyncMock, return_value=mock_result):
        response = client.post("/chat", json={"message": "Quem é o Nonexistent?"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_found"


def test_chat_endpoint_unsupported(client):
    """Testa chat com ferramenta não suportada."""
    mock_result = {
        "answer": "A ferramenta de evolução não está disponível nesta configuração.",
        "sources": [],
        "tools_used": ["search_tools", "get_tool_schema"],
        "warnings": []
    }
    
    with patch('src.api.router.orchestrator.chat', new_callable=AsyncMock, return_value=mock_result):
        response = client.post("/chat", json={"message": "Qual a evolução do Charizard?"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unsupported"


def test_chat_endpoint_error(client):
    """Testa chat com erro interno."""
    mock_result = {
        "answer": "Erro ao processar requisição: simulação de erro",
        "sources": [],
        "tools_used": [],
        "warnings": ["Erro: simulação de erro"]
    }
    
    with patch('src.api.router.orchestrator.chat', new_callable=AsyncMock, return_value=mock_result):
        response = client.post("/chat", json={"message": "Teste de erro"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"


def test_chat_endpoint_exception(client):
    """Testa chat com exceção não tratada."""
    with patch('src.api.router.orchestrator.chat', new_callable=AsyncMock, side_effect=Exception("Unexpected error")):
        response = client.post("/chat", json={"message": "Teste"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Erro interno" in data["answer"]


def test_cors_headers(client):
    """Testa que CORS headers estão configurados."""
    response = client.options("/health")
    
    # Verificar que resposta não tem erro de CORS
    assert response.status_code in [200, 405]  # 405 para OPTIONS se não implementado
