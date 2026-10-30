from typing import Any

from pydantic import BaseModel, Field

from src.tools.base import ToolResult
from src.tools.pokemon import get_pokemon


class ComparePokemonInput(BaseModel):
    """Input schema para compare_pokemon."""
    identifiers: list[str] = Field(
        ...,
        min_length=2,
        max_length=6,
        description="Lista de 2 a 6 Pokémon para comparar (nomes ou IDs)"
    )


async def compare_pokemon(identifiers: list[str]) -> dict[str, Any]:
    """
    Compara estatísticas base de múltiplos Pokémon.
    
    Args:
        identifiers: Lista de nomes ou IDs de Pokémon (2 a 6)
        
    Returns:
        Dicionário com comparação de estatísticas e avisos
    """
    if len(identifiers) < 2 or len(identifiers) > 6:
        return ToolResult(
            data=None,
            error="É necessário fornecer entre 2 e 6 Pokémon para comparação"
        ).to_dict()
    
    # Buscar dados de todos os Pokémon
    pokemon_data = []
    all_sources = []
    errors = []
    
    for identifier in identifiers:
        result = await get_pokemon(identifier)
        
        if result.get("error"):
            errors.append(f"{identifier}: {result['error']}")
            continue
        
        pokemon_data.append({
            "name": result["data"]["name"],
            "id": result["data"]["id"],
            "stats": result["data"]["stats"]
        })
        all_sources.extend(result["sources"])
    
    if not pokemon_data:
        return ToolResult(
            data=None,
            sources=[],
            error="Nenhum Pokémon válido encontrado para comparação"
        ).to_dict()
    
    # Calcular diferenças por estatística
    stat_names = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]
    comparisons = {}
    
    for stat in stat_names:
        values = [p["stats"].get(stat, 0) for p in pokemon_data]
        max_val = max(values)
        min_val = min(values)
        
        if max_val == min_val:
            # Empate
            comparisons[stat] = {
                "max": max_val,
                "min": min_val,
                "best": [p["name"] for p in pokemon_data if p["stats"].get(stat, 0) == max_val],
                "worst": [p["name"] for p in pokemon_data if p["stats"].get(stat, 0) == min_val],
                "tie": True
            }
        else:
            comparisons[stat] = {
                "max": max_val,
                "min": min_val,
                "best": [p["name"] for p in pokemon_data if p["stats"].get(stat, 0) == max_val],
                "worst": [p["name"] for p in pokemon_data if p["stats"].get(stat, 0) == min_val],
                "tie": False
            }
    
    # Calcular soma total de estatísticas
    total_stats = [
        sum(p["stats"].values()) for p in pokemon_data
    ]
    max_total = max(total_stats)
    
    total_comparison = {
        "totals": {p["name"]: total for p, total in zip(pokemon_data, total_stats)},
        "max": max_total,
        "best": [p["name"] for p, total in zip(pokemon_data, total_stats) if total == max_total],
        "tie": total_stats.count(max_total) > 1
    }
    
    warnings = []
    if not total_comparison["tie"]:
        warnings.append(
            "A maior soma de atributos base não é garantia de vitória em batalha"
        )
    
    if errors:
        warnings.extend(errors)
    
    return ToolResult(
        data={
            "pokemon": pokemon_data,
            "stat_comparisons": comparisons,
            "total_stats": total_comparison
        },
        sources=all_sources,
        warnings=warnings
    ).to_dict()
