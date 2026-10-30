from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from src.config import settings
from src.tools.base import ToolResult


class ToolMetadata(BaseModel):
    """Metadados de uma ferramenta registrada."""
    name: str
    version: str
    description: str
    tags: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    enabled: bool


@dataclass(frozen=True)
class ToolRegistration:
    handler: Callable[..., Awaitable[Any]]
    input_model: type[BaseModel]
    output_model: type[BaseModel]


class ToolValidationError(ValueError):
    """Raised when a registered tool input or output violates its schema."""


class ToolRegistry:
    """Registro de ferramentas com busca dinâmica e guarda de segurança em runtime."""
    
    def __init__(self):
        self._tools: dict[str, ToolMetadata] = {}
        self._registrations: dict[str, ToolRegistration] = {}
        self._discovered_tools: set[str] = set()
        self._load_tools()
        self._register_builtin_tools()

    def register_tool(
        self,
        metadata: ToolMetadata,
        handler: Callable[..., Awaitable[Any]],
        input_model: type[BaseModel],
        output_model: type[BaseModel],
    ) -> None:
        """Register a tool implementation and derive its public schemas from Pydantic."""
        if metadata.name in self._registrations:
            raise ValueError(f"Tool '{metadata.name}' já está registrada")

        metadata.input_schema = input_model.model_json_schema()
        metadata.output_schema = output_model.model_json_schema()
        self._tools[metadata.name] = metadata
        self._registrations[metadata.name] = ToolRegistration(
            handler=handler,
            input_model=input_model,
            output_model=output_model,
        )

    def _register_builtin_tools(self) -> None:
        from src.tools.base import ToolOutput
        from src.tools.compare import ComparePokemonInput, compare_pokemon
        from src.tools.evolution import GetEvolutionChainInput, get_evolution_chain
        from src.tools.matchups import GetTypeMatchupsInput, get_type_matchups
        from src.tools.pokemon import GetPokemonInput, get_pokemon

        implementations = {
            "get_pokemon": (get_pokemon, GetPokemonInput),
            "compare_pokemon": (compare_pokemon, ComparePokemonInput),
            "get_type_matchups": (get_type_matchups, GetTypeMatchupsInput),
            "get_evolution_chain": (get_evolution_chain, GetEvolutionChainInput),
        }
        for name, (handler, input_model) in implementations.items():
            metadata = self._tools.get(name)
            if metadata is not None and metadata.enabled:
                self.register_tool(metadata, handler, input_model, ToolOutput)

    def get_registration(self, name: str) -> ToolRegistration | None:
        return self._registrations.get(name)

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.check_tool_execution_allowed(name):
            raise PermissionError(f"Tool '{name}' não foi descoberta nesta requisição")
        registration = self.get_registration(name)
        if registration is None:
            raise KeyError(f"Tool '{name}' não possui implementação registrada")

        try:
            validated_input = registration.input_model.model_validate(arguments)
        except ValidationError as error:
            raise ToolValidationError(f"Entrada inválida para '{name}': {error}") from error

        result = await registration.handler(**validated_input.model_dump())
        try:
            validated_output = registration.output_model.model_validate(result)
        except ValidationError as error:
            raise ToolValidationError(f"Saída inválida para '{name}': {error}") from error
        return validated_output.model_dump(mode="json")
    
    def _load_tools(self) -> None:
        """Carrega ferramentas baseadas na configuração do catálogo."""
        config = settings.catalog_config
        
        # Ferramentas de descoberta (sempre disponíveis)
        self._tools["search_tools"] = ToolMetadata(
            name="search_tools",
            version="1.0.0",
            description="Busca ferramentas disponíveis no catálogo por nome, descrição ou tags",
            tags=["discovery", "catalog"],
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca"
                    }
                },
                "required": ["query"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "tools": {
                        "type": "array",
                        "items": {
                            "type": "object"
                        }
                    }
                }
            },
            enabled=True
        )
        
        self._tools["get_tool_schema"] = ToolMetadata(
            name="get_tool_schema",
            version="1.0.0",
            description="Obtém o schema de input detalhado de uma ferramenta específica",
            tags=["discovery", "catalog"],
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nome da ferramenta"
                    }
                },
                "required": ["name"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "object"
                    }
                }
            },
            enabled=True
        )
        
        # Ferramentas de domínio - Configuração A (sem evolution)
        if config == "config_a":
            self._tools["get_pokemon"] = ToolMetadata(
                name="get_pokemon",
                version="1.0.0",
                description="Busca informações detalhadas de um Pokémon (ID, nome, altura, peso, tipos, habilidades, estatísticas base)",
                tags=["pokemon", "data"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name_or_id": {
                            "type": "string",
                            "description": "Nome ou ID do Pokémon"
                        }
                    },
                    "required": ["name_or_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
            
            self._tools["compare_pokemon"] = ToolMetadata(
                name="compare_pokemon",
                version="1.0.0",
                description="Compara estatísticas base de 2 a 6 Pokémon",
                tags=["pokemon", "comparison"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                            "maxItems": 6
                        }
                    },
                    "required": ["identifiers"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
            
            self._tools["get_type_matchups"] = ToolMetadata(
                name="get_type_matchups",
                version="1.0.0",
                description="Calcula efetividade de tipos defensiva de um Pokémon",
                tags=["pokemon", "types"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name_or_id": {
                            "type": "string",
                            "description": "Nome ou ID do Pokémon"
                        }
                    },
                    "required": ["name_or_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
            
            # get_evolution_chain NÃO registrado no config_a
            self._tools["get_evolution_chain"] = ToolMetadata(
                name="get_evolution_chain",
                version="1.0.0",
                description="Obtém a cadeia de evolução de um Pokémon",
                tags=["pokemon", "evolution"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name_or_id": {
                            "type": "string",
                            "description": "Nome ou ID do Pokémon"
                        }
                    },
                    "required": ["name_or_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=False
            )
        
        # Configuração B (todas as ferramentas)
        elif config == "config_b":
            self._tools["get_pokemon"] = ToolMetadata(
                name="get_pokemon",
                version="1.0.0",
                description="Busca informações detalhadas de um Pokémon (ID, nome, altura, peso, tipos, habilidades, estatísticas base)",
                tags=["pokemon", "data"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name_or_id": {
                            "type": "string",
                            "description": "Nome ou ID do Pokémon"
                        }
                    },
                    "required": ["name_or_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
            
            self._tools["compare_pokemon"] = ToolMetadata(
                name="compare_pokemon",
                version="1.0.0",
                description="Compara estatísticas base de 2 a 6 Pokémon",
                tags=["pokemon", "comparison"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                            "maxItems": 6
                        }
                    },
                    "required": ["identifiers"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
            
            self._tools["get_type_matchups"] = ToolMetadata(
                name="get_type_matchups",
                version="1.0.0",
                description="Calcula efetividade de tipos defensiva de um Pokémon",
                tags=["pokemon", "types"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name_or_id": {
                            "type": "string",
                            "description": "Nome ou ID do Pokémon"
                        }
                    },
                    "required": ["name_or_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
            
            self._tools["get_evolution_chain"] = ToolMetadata(
                name="get_evolution_chain",
                version="1.0.0",
                description="Obtém a cadeia de evolução de um Pokémon",
                tags=["pokemon", "evolution"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name_or_id": {
                            "type": "string",
                            "description": "Nome ou ID do Pokémon"
                        }
                    },
                    "required": ["name_or_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
        
        # Configuração padrão (todas as ferramentas)
        else:
            self._tools["get_pokemon"] = ToolMetadata(
                name="get_pokemon",
                version="1.0.0",
                description="Busca informações detalhadas de um Pokémon (ID, nome, altura, peso, tipos, habilidades, estatísticas base)",
                tags=["pokemon", "data"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name_or_id": {
                            "type": "string",
                            "description": "Nome ou ID do Pokémon"
                        }
                    },
                    "required": ["name_or_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
            
            self._tools["compare_pokemon"] = ToolMetadata(
                name="compare_pokemon",
                version="1.0.0",
                description="Compara estatísticas base de 2 a 6 Pokémon",
                tags=["pokemon", "comparison"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                            "maxItems": 6
                        }
                    },
                    "required": ["identifiers"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
            
            self._tools["get_type_matchups"] = ToolMetadata(
                name="get_type_matchups",
                version="1.0.0",
                description="Calcula efetividade de tipos defensiva de um Pokémon",
                tags=["pokemon", "types"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name_or_id": {
                            "type": "string",
                            "description": "Nome ou ID do Pokémon"
                        }
                    },
                    "required": ["name_or_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
            
            self._tools["get_evolution_chain"] = ToolMetadata(
                name="get_evolution_chain",
                version="1.0.0",
                description="Obtém a cadeia de evolução de um Pokémon",
                tags=["pokemon", "evolution"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name_or_id": {
                            "type": "string",
                            "description": "Nome ou ID do Pokémon"
                        }
                    },
                    "required": ["name_or_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object"},
                        "sources": {"type": "array"},
                        "warnings": {"type": "array"}
                    }
                },
                enabled=True
            )
    
    def search_tools(self, query: str) -> list[dict[str, Any]]:
        """
        Busca ferramentas por nome, descrição ou tags (busca lexical).
        
        Args:
            query: Termo de busca
            
        Returns:
            Lista de ferramentas encontradas
        """
        query_lower = query.lower()
        results = []
        
        for tool_name, metadata in self._tools.items():
            if not metadata.enabled:
                continue
            
            # Buscar em nome, descrição e tags
            if (
                query_lower in metadata.name.lower() or
                query_lower in metadata.description.lower() or
                any(query_lower in tag.lower() for tag in metadata.tags)
            ):
                results.append({
                    "name": metadata.name,
                    "version": metadata.version,
                    "description": metadata.description,
                    "tags": metadata.tags
                })
        
        return results
    
    def get_tool_schema(self, name: str) -> dict[str, Any] | None:
        """
        Obtém o schema de input de uma ferramenta específica.
        
        Marca a ferramenta como "descoberta" na sessão atual.
        
        Args:
            name: Nome da ferramenta
            
        Returns:
            Schema da ferramenta ou None se não encontrada/desabilitada
        """
        metadata = self._tools.get(name)
        
        if metadata is None or not metadata.enabled:
            return None
        
        # Marcar como descoberta nesta sessão
        self._discovered_tools.add(name)
        
        return {
            "name": metadata.name,
            "version": metadata.version,
            "description": metadata.description,
            "input_schema": metadata.input_schema,
            "output_schema": metadata.output_schema
        }
    
    def check_tool_execution_allowed(self, name: str) -> bool:
        """
        Verifica se a execução de uma ferramenta é permitida (guarda de runtime).
        
        Uma ferramenta só pode ser executada se foi descoberta via get_tool_schema
        na sessão atual.
        
        Args:
            name: Nome da ferramenta
            
        Returns:
            True se permitida, False caso contrário
        """
        # Ferramentas de descoberta sempre permitidas
        if name in ["search_tools", "get_tool_schema"]:
            return True
        
        # Verificar se foi descoberta
        return name in self._discovered_tools
    
    def reset_session(self) -> None:
        """Reseta o estado de ferramentas descobertas (nova sessão)."""
        self._discovered_tools.clear()
    
    def get_all_enabled_tools(self) -> list[dict[str, Any]]:
        """
        Retorna todas as ferramentas habilitadas no catálogo.
        
        Returns:
            Lista de metadados de ferramentas habilitadas
        """
        return [
            {
                "name": metadata.name,
                "version": metadata.version,
                "description": metadata.description,
                "tags": metadata.tags
            }
            for metadata in self._tools.values()
            if metadata.enabled
        ]


# Instância global do registro
tool_registry = ToolRegistry()
