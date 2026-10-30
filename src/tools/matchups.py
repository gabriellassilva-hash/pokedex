from typing import Any

from pydantic import BaseModel, Field

from src.client.pokeapi import pokeapi_client
from src.tools.base import ToolResult


class GetTypeMatchupsInput(BaseModel):
    """Input schema para get_type_matchups."""
    name_or_id: str | int = Field(
        ...,
        description="Nome ou ID do Pokémon para calcular efetividade de tipos"
    )


async def get_type_matchups(name_or_id: str | int) -> dict[str, Any]:
    """
    Calcula efetividade de tipos defensiva de um Pokémon.
    
    Args:
        name_or_id: Nome ou ID do Pokémon
        
    Returns:
        Dicionário com multiplicadores de dano por tipo
    """
    # Buscar dados do Pokémon para obter tipos
    pokemon_result = await pokeapi_client.get("pokemon", name_or_id)
    
    if pokemon_result.get("error"):
        return ToolResult(
            data=None,
            sources=[],
            error=pokemon_result["error"]
        ).to_dict()
    
    if pokemon_result["data"] is None:
        return ToolResult(
            data=None,
            sources=[],
            error=f"Pokémon '{name_or_id}' não encontrado"
        ).to_dict()
    
    pokemon_data = pokemon_result["data"]
    type_urls = [t["type"]["url"] for t in pokemon_data["types"]]
    
    # Extrair IDs dos tipos das URLs
    type_ids = []
    for url in type_urls:
        # URL format: https://pokeapi.co/api/v2/type/{id}/
        type_id = url.rstrip("/").split("/")[-1]
        type_ids.append(type_id)
    
    # Buscar dados de cada tipo
    all_sources = pokemon_result["sources"].copy()
    type_data_list = []
    
    for type_id in type_ids:
        type_result = await pokeapi_client.get("type", type_id)
        
        if type_result.get("error"):
            continue
        
        if type_result["data"]:
            type_data_list.append(type_result["data"])
            all_sources.extend(type_result["sources"])
    
    if not type_data_list:
        return ToolResult(
            data=None,
            sources=all_sources,
            error="Não foi possível obter dados de tipos"
        ).to_dict()
    
    # Calcular multiplicadores combinados
    # Começar com 1.0 (neutro)
    multipliers: dict[str, float] = {}
    
    for type_data in type_data_list:
        damage_relations = type_data["damage_relations"]
        
        # Tipos que causam dano dobrado (2x)
        for type_info in damage_relations["double_damage_from"]:
            type_name = type_info["name"]
            multipliers[type_name] = multipliers.get(type_name, 1.0) * 2.0
        
        # Tipos que causam metade do dano (0.5x)
        for type_info in damage_relations["half_damage_from"]:
            type_name = type_info["name"]
            multipliers[type_name] = multipliers.get(type_name, 1.0) * 0.5
        
        # Tipos que causam dano zero (imunidade 0x)
        for type_info in damage_relations["no_damage_from"]:
            type_name = type_info["name"]
            multipliers[type_name] = 0.0
    
    # Garantir que tipos não listados apareçam como 1.0 (neutro)
    # Lista de todos os tipos do Pokémon
    pokemon_types = [t["type"]["name"] for t in pokemon_data["types"]]
    
    return ToolResult(
        data={
            "pokemon": pokemon_data["name"],
            "types": pokemon_types,
            "defensive_matchups": multipliers
        },
        sources=all_sources
    ).to_dict()
