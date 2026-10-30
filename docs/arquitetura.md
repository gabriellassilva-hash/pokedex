# Arquitetura PokéGarden API

## Arquitetura Atual: Monolito Modular

### Visão Geral

A PokéGarden API segue uma arquitetura de **Monolito Modular**, onde o sistema é implantado como uma única unidade, mas com isolamento estrito entre domínios através de boundaries bem definidos.

### Princípios

1. **Isolamento de Domínio**: Cada módulo (`agent`, `api`, `catalog`, `client`, `tools`) tem responsabilidade única e interfaces claras.
2. **Acoplamento Frouxo**: Módulos se comunicam através de interfaces bem definidas, não dependendo de implementações internas.
3. **Coesão Alta**: Código relacionado é agrupado no mesmo módulo.
4. **Independência de Deploy**: Embora implantado como uma unidade, módulos podem ser extraídos facilmente para microserviços.

### Diagrama de Módulos

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  /health     │  │  /tools      │  │  /chat       │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  API Layer (src/api/)                    │
│  • router.py - Endpoints FastAPI                         │
│  • schemas.py - DTOs Pydantic                            │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│               Agent Layer (src/agent/)                   │
│  • orchestrator.py - OpenAI Agents SDK wrapper           │
│  • prompts.py - System prompts em português              │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│             Catalog Layer (src/catalog/)                 │
│  • registry.py - Tool registry + discovery engine        │
│  • Runtime guard for tool execution                      │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Tools Layer (src/tools/)                     │
│  • pokemon.py - get_pokemon                              │
│  • compare.py - compare_pokemon                          │
│  • matchups.py - get_type_matchups                       │
│  • evolution.py - get_evolution_chain                    │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Client Layer (src/client/)                  │
│  • pokeapi.py - HTTP client resiliente                   │
│  • cache.py - SQLite cache persistente                   │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                 External Services                        │
│  • PokéAPI v2 (https://pokeapi.co/api/v2)                │
│  • OpenAI API (GPT-4o-mini)                              │
└─────────────────────────────────────────────────────────┘
```

### Fluxo de Requisição

1. **HTTP Request** → FastAPI endpoint
2. **Router** → Valida Pydantic schema
3. **Orchestrator** → Inicializa Agent OpenAI
4. **Agent** → Usa ferramentas de descoberta (`search_tools`, `get_tool_schema`)
5. **Catalog** → Retorna metadados e marca ferramenta como descoberta
6. **Agent** → Executa ferramenta de domínio (ex: `get_pokemon`)
7. **Tool** → Consulta Client Layer
8. **Client** → Verifica cache → Se miss, faz HTTP request para PokéAPI
9. **Response** → Propaga de volta através das camadas
10. **API** → Retorna JSON estruturado com sources, warnings, etc.

### Vantagens do Monolito Modular

**Desenvolvimento:**
- Simplicidade de setup e debugging
- IDE suporte nativo (jump to definition, refactoring)
- Share de código entre módulos (sem overhead de RPC)
- Testes integrados simples

**Operacional:**
- Deploy simples (single artifact)
- Monitoramento e logging centralizados
- Menor overhead de rede (chamadas são funções locais)
- Menor latência

**Financeiro:**
- Menor custo de infraestrutura (single instance)
- Menor complexidade de DevOps
- Simpler CI/CD pipeline

### Desvantagens

**Escalabilidade:**
- Escalabilidade vertical (mais recursos) em vez de horizontal
- Single point of failure se o monolito cair
- Harder to scale individual components independently

**Manutenibilidade (Longo Prazo):**
- Codebase pode crescer significativamente
- Require disciplines rigorosas para manter boundaries
- Merge conflicts em equipe grande

## Roadmap: Migração para Event-Driven Microservices

### Motivação

A arquitetura de microserviços Event-Driven (EDA) seria apropriada quando:

- **Volume**: Milhares de requisições por segundo
- **Equipe**: Múltiplas equipes trabalhando em paralelo
- **Latência**: Requisitos de baixa latência para componentes específicos
- **Deploy**: Need independent deployment cycles per service
- **Resiliência**: Isolamento de falhas crítico

### Arquitetura Alvo

```
┌─────────────────────────────────────────────────────────┐
│                    API Gateway                            │
│  (Kong / AWS API Gateway / Traefik)                      │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Chat Service │   │ Tool Service  │   │ Cache Service │
│  (FastAPI)    │   │  (FastAPI)    │   │   (Redis)     │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Message Broker (Redis Pub/Sub)               │
│  • pokemon.request                                       │
│  • pokemon.response                                      │
│  • cache.invalidate                                      │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│Agent Service  │   │Catalog Svc   │   │Client Service │
│  (OpenAI)     │   │  (Registry)  │   │  (HTTP Client)│
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  External Services                        │
│  • PokéAPI                                                │
│  • OpenAI API                                             │
└─────────────────────────────────────────────────────────┘
```

### Componentes

#### 1. API Gateway
- **Responsabilidade**: Routing, authentication, rate limiting
- **Tecnologia**: Kong, AWS API Gateway, ou Traefik
- **Funcionalidades**:
  - JWT validation
  - Rate limiting por usuário
  - Request/response transformation
  - Circuit breaker

#### 2. Chat Service
- **Responsabilidade**: Endpoint `/chat`, request validation
- **Tecnologia**: FastAPI
- **Eventos**:
  - Publica: `chat.request` → Agent Service
  - Consome: `chat.response`

#### 3. Agent Service
- **Responsabilidade**: Orquestração OpenAI Agents
- **Tecnologia**: FastAPI + OpenAI Agents SDK
- **Eventos**:
  - Consome: `chat.request`
  - Publica: `tool.discovery.request` → Catalog Service
  - Publica: `tool.execution.request` → Tool Service
  - Publica: `chat.response`

#### 4. Catalog Service
- **Responsabilidade**: Tool registry e discovery
- **Tecnologia**: FastAPI
- **Eventos**:
  - Consome: `tool.discovery.request`
  - Publica: `tool.discovery.response`

#### 5. Tool Service
- **Responsabilidade**: Execução de ferramentas de domínio
- **Tecnologia**: FastAPI
- **Eventos**:
  - Consome: `tool.execution.request`
  - Publica: `client.request` → Client Service
  - Publica: `tool.execution.response`

#### 6. Client Service
- **Responsabilidade**: HTTP client resiliente + cache
- **Tecnologia**: FastAPI + Redis (cache)
- **Eventos**:
  - Consome: `client.request`
  - Publica: `client.response`
  - Publica: `cache.invalidate` (opcional)

#### 7. Cache Service
- **Responsabilidade**: Cache distribuído
- **Tecnologia**: Redis
- **Funcionalidades**:
  - Distributed cache
  - Pub/Sub para invalidação
  - TTL management

#### 8. Message Broker
- **Responsabilidade**: Event routing
- **Tecnologia**: Redis Pub/Sub (simples) ou RabbitMQ/Kafka (robusto)
- **Topics**:
  - `chat.request`
  - `chat.response`
  - `tool.discovery.request`
  - `tool.discovery.response`
  - `tool.execution.request`
  - `tool.execution.response`
  - `client.request`
  - `client.response`
  - `cache.invalidate`

### Docker Compose Setup

```yaml
version: '3.8'

services:
  api-gateway:
    image: kong:latest
    ports:
      - "8000:8000"
      - "8443:8443"
    environment:
      KONG_DATABASE: "off"
      KONG_PROXY_ACCESS_LOG: /dev/stdout

  chat-service:
    build: ./services/chat-service
    ports:
      - "8001:8000"
    environment:
      REDIS_URL: redis://redis:6379
      AGENT_SERVICE_URL: http://agent-service:8000

  agent-service:
    build: ./services/agent-service
    ports:
      - "8002:8000"
    environment:
      REDIS_URL: redis://redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      CATALOG_SERVICE_URL: http://catalog-service:8000
      TOOL_SERVICE_URL: http://tool-service:8000

  catalog-service:
    build: ./services/catalog-service
    ports:
      - "8003:8000"
    environment:
      REDIS_URL: redis://redis:6379

  tool-service:
    build: ./services/tool-service
    ports:
      - "8004:8000"
    environment:
      REDIS_URL: redis://redis:6379
      CLIENT_SERVICE_URL: http://client-service:8000

  client-service:
    build: ./services/client-service
    ports:
      - "8005:8000"
    environment:
      REDIS_URL: redis://redis:6379
      POKEAPI_BASE_URL: https://pokeapi.co/api/v2

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin

volumes:
  redis_data:
```

### Estrutura de Diretórios (Microservices)

```
pokegarden-microservices/
├── services/
│   ├── chat-service/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── agent-service/
│   ├── catalog-service/
│   ├── tool-service/
│   └── client-service/
├── docker-compose.yml
├── prometheus.yml
└── README.md
```

### Plano de Migração

#### Fase 1: Preparação (2-3 semanas)
- [ ] Identificar boundaries entre módulos
- [ ] Definir contracts (APIs) entre serviços
- [ ] Setup Docker Compose environment
- [ ] Implementar message broker (Redis)
- [ ] Adicionar tracing distribuído (OpenTelemetry)

#### Fase 2: Extração de Serviços (4-6 semanas)
- [ ] Extrair Client Service (primeiro, mais simples)
- [ ] Extrair Catalog Service
- [ ] Extrair Tool Service
- [ ] Extrair Agent Service
- [ ] Extrair Chat Service
- [ ] Configurar API Gateway

#### Fase 3: Migração de Eventos (2-3 semanas)
- [ ] Implementar pub/sub patterns
- [ ] Migrar chamadas síncronas para assíncronas
- [ ] Implementar saga patterns para transações
- [ ] Add dead letter queues

#### Fase 4: Operacionalização (2-3 semanas)
- [ ] Setup monitoring (Prometheus + Grafana)
- [ ] Implementar centralized logging (ELK ou Loki)
- [ ] Add alerting
- [ ] Configure auto-scaling
- [ ] Implement blue-green deployments

#### Fase 5: Otimização (contínuo)
- [ ] Performance tuning
- [ ] Cost optimization
- [ ] Security hardening
- [ ] Disaster recovery procedures

### Trade-offs: Monolito vs Microservices

| Aspecto | Monolito Modular | Event-Driven Microservices |
|---------|------------------|----------------------------|
| **Complexidade Inicial** | Baixa | Alta |
| **Latência** | Baixa (chamadas locais) | Média (network overhead) |
| **Escalabilidade** | Vertical | Horizontal |
| **Deploy** | Simples | Complexo (orquestração) |
| **Debugging** | Fácil (single process) | Difícil (distribuído) |
| **Fault Isolation** | Nenhuma | Alta |
| **Team Scaling** | Limitado | Ilimitado |
| **Tech Diversity** | Limitado | Alta |
| **Operational Cost** | Baixo | Alto |
| **Time to Market** | Rápido | Lento |

### Quando Migrar?

Migrar para microservices quando:

1. **Equipe > 10 desenvolvedores**: Dificuldade de coordenação em monolito
2. **Throughput > 10k RPS**: Necessidade de escalabilidade horizontal
3. **SLAs Diferentes**: Componentes com requisitos de latência diferentes
4. **Frequente Deploy**: Necessidade de independent deployment cycles
5. **Fault Isolation Crítico**: Um componente não pode derrubar o sistema

### Conclusão

A arquitetura de Monolito Modular é o ponto de partida ideal para o PokéGarden API, oferecendo simplicidade e velocidade de desenvolvimento. O roadmap para microserviços Event-Driven está documentado para quando o projeto atingir maturidade e escala que justifiquem a complexidade adicional.

A transição pode ser incremental, começando pela extração dos serviços mais simples (Client, Catalog) e progredindo para os mais complexos (Agent, Chat), minimizando riscos e permitindo validação contínua.
