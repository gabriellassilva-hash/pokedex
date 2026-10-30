from typing import Any

from pydantic import BaseModel, Field

from src.client.pokeapi import pokeapi_client
from src.tools.base import ToolResult


class GetPokemonInput(BaseModel):
    """Input schema para get_pokemon."""
    name_or_id: str | int = Field(
        ...,
        description="Nome ou ID do Pokémon (ex: 'charizard' ou 6)"
    )


async def get_pokemon(name_or_id: str | int) -> dict[str, Any]:
    """
    Busca informações detalhadas de um Pokémon.
    
    Args:
        name_or_id: Nome ou ID do Pokémon
        
    Returns:
        Dicionário com dados do Pokémon, fontes e avisos
    """
    result = await pokeapi_client.get("pokemon", name_or_id)
    
    if result.get("error"):
        return ToolResult(
            data=None,
            sources=[],
            error=result["error"]
        ).to_dict()
    
    if result["data"] is None:
        return ToolResult(
            data=None,
            sources=[],
            error=f"Pokémon '{name_or_id}' não encontrado"
        ).to_dict()
    
    data = result["data"]
    
    # Extrair e converter dados
    pokemon_data = {
        "id": data["id"],
        "name": data["name"],
        "height": data["height"] / 10,  # decímetros para metros
        "weight": data["weight"] / 10,  # hectogramas para kg
        "types": [t["type"]["name"] for t in data["types"]],
        "abilities": [a["ability"]["name"] for a in data["abilities"]],
        "stats": {
            stat["stat"]["name"]: stat["base_stat"]
            for stat in data["stats"]
        }
    }
    
    return ToolResult(
        data=pokemon_data,
        sources=result["sources"]
    ).to_dict()
