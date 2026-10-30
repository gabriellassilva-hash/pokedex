from unittest.mock import AsyncMock, patch

import pytest

from src.tools.pokemon import get_pokemon
from src.tools.compare import compare_pokemon
from src.tools.matchups import get_type_matchups
from src.tools.evolution import get_evolution_chain


@pytest.mark.asyncio
async def test_get_pokemon_success():
    """Testa busca de Pokémon com sucesso."""
    mock_pokemon_data = {
        "id": 25,
        "name": "pikachu",
        "height": 4,  # 0.4m
        "weight": 60,  # 6.0kg
        "types": [{"type": {"name": "electric"}}],
        "abilities": [{"ability": {"name": "static"}}, {"ability": {"name": "lightning-rod"}}],
        "stats": [
            {"stat": {"name": "hp"}, "base_stat": 35},
            {"stat": {"name": "attack"}, "base_stat": 55},
            {"stat": {"name": "defense"}, "base_stat": 40},
            {"stat": {"name": "special-attack"}, "base_stat": 50},
            {"stat": {"name": "special-defense"}, "base_stat": 50},
            {"stat": {"name": "speed"}, "base_stat": 90}
        ]
    }
    
    mock_response = {
        "data": mock_pokemon_data,
        "sources": [{"url": "https://pokeapi.co/api/v2/pokemon/25", "fetched_at": "2026-10-29T14:30:00Z", "cached": False}]
    }
    
    with patch('src.tools.pokemon.pokeapi_client.get', return_value=mock_response):
        result = await get_pokemon("pikachu")
        
        assert result["data"]["id"] == 25
        assert result["data"]["name"] == "pikachu"
        assert result["data"]["height"] == 0.4  # 4dm -> 0.4m
        assert result["data"]["weight"] == 6.0  # 60hg -> 6.0kg
        assert result["data"]["types"] == ["electric"]
        assert "static" in result["data"]["abilities"]
        assert result["data"]["stats"]["hp"] == 35
        assert result["data"]["stats"]["speed"] == 90


@pytest.mark.asyncio
async def test_get_pokemon_not_found():
    """Testa Pokémon não encontrado."""
    mock_response = {
        "data": None,
        "sources": [],
        "error": "Recurso não encontrado"
    }
    
    with patch('src.tools.pokemon.pokeapi_client.get', return_value=mock_response):
        result = await get_pokemon("nonexistent")
        
        assert result["data"] is None
        assert result["error"] is not None
        assert "não encontrado" in result["error"].lower()


@pytest.mark.asyncio
async def test_compare_pokemon_two():
    """Testa comparação de 2 Pokémon."""
    # Mock get_pokemon
    async def mock_get_pokemon(name):
        if name == "pikachu":
            return {
                "data": {
                    "name": "pikachu",
                    "id": 25,
                    "stats": {"hp": 35, "attack": 55, "defense": 40, "special-attack": 50, "special-defense": 50, "speed": 90}
                },
                "sources": [{"url": "https://pokeapi.co/api/v2/pokemon/25", "cached": False}]
            }
        elif name == "charizard":
            return {
                "data": {
                    "name": "charizard",
                    "id": 6,
                    "stats": {"hp": 78, "attack": 84, "defense": 78, "special-attack": 109, "special-defense": 85, "speed": 100}
                },
                "sources": [{"url": "https://pokeapi.co/api/v2/pokemon/6", "cached": False}]
            }
        return {"data": None, "error": "Not found"}
    
    with patch('src.tools.compare.get_pokemon', side_effect=mock_get_pokemon):
        result = await compare_pokemon(["pikachu", "charizard"])
        
        assert result["data"]["pokemon"][0]["name"] == "pikachu"
        assert result["data"]["pokemon"][1]["name"] == "charizard"
        assert result["data"]["stat_comparisons"]["hp"]["max"] == 78
        assert result["data"]["stat_comparisons"]["hp"]["best"] == ["charizard"]
        assert any("A maior soma de atributos base não é garantia de vitória em batalha" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_compare_pokemon_too_few():
    """Testa erro com menos de 2 Pokémon."""
    result = await compare_pokemon(["pikachu"])
    
    assert result["data"] is None
    assert result["error"] is not None
    assert "entre 2 e 6" in result["error"].lower()


@pytest.mark.asyncio
async def test_compare_pokemon_too_many():
    """Testa erro com mais de 6 Pokémon."""
    result = await compare_pokemon(["p1", "p2", "p3", "p4", "p5", "p6", "p7"])
    
    assert result["data"] is None
    assert result["error"] is not None
    assert "entre 2 e 6" in result["error"].lower()


@pytest.mark.asyncio
async def test_compare_pokemon_tie():
    """Testa empate em estatística."""
    async def mock_get_pokemon(name):
        return {
            "data": {
                "name": name,
                "id": 1,
                "stats": {"hp": 50, "attack": 50, "defense": 50, "special-attack": 50, "special-defense": 50, "speed": 50}
            },
            "sources": []
        }
    
    with patch('src.tools.compare.get_pokemon', side_effect=mock_get_pokemon):
        result = await compare_pokemon(["p1", "p2"])
        
        assert result["data"]["stat_comparisons"]["hp"]["tie"] is True
        assert len(result["data"]["stat_comparisons"]["hp"]["best"]) == 2


@pytest.mark.asyncio
async def test_get_type_matchups_single_type():
    """Testa matchups de tipo único."""
    mock_pokemon_response = {
        "data": {
            "name": "pikachu",
            "types": [{"type": {"name": "electric", "url": "https://pokeapi.co/api/v2/type/13/"}}]
        },
        "sources": []
    }
    
    mock_type_response = {
        "data": {
            "name": "electric",
            "damage_relations": {
                "double_damage_from": [{"name": "ground"}],
                "half_damage_from": [{"name": "electric"}, {"name": "flying"}, {"name": "steel"}],
                "no_damage_from": []
            }
        },
        "sources": []
    }
    
    with patch('src.tools.matchups.pokeapi_client.get') as mock_get:
        mock_get.side_effect = [mock_pokemon_response, mock_type_response]
        
        result = await get_type_matchups("pikachu")
        
        assert result["data"]["pokemon"] == "pikachu"
        assert result["data"]["types"] == ["electric"]
        assert result["data"]["defensive_matchups"]["ground"] == 2.0
        assert result["data"]["defensive_matchups"]["electric"] == 0.5
        assert result["data"]["defensive_matchups"]["flying"] == 0.5


@pytest.mark.asyncio
async def test_get_type_matchups_dual_type_immunity():
    """Testa imunidade (0x) em tipo duplo."""
    mock_pokemon_response = {
        "data": {
            "name": "gengar",
            "types": [
                {"type": {"name": "ghost", "url": "https://pokeapi.co/api/v2/type/8/"}},
                {"type": {"name": "poison", "url": "https://pokeapi.co/api/v2/type/4/"}}
            ]
        },
        "sources": []
    }
    
    # Ghost tem no_damage_from: normal, fighting
    # Poison tem no_damage_from: (nenhum específico, mas combinações podem ocorrer)
    mock_ghost_response = {
        "data": {
            "damage_relations": {
                "double_damage_from": [{"name": "ghost"}, {"name": "dark"}],
                "half_damage_from": [{"name": "poison"}, {"name": "bug"}],
                "no_damage_from": [{"name": "normal"}, {"name": "fighting"}]
            }
        },
        "sources": []
    }
    
    mock_poison_response = {
        "data": {
            "damage_relations": {
                "double_damage_from": [{"name": "ground"}, {"name": "psychic"}],
                "half_damage_from": [{"name": "grass"}, {"name": "fairy"}, {"name": "fighting"}, {"name": "bug"}],
                "no_damage_from": []
            }
        },
        "sources": []
    }
    
    with patch('src.tools.matchups.pokeapi_client.get') as mock_get:
        mock_get.side_effect = [mock_pokemon_response, mock_ghost_response, mock_poison_response]
        
        result = await get_type_matchups("gengar")
        
        # Verificar imunidade (0x)
        assert result["data"]["defensive_matchups"]["normal"] == 0.0
        assert result["data"]["defensive_matchups"]["fighting"] == 0.0  # Ghost (0x) * Poison (0.5x) = 0x


@pytest.mark.asyncio
async def test_get_evolution_chain_simple():
    """Testa cadeia de evolução simples."""
    mock_species_response = {
        "data": {
            "name": "pikachu",
            "evolution_chain": {
                "url": "https://pokeapi.co/api/v2/evolution-chain/10/"
            }
        },
        "sources": []
    }
    
    mock_chain_response = {
        "data": {
            "id": 10,
            "chain": {
                "species": {"name": "pichu"},
                "evolves_to": [
                    {
                        "species": {"name": "pikachu"},
                        "evolution_details": [{"min_level": 2}],
                        "evolves_to": [
                            {
                                "species": {"name": "raichu"},
                                "evolution_details": [{"item": {"name": "thunder-stone"}}],
                                "evolves_to": []
                            }
                        ]
                    }
                ]
            }
        },
        "sources": []
    }
    
    with patch('src.tools.evolution.pokeapi_client.get') as mock_get:
        mock_get.side_effect = [mock_species_response, mock_chain_response]
        
        result = await get_evolution_chain("pikachu")
        
        assert result["data"]["pokemon"] == "pikachu"
        assert result["data"]["evolution_chain"][0]["name"] == "pichu"
        assert result["data"]["evolution_chain"][0]["evolves_to"][0]["name"] == "pikachu"
        assert result["data"]["evolution_chain"][0]["evolves_to"][0]["conditions"]["level"] == 2


@pytest.mark.asyncio
async def test_get_evolution_chain_no_evolution():
    """Testa Pokémon sem cadeia de evolução."""
    mock_species_response = {
        "data": {
            "name": "mew",
            "evolution_chain": None
        },
        "sources": []
    }
    
    with patch('src.tools.evolution.pokeapi_client.get', return_value=mock_species_response):
        result = await get_evolution_chain("mew")
        
        assert result["data"]["pokemon"] == "mew"
        assert result["data"]["evolution_chain"] == []
        assert "não possui cadeia de evolução" in result["data"]["note"]
