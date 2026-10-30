from typing import Any

from pydantic import BaseModel, Field

from src.client.pokeapi import pokeapi_client
from src.tools.base import ToolResult


class GetEvolutionChainInput(BaseModel):
    """Input schema para get_evolution_chain."""
    name_or_id: str | int = Field(
        ...,
        description="Nome ou ID do Pokémon para obter cadeia de evolução"
    )


def _parse_evolution_details(evolution_details: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Extrai condições de evolução dos detalhes.
    
    Args:
        evolution_details: Lista de detalhes de evolução da API
        
    Returns:
        Dicionário com condições (level, item, trade, etc.)
    """
    conditions = {}
    
    for detail in evolution_details:
        # Nível
        if detail.get("min_level"):
            conditions["level"] = detail["min_level"]
        
        # Item
        if detail.get("item"):
            conditions["item"] = detail["item"]["name"]
        
        # Trade
        if detail.get("trigger", {}).get("name") == "trade":
            conditions["trade"] = True
        
        # Happiness
        if detail.get("min_happiness"):
            conditions["happiness"] = detail["min_happiness"]
        
        # Time of day
        if detail.get("time_of_day") and detail["time_of_day"] != "":
            conditions["time_of_day"] = detail["time_of_day"]
        
        # Held item during trade
        if detail.get("held_item"):
            conditions["held_item"] = detail["held_item"]["name"]
        
        # Known move
        if detail.get("known_move"):
            conditions["known_move"] = detail["known_move"]["name"]
        
        # Known move type
        if detail.get("known_move_type"):
            conditions["known_move_type"] = detail["known_move_type"]["name"]
        
        # Location
        if detail.get("location"):
            conditions["location"] = detail["location"]["name"]
        
        # Affection (for Pikachu -> Raichu in Let's Go)
        if detail.get("min_affection"):
            conditions["affection"] = detail["min_affection"]
        
        # Physical stats (for Hitmonlee/Hitmonchan)
        if detail.get("relative_physical_stats") is not None:
            conditions["relative_physical_stats"] = detail["relative_physical_stats"]
    
    return conditions


def _parse_evolution_chain(evolution_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Analisa recursivamente a cadeia de evolução preservando estrutura de árvore.
    
    Args:
        evolution_data: Dados da cadeia de evolução da API
        
    Returns:
        Lista de Pokémon com suas evoluções (estrutura recursiva)
    """
    chain = evolution_data["chain"]
    
    def parse_node(node: dict[str, Any]) -> dict[str, Any]:
        """Analisa um nó da árvore de evolução."""
        pokemon_name = node["species"]["name"]
        
        # Extrair condições para evoluir para este Pokémon
        evolution_details = node.get("evolution_details", [])
        conditions = _parse_evolution_details(evolution_details) if evolution_details else {}
        
        # Analisar evoluções subsequentes recursivamente
        evolves_to = []
        for child in node.get("evolves_to", []):
            evolves_to.append(parse_node(child))
        
        result = {
            "name": pokemon_name,
            "evolves_to": evolves_to
        }
        
        if conditions:
            result["conditions"] = conditions
        
        return result
    
    return [parse_node(chain)]


async def get_evolution_chain(name_or_id: str | int) -> dict[str, Any]:
    """
    Obtém a cadeia de evolução de um Pokémon.
    
    Args:
        name_or_id: Nome ou ID do Pokémon
        
    Returns:
        Dicionário com cadeia de evolução em estrutura de árvore
    """
    # Buscar dados da espécie do Pokémon
    species_result = await pokeapi_client.get("pokemon-species", name_or_id)
    
    if species_result.get("error"):
        return ToolResult(
            data=None,
            sources=[],
            error=species_result["error"]
        ).to_dict()
    
    if species_result["data"] is None:
        return ToolResult(
            data=None,
            sources=[],
            error=f"Pokémon '{name_or_id}' não encontrado"
        ).to_dict()
    
    species_data = species_result["data"]
    evolution_chain_obj = species_data.get("evolution_chain")
    evolution_chain_url = evolution_chain_obj.get("url") if evolution_chain_obj else None
    
    if not evolution_chain_url:
        return ToolResult(
            data={
                "pokemon": species_data["name"],
                "evolution_chain": [],
                "note": "Este Pokémon não possui cadeia de evolução"
            },
            sources=species_result["sources"]
        ).to_dict()
    
    # Extrair ID da cadeia de evolução da URL
    # URL format: https://pokeapi.co/api/v2/evolution-chain/{id}/
    chain_id = evolution_chain_url.rstrip("/").split("/")[-1]
    
    # Buscar dados da cadeia de evolução
    chain_result = await pokeapi_client.get("evolution-chain", chain_id)
    
    if chain_result.get("error"):
        return ToolResult(
            data=None,
            sources=species_result["sources"],
            error=chain_result["error"]
        ).to_dict()
    
    if chain_result["data"] is None:
        return ToolResult(
            data=None,
            sources=species_result["sources"],
            error="Não foi possível obter dados da cadeia de evolução"
        ).to_dict()
    
    # Analisar cadeia de evolução
    evolution_tree = _parse_evolution_chain(chain_result["data"])
    
    all_sources = species_result["sources"] + chain_result["sources"]
    
    return ToolResult(
        data={
            "pokemon": species_data["name"],
            "evolution_chain": evolution_tree
        },
        sources=all_sources
    ).to_dict()
