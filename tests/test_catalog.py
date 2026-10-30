import pytest

from src.catalog.registry import ToolRegistry, tool_registry


@pytest.fixture
def registry():
    """Fixture para registro de ferramentas."""
    return ToolRegistry()


def test_search_tools_found(registry):
    """Testa busca de ferramentas encontradas."""
    results = registry.search_tools("pokemon")
    
    assert len(results) > 0
    assert any("pokemon" in tool["name"].lower() for tool in results)


def test_search_tools_by_tag(registry):
    """Testa busca por tag."""
    results = registry.search_tools("data")
    
    assert len(results) > 0
    assert any("data" in tag for tool in results for tag in tool["tags"])


def test_search_tools_not_found(registry):
    """Testa busca sem resultados."""
    results = registry.search_tools("nonexistent_tool_xyz")
    
    assert len(results) == 0


def test_get_tool_schema_enabled(registry):
    """Testa obtenção de schema de ferramenta habilitada."""
    schema = registry.get_tool_schema("get_pokemon")
    
    assert schema is not None
    assert schema["name"] == "get_pokemon"
    assert "input_schema" in schema
    assert "output_schema" in schema
    assert "description" in schema


def test_get_tool_schema_disabled(registry):
    """Testa obtenção de schema de ferramenta desabilitada."""
    # Ferramenta desabilitada retorna None
    schema = registry.get_tool_schema("disabled_tool")
    
    assert schema is None


def test_get_tool_schema_marks_discovered(registry):
    """Testa que get_tool_schema marca ferramenta como descoberta."""
    # Resetar estado
    registry.reset_session()
    
    # Inicialmente não descoberta
    assert not registry.check_tool_execution_allowed("get_pokemon")
    
    # Obter schema
    registry.get_tool_schema("get_pokemon")
    
    # Agora deve estar descoberta
    assert registry.check_tool_execution_allowed("get_pokemon")


def test_check_tool_execution_allowed_discovery_tools(registry):
    """Testa que ferramentas de descoberta sempre são permitidas."""
    assert registry.check_tool_execution_allowed("search_tools")
    assert registry.check_tool_execution_allowed("get_tool_schema")


def test_check_tool_execution_allowed_not_discovered(registry):
    """Testa bloqueio de ferramenta não descoberta."""
    registry.reset_session()
    
    # Ferramenta de domínio não descoberta
    assert not registry.check_tool_execution_allowed("get_pokemon")


def test_check_tool_execution_allowed_after_discovery(registry):
    """Testa permissão após descoberta."""
    registry.reset_session()
    
    # Descobrir ferramenta
    registry.get_tool_schema("get_pokemon")
    
    # Agora permitida
    assert registry.check_tool_execution_allowed("get_pokemon")


def test_reset_session(registry):
    """Testa reset de sessão."""
    # Descobrir ferramenta
    registry.get_tool_schema("get_pokemon")
    assert registry.check_tool_execution_allowed("get_pokemon")
    
    # Resetar
    registry.reset_session()
    
    # Não deve mais ser permitida
    assert not registry.check_tool_execution_allowed("get_pokemon")


def test_get_all_enabled_tools(registry):
    """Testa listagem de todas as ferramentas habilitadas."""
    tools = registry.get_all_enabled_tools()
    
    assert len(tools) > 0
    # Ferramentas de descoberta sempre presentes
    assert any(tool["name"] == "search_tools" for tool in tools)
    assert any(tool["name"] == "get_tool_schema" for tool in tools)
    
    # Todas devem ter campos obrigatórios
    for tool in tools:
        assert "name" in tool
        assert "version" in tool
        assert "description" in tool
        assert "tags" in tool


def test_config_a_excludes_evolution(registry):
    """Testa que config_a exclui get_evolution_chain."""
    from src.config import settings
    
    # Sobrescrever config temporariamente
    original_config = settings.catalog_config
    settings.catalog_config = "config_a"
    
    registry_a = ToolRegistry()
    
    # get_evolution_chain deve estar desabilitado
    evolution_tool = registry_a._tools.get("get_evolution_chain")
    assert evolution_tool is not None
    assert evolution_tool.enabled is False
    
    # get_pokemon deve estar habilitado
    pokemon_tool = registry_a._tools.get("get_pokemon")
    assert pokemon_tool is not None
    assert pokemon_tool.enabled is True
    
    # Restaurar config
    settings.catalog_config = original_config


def test_config_b_includes_evolution(registry):
    """Testa que config_b inclui get_evolution_chain."""
    from src.config import settings
    
    # Sobrescrever config temporariamente
    original_config = settings.catalog_config
    settings.catalog_config = "config_b"
    
    registry_b = ToolRegistry()
    
    # get_evolution_chain deve estar habilitado
    evolution_tool = registry_b._tools.get("get_evolution_chain")
    assert evolution_tool is not None
    assert evolution_tool.enabled is True
    
    # get_pokemon também habilitado
    pokemon_tool = registry_b._tools.get("get_pokemon")
    assert pokemon_tool is not None
    assert pokemon_tool.enabled is True
    
    # Restaurar config
    settings.catalog_config = original_config
