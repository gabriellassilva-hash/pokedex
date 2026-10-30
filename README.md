# PokéGarden API

API de assistente de Pokémon usando OpenAI Agents SDK, FastAPI e dados do PokéAPI v2.

## 🚀 Guia Rápido

### Instalação

```bash
# Instalar Poetry (se não tiver)
pip install poetry

# Instalar dependências
cd pokegarden-api
poetry install --no-root

# Configurar ambiente
cp .env.example .env
# Editar .env (configure REDIS_URL e GROQ_API_KEY ou OPENAI_API_KEY)
```

### Testes (Offline - Sem OpenAI API)

```bash
# Rodar toda a suíte de testes
poetry run pytest tests/ -v
```

### Executar Servidor

```bash
# Desenvolvimento
poetry run uvicorn src.main:app --reload

# Produção
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### Interface Streamlit

Em outro terminal, com a API em execução:

```bash
poetry run streamlit run streamlit_app.py
```

Configure `POKEGARDEN_API_URL` se a API estiver em outro endereço. Conversas e mensagens ficam persistidas no Redis; o chat reabre o histórico completo e envia até 20 mensagens anteriores como contexto ao agente.

### Endpoints

- `GET /health` - Health check (sem tokens OpenAI)
- `GET /tools` - Listar ferramentas disponíveis
- `GET /tools/{name}` - Obter schema de ferramenta
- `POST /chat` - Chat com agente (prioriza GROQ_API_KEY quando configurada; caso contrário usa OPENAI_API_KEY)
- `POST /chats` - Criar conversa persistente
- `GET /chats` - Listar conversas salvas
- `GET /chats/{chat_id}` - Recuperar mensagens de uma conversa
- `POST /chats/{chat_id}/messages` - Salvar mensagem e receber resposta do agente

## Contexto

Este projeto foi desenvolvido como parte do desafio LYNN Garden, criando um assistente de IA que responde perguntas sobre Pokémon usando uma arquitetura de Monolito Modular em Python 3.12+.

## Stack Tecnológico

- Python 3.12+
- FastAPI
- OpenAI Agents SDK (`openai-agents`) - **opcional** (para agente)
- Pydantic v2
- httpx (cliente HTTP resiliente)
- redis-py (persistência de conversas)
- SQLite (cache persistente)
- pytest (testes offline)
- Poetry (gerenciamento de dependências)

## Arquitetura

O projeto segue uma arquitetura de Monolito Modular com isolamento estrito de domínios:

```
src/
├── agent/          # Orquestrador do agente OpenAI e prompts
├── api/            # Endpoints FastAPI e schemas
├── catalog/        # Registro de ferramentas e descoberta dinâmica
├── client/         # Clientes PokéAPI/Redis e cache SQLite
├── tools/          # Ferramentas de domínio (pokemon, compare, matchups, evolution)
├── config.py       # Configurações de ambiente
└── main.py         # Entrypoint FastAPI
```

## Documentação

- `SOLUCAO.md` - Guia de solução, instalação e limitações conhecidas
- `docs/arquitetura.md` - Nota de arquitetura e roadmap para microserviços
