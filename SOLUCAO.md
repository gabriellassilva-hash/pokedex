# Solução - PokéGarden API

## Visão Geral

Este documento descreve a solução implementada para o desafio LYNN Garden, criando a PokéGarden API - um assistente de IA para responder perguntas sobre Pokémon usando OpenAI Agents SDK, FastAPI e dados do PokéAPI v2.

## Stack Tecnológico

- **Python**: 3.12+
- **FastAPI**: Framework web assíncrono
- **OpenAI Agents SDK**: Orquestração de agentes de IA
- **Pydantic v2**: Validação de dados e settings
- **httpx**: Cliente HTTP resiliente
- **SQLite**: Cache persistente
- **pytest**: Suite de testes offline

## Instalação

### Pré-requisitos

- Python 3.12 ou superior
- Poetry (gerenciador de dependências)

### Passos

1. **Instalar Poetry** (se não tiver)
   ```bash
   pip install poetry
   ```

2. **Navegar para o projeto**
   ```bash
   cd pokegarden-api
   ```

3. **Instalar dependências**
   ```bash
   poetry install --no-root
   ```

4. **Configurar variáveis de ambiente**
   ```bash
   cp .env.example .env
   ```

   Editar `.env`:
   ```
   OPENAI_API_KEY=  # Deixe vazio para testes offline
   OPENAI_MODEL=gpt-4o-mini
   POKEAPI_BASE_URL=https://pokeapi.co/api/v2
   CACHE_DB_PATH=data/cache.db
   CACHE_TTL_SECONDS=86400
   REQUEST_TIMEOUT_SECONDS=10.0
   MAX_TURNS_PER_REQUEST=5
   CATALOG_CONFIG=default
   ```

   **IMPORTANTE:** Para usar o agente OpenAI, adicione sua API key. Para testes offline, deixe vazio.

## Estrutura do Projeto

```
pokegarden-api/
├── src/
│   ├── agent/          # Orquestrador OpenAI e prompts em português
│   ├── api/            # Endpoints FastAPI e schemas Pydantic
│   ├── catalog/        # Registro de ferramentas com descoberta dinâmica
│   ├── client/         # Cliente PokéAPI resiliente + cache SQLite
│   ├── tools/          # Ferramentas de domínio (pokemon, compare, matchups, evolution)
│   ├── config.py       # Configurações (pydantic-settings)
│   └── main.py         # Entrypoint FastAPI
├── tests/              # Testes unitários (100% offline com mocks)
├── evals/              # Runner de avaliação E01-E12
├── docs/               # Documentação de arquitetura
└── evidence/           # Relatórios de execução
```

## Testes

### Testes Unitários (Offline - NÃO precisa OpenAI API)

Os testes rodam 100% offline com mocks, sem precisar de API key do OpenAI:

```bash
# Rodar todos os testes
poetry run pytest tests/ -v

# Rodar apenas testes específicos
poetry run pytest tests/test_cache.py -v
poetry run pytest tests/test_pokeapi_client.py -v
poetry run pytest tests/test_tools.py -v
poetry run pytest tests/test_catalog.py -v
```

**Testes disponíveis:**
- `test_cache.py` - Cache SQLite com TTL (7 testes)
- `test_pokeapi_client.py` - Cliente HTTP resiliente (10 testes)
- `test_tools.py` - Ferramentas de domínio (9 testes)
- `test_catalog.py` - Catálogo e discovery (14 testes)

**Total: 40 testes unitários** ✅

### Executar o Servidor

```bash
# Para desenvolvimento (com reload)
poetry run uvicorn src.main:app --reload

# Para produção
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

**Nota:** O endpoint `/chat` requer OpenAI API key configurada. Os endpoints `/health`, `/tools` e `/tools/{name}` funcionam sem ela.

## Endpoints da API

### GET /health
Health check sem consumir tokens OpenAI ou acessar PokéAPI.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### GET /tools?query=...
Lista ferramentas disponíveis no catálogo. Opcionalmente filtra por query.

**Response:**
```json
{
  "tools": [
    {
      "name": "get_pokemon",
      "version": "1.0.0",
      "description": "Busca informações detalhadas de um Pokémon...",
      "tags": ["pokemon", "data"]
    }
  ]
}
```

### GET /tools/{name}
Obtém schema detalhado de uma ferramenta específica. Marca a ferramenta como "descoberta" na sessão.

**Response:**
```json
{
  "name": "get_pokemon",
  "version": "1.0.0",
  "description": "...",
  "input_schema": {...},
  "output_schema": {...}
}
```

### POST /chat
Endpoint principal de chat com o agente.

**Request:**
```json
{
  "message": "Quem é o Charizard?"
}
```

**Response:**
```json
{
  "request_id": "req-abc123",
  "status": "ok",
  "answer": "Charizard é um Pokémon do tipo Fogo/Voador...",
  "sources": [
    {
      "url": "https://pokeapi.co/api/v2/pokemon/6",
      "fetched_at": "2026-10-29T14:30:00Z",
      "cached": false
    }
  ],
  "tools_used": ["search_tools", "get_tool_schema", "get_pokemon"],
  "warnings": []
}
```

## Exemplos de Uso (cURL)

### Health Check
```bash
curl http://localhost:8000/health
```

### Listar Ferramentas
```bash
curl http://localhost:8000/tools
```

### Buscar Schema de Ferramenta
```bash
curl http://localhost:8000/tools/get_pokemon
```

### Chat com o Agente
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Quem é o Pikachu?"}'
```

## Configurações de Catálogo (Extension A/B)

O sistema suporta configurações diferentes do catálogo via variável `CATALOG_CONFIG`:

### Config A (CATALOG_CONFIG=config_a)
Apenas ferramentas básicas habilitadas:
- `get_pokemon`
- `compare_pokemon`
- `get_type_matchups`

**NÃO habilitado:**
- `get_evolution_chain`

### Config B (CATALOG_CONFIG=config_b)
Todas as ferramentas habilitadas:
- `get_pokemon`
- `compare_pokemon`
- `get_type_matchups`
- `get_evolution_chain`

A troca entre configs não requer alterações no código do orquestrador, prompts ou API.

## Executar Testes

### Testes Unitários (Offline)
```bash
poetry run pytest tests/ -v
```

Todos os testes rodam 100% offline usando `pytest-mock` e fixtures.

### Avaliação (E01-E12)
```bash
poetry run python evals/eval_runner.py
```

Executa os 12 casos de avaliação e salva resultados em `evidence/eval_results.json`.

## Decisões de Design

### 1. Monolito Modular
Escolhemos arquitetura de Monolito Modular em vez de microserviços iniciais por:
- Simplicidade de desenvolvimento e deploy
- Baixa latência (sem overhead de rede entre serviços)
- Fácil refatoração futura para microserviços

### 2. Cache SQLite
SQLite foi escolhido para cache persistente por:
- Zero configuração (file-based)
- Suficiente para o caso de uso
- Fácil migração futura para Redis se necessário

### 3. Guarda de Runtime de Ferramentas
Implementamos verificação de "descoberta" para prevenir execução não autorizada:
- Ferramentas de domínio só podem ser executadas após `get_tool_schema`
- Previne ataques de tool injection
- Mantém audit trail de ferramentas usadas

### 4. Normalização de Nomes
Normalização robusta de nomes Pokémon:
- Minúsculas e trim
- Substituição de caracteres especiais (♀→-f, ♂→-m)
- Remoção de acentos
- Conversão de espaços para hífens

### 5. Retry com Exponential Backoff
Cliente HTTP implementa retry para:
- Erros 5xx (3 retries)
- Rate limit 429 (3 retries)
- Network errors/timeout (3 retries)
- Backoff exponencial: 2^attempt segundos

## Limitações Conhecidas

### 1. Intercepção de Chamadas de Ferramenta
A implementação atual do orquestrador não intercepta completamente as chamadas de ferramenta para coletar `sources`, `warnings`, etc. Em produção, seria necessário:
- Hook no SDK do OpenAI Agents para interceptar tool calls
- Context manager para rastrear execution metadata
- Mais integração com o sistema de logging

### 2. Estado de Sessão
O estado de "ferramentas descobertas" é mantido em memória por instância do registry. Em cenários de:
- Múltiplas instâncias (load balancing)
- Processos worker separados
- Containers stateless

Solução futura: Redis ou outro store distribuído para estado de sessão.

### 3. Validação de Prompt Injection
A validação atual de prompt injection é básica (não inclui input do usuário no system prompt). Soluções futuras:
- Parser de instruções maliciosas
- Sanitização de input
- Rate limiting por usuário/IP
- Detecção de padrões de ataque

### 4. Evolução Recursiva
O parser de cadeia de evolução handle casos complexos, mas pode não cobrir edge cases extremos da PokéAPI (ex: evoluções muito profundas com múltiplas condições complexas).

### 5. OpenAI Agents SDK
A versão atual do SDK (`openai-agents`) pode ter limitações em:
- Tool discovery dinâmica
- Intercepção de tool calls
- Customização de runtime behavior

## Tempo de Desenvolvimento

Estimativa aproximada:
- Inicialização e configuração: 30 min
- Cliente PokéAPI + Cache: 45 min
- Ferramentas de domínio: 60 min
- Catálogo + Descoberta: 45 min
- Orquestrador OpenAI: 45 min
- FastAPI Endpoints: 30 min
- Testes + Evals: 60 min
- Documentação: 30 min

**Total: ~5 horas**

## Próximos Passos

1. Melhorar intercepção de tool calls do SDK OpenAI
2. Implementar logging estruturado em JSON
3. Adicionar métricas (Prometheus)
4. Implementar rate limiting
5. Migrar cache para Redis para escalabilidade
6. Adicionar autenticação/autorização
7. Implementar roadmap para microserviços (ver `docs/arquitetura.md`)

## Referências

- [PokéAPI v2 Documentation](https://pokeapi.co/docs/v2)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Pydantic v2 Documentation](https://docs.pydantic.dev)
