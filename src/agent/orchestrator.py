import asyncio
import json
from typing import Any

try:
    from agents import Agent, FunctionTool, ModelSettings, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from src.agent.prompts import SYSTEM_PROMPT
from src.catalog.registry import ToolRegistry, ToolValidationError, tool_registry
from src.config import settings


class AgentOrchestrator:
    """Descobre no catálogo e executa uma tool antes da resposta do agente."""

    def __init__(self, registry: ToolRegistry | None = None):
        self.registry = registry or tool_registry
        if not OPENAI_AVAILABLE or not (settings.groq_api_key or settings.openai_api_key):
            self.enabled = False
            return

        use_groq = bool(settings.groq_api_key)
        self.client = AsyncOpenAI(
            api_key=settings.groq_api_key if use_groq else settings.openai_api_key,
            base_url=settings.groq_base_url if use_groq else None,
        )
        self.model = OpenAIChatCompletionsModel(
            model=settings.groq_model if use_groq else settings.openai_model,
            openai_client=self.client,
        )
        if use_groq:
            set_tracing_disabled(True)

        self.enabled = True
        self._chat_lock = asyncio.Lock()
        self._all_domain_tools: list[FunctionTool] = []
        self.agent = self._create_agent()

    def _create_agent(self):
        @function_tool(name_override="search_tools")
        async def search_tools_func(query: str) -> str:
            """Busca tools no catálogo por nome, descrição ou tags."""
            matches = self.registry.search_tools(query)
            if not matches:
                matches = [
                    tool for tool in self.registry.get_all_enabled_tools()
                    if tool["name"] not in {"search_tools", "get_tool_schema"}
                ]
            return json.dumps(matches, ensure_ascii=False)

        @function_tool(name_override="get_tool_schema")
        async def get_tool_schema_func(name: str) -> str:
            """Obtém e valida o schema da tool descoberta, habilitando sua execução."""
            schema = self.registry.get_tool_schema(name)
            if schema is None:
                return json.dumps({"error": f"Tool '{name}' indisponível no catálogo."}, ensure_ascii=False)
            return json.dumps(schema, ensure_ascii=False)

        self._schema_discovery_tool = get_tool_schema_func
        self._search_discovery_tool = search_tools_func

        # Pré-constrói todas as domain tools para que a API sempre as receba
        # O requisito #4 continua satisfeito: a guarda em registry.execute_tool()
        # impede execução sem get_tool_schema ter sido chamada primeiro.
        self._all_domain_tools = self._build_all_domain_tools()

        all_tools = [
            self._search_discovery_tool,
            self._schema_discovery_tool,
            *self._all_domain_tools,
        ]

        return Agent(
            name="PokeGarden Assistant",
            instructions=SYSTEM_PROMPT,
            model=self.model,
            tools=all_tools,
            reset_tool_choice=False,
        )

    def _build_all_domain_tools(self) -> list:
        """Constrói FunctionTools para todas as domain tools habilitadas no catálogo."""
        domain_tools = []
        for tool_meta in self.registry.get_all_enabled_tools():
            name = tool_meta["name"]
            if name in ("search_tools", "get_tool_schema"):
                continue
            schema = self.registry.get_tool_schema.__wrapped__(self.registry, name) if hasattr(self.registry.get_tool_schema, "__wrapped__") else self._get_schema_no_mark(name)
            tool = self._build_domain_tool(name, schema)
            if tool is not None:
                domain_tools.append(tool)
        return domain_tools

    def _get_schema_no_mark(self, name: str) -> dict[str, Any] | None:
        """Obtém schema sem marcar como descoberta (usado apenas na inicialização)."""
        metadata = self.registry._tools.get(name)
        if metadata is None or not metadata.enabled:
            return None
        return {
            "name": metadata.name,
            "version": metadata.version,
            "description": metadata.description,
            "input_schema": metadata.input_schema,
            "output_schema": metadata.output_schema,
        }

    def _build_domain_tool(self, tool_name: str, schema: dict[str, Any] | None) -> FunctionTool | None:
        if schema is None:
            return None
        registration = self.registry.get_registration(tool_name)
        if registration is None:
            return None

        async def invoke_tool(_context: Any, raw_arguments: str) -> str:
            try:
                arguments = json.loads(raw_arguments)
                result = await self.registry.execute_tool(tool_name, arguments)
            except Exception as error:
                result = {"data": None, "sources": [], "warnings": [], "error": str(error)}
            return json.dumps(result, ensure_ascii=False)

        return FunctionTool(
            name=tool_name,
            description=schema["description"],
            params_json_schema=registration.input_model.model_json_schema(),
            on_invoke_tool=invoke_tool,
            strict_json_schema=False,
        )

    def _get_initial_tools(self) -> list:
        """Retorna a lista completa de tools para cada nova requisição."""
        return [
            self._search_discovery_tool,
            self._schema_discovery_tool,
            *self._all_domain_tools,
        ]

    async def chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {
                "answer": "Agente OpenAI não disponível. Instale com: poetry install --with agent",
                "sources": [],
                "tools_used": [],
                "warnings": ["OpenAI Agents SDK não instalado ou sem chave configurada"],
            }

        async with self._chat_lock:
            self.registry.reset_session()
            self.agent.instructions = SYSTEM_PROMPT
            self.agent.tools[:] = self._get_initial_tools()
            self.agent.model_settings = ModelSettings(tool_choice="auto")
            try:
                agent_input = [*history, {"role": "user", "content": message}] if history else message
                result = await Runner.run(
                    self.agent,
                    agent_input,
                    max_turns=settings.max_turns_per_request,
                )

                tools_used = list(dict.fromkeys(
                    item.raw_item.name
                    for item in result.new_items
                    if getattr(item, "type", None) == "tool_call_item"
                ))
                sources = []
                warnings = []
                for item in result.new_items:
                    if getattr(item, "type", None) != "tool_call_output_item":
                        continue
                    try:
                        tool_result = json.loads(item.output)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    if isinstance(tool_result, dict):
                        sources.extend(tool_result.get("sources", []))
                        warnings.extend(tool_result.get("warnings", []))

                return {
                    "answer": result.final_output,
                    "sources": sources,
                    "tools_used": tools_used,
                    "warnings": warnings,
                }
            except Exception as error:
                return {
                    "answer": f"Erro ao processar requisição: {error}",
                    "sources": [],
                    "tools_used": [],
                    "warnings": [f"Erro interno: {error}"],
                }
            finally:
                self.registry.reset_session()
                self.agent.tools[:] = self._get_initial_tools()
                self.agent.model_settings = ModelSettings()


orchestrator = AgentOrchestrator()
