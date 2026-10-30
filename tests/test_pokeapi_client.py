from unittest.mock import AsyncMock, patch

import pytest
import httpx

from src.client.pokeapi import PokeAPIClient


@pytest.fixture
def client():
    """Fixture para cliente PokéAPI."""
    return PokeAPIClient(base_url="https://pokeapi.co/api/v2", timeout=10.0)


def test_normalize_name(client):
    """Testa normalização de nomes."""
    # Minúsculas e trim
    assert client._normalize_name("  Charizard  ") == "charizard"
    
    # ID numérico
    assert client._normalize_name(25) == "25"
    
    # Caracteres especiais
    assert client._normalize_name("Nidoran♀") == "nidoran-f"
    assert client._normalize_name("Nidoran♂") == "nidoran-m"
    
    # Acentos
    assert client._normalize_name("Pokémon") == "pokemon"
    assert client._normalize_name("Pikachú") == "pikachu"
    
    # Espaços internos
    assert client._normalize_name("Mr Mime") == "mr-mime"


def test_validate_url_allowed(client):
    """Testa validação de URL permitida."""
    allowed_url = "https://pokeapi.co/api/v2/pokemon/25"
    assert client._validate_url(allowed_url) is True


def test_validate_url_blocked(client):
    """Testa validação de URL bloqueada (domínio diferente)."""
    blocked_url = "https://evil.com/api/data"
    assert client._validate_url(blocked_url) is False
    
    blocked_url2 = "https://pokeapi.co.evil.com/api/v2/pokemon/25"
    assert client._validate_url(blocked_url2) is False


@pytest.mark.asyncio
async def test_get_404_response(client):
    """Testa resposta 404 (não encontrado)."""
    mock_response = AsyncMock()
    mock_response.status_code = 404
    
    with patch.object(httpx.AsyncClient, 'get', return_value=mock_response):
        result = await client.get("pokemon", "nonexistent")
        
        assert result["data"] is None
        assert result["error"] is not None
        assert "não encontrado" in result["error"].lower() or "erro" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_domain_validation_block(client):
    """Testa bloqueio de URL com domínio inválido."""
    # Sobrescrever validação para simular URL externa
    with patch.object(client, '_validate_url', return_value=False):
        result = await client.get("pokemon", "charizard")
        
        assert result["data"] is None
        assert "não permitida" in result["error"].lower()
        assert "domínio bloqueado" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_success_response(client):
    """Testa resposta de sucesso."""
    mock_data = {"id": 25, "name": "pikachu"}
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: mock_data
    
    with patch.object(httpx.AsyncClient, 'get', return_value=mock_response):
        result = await client.get("pokemon", "pikachu", use_cache=False)

        assert result["data"] == mock_data
        assert result.get("error") is None
        assert len(result["sources"]) == 1
        assert result["sources"][0]["cached"] is False


@pytest.mark.asyncio
async def test_get_5xx_retry(client):
    """Testa retry em erro 5xx."""
    mock_response_5xx = AsyncMock()
    mock_response_5xx.status_code = 500

    mock_response_success = AsyncMock()
    mock_response_success.status_code = 200
    mock_response_success.json = lambda: {"id": 25, "name": "pikachu"}

    with patch.object(httpx.AsyncClient, 'get', side_effect=[mock_response_5xx, mock_response_success]):
        result = await client.get("pokemon", "pikachu")

        assert result["data"] is not None
        assert result["data"]["name"] == "pikachu"


@pytest.mark.asyncio
async def test_get_429_retry(client):
    """Testa retry em rate limit (429)."""
    mock_response_429 = AsyncMock()
    mock_response_429.status_code = 429

    mock_response_success = AsyncMock()
    mock_response_success.status_code = 200
    mock_response_success.json = lambda: {"id": 25, "name": "pikachu"}

    with patch.object(httpx.AsyncClient, 'get', side_effect=[mock_response_429, mock_response_success]):
        result = await client.get("pokemon", "pikachu")

        assert result["data"] is not None
        assert result["data"]["name"] == "pikachu"


@pytest.mark.asyncio
async def test_get_timeout_retry(client):
    """Testa retry em timeout."""
    with patch.object(httpx.AsyncClient, 'get', side_effect=httpx.TimeoutException("Timeout")):
        result = await client.get("pokemon", "pikachu", use_cache=False)

        assert result["data"] is None
        assert result["error"] is not None


@pytest.mark.asyncio
async def test_get_max_retries_exceeded(client):
    """Testa falha após máximo de retries."""
    mock_response_5xx = AsyncMock()
    mock_response_5xx.status_code = 500

    with patch.object(httpx.AsyncClient, 'get', return_value=mock_response_5xx):
        result = await client.get("pokemon", "pikachu", use_cache=False)

        assert result["data"] is None
        assert result["error"] is not None
