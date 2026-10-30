import os
from uuid import uuid4

import httpx
import streamlit as st


st.set_page_config(
    page_title="PokéGarden",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = os.getenv("POKEGARDEN_API_URL", "http://127.0.0.1:8000").rstrip("/")
POKEMON = [
    {"id": 1, "name": "Bulbasaur", "type": "GRAMA · VENENO", "color": "#a7c879"},
    {"id": 4, "name": "Charmander", "type": "FOGO", "color": "#e99563"},
    {"id": 7, "name": "Squirtle", "type": "ÁGUA", "color": "#77b9d1"},
    {"id": 25, "name": "Pikachu", "type": "ELÉTRICO", "color": "#e5c751"},
    {"id": 133, "name": "Eevee", "type": "NORMAL", "color": "#bd8e6e"},
    {"id": 152, "name": "Chikorita", "type": "GRAMA", "color": "#8abf8d"},
]
TOOL_EXAMPLES = {
    "search_tools": "Quais tools existem para consultar e comparar Pokémon? Busque no catálogo e liste os nomes.",
    "get_tool_schema": "Mostre quais dados a tool compare_pokemon recebe e o que ela retorna.",
    "get_pokemon": "Busque Pikachu na PokéAPI e informe tipos, altura e habilidades, citando a fonte.",
    "compare_pokemon": "Compare Pikachu e Raichu nos atributos base e diga quem tem maior ataque.",
    "get_type_matchups": "Quais tipos são mais efetivos contra Charizard? Mostre fraquezas e imunidades.",
    "get_evolution_chain": "Mostre a cadeia evolutiva de Bulbasaur e as condições para evoluir.",
}

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root {
        --ink: #20362e;
        --muted: #718078;
        --leaf: #39775b;
        --leaf-dark: #183f34;
        --coral: #e77e68;
        --paper: #f2f6ef;
    }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; color: var(--ink); letter-spacing: 0; }
    [data-testid="stAppViewContainer"] {
        background-color: var(--paper);
        background-image: radial-gradient(rgba(57,119,91,.09) .7px, transparent .7px);
        background-size: 19px 19px;
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: var(--leaf-dark); }
    [data-testid="stSidebar"] * { color: #edf4e9; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #b6c8bc; }
    .block-container { max-width: 1440px; padding-top: 2rem; padding-bottom: 3rem; }
    .brand-mark { font: 700 1.5rem 'Space Grotesk', sans-serif; color: #f6f7df; }
    .brand-note { color: #aec8b8; font-size: .82rem; margin-top: -.25rem; }
    .eyebrow { color: var(--leaf); font-size: .72rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    .panel-title { font: 600 1.1rem 'Space Grotesk', sans-serif; color: var(--ink); }
    .pokemon-title { font: 600 1.02rem 'Space Grotesk', sans-serif; color: var(--ink); }
    .type-pill { display: inline-block; border-radius: 4px; padding: 3px 7px; color: #32473c; font-size: .66rem; font-weight: 700; background: #e5eee1; }
    [data-testid="stImage"] img { object-fit: contain; }
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: rgba(32,54,46,.12); background: rgba(255,255,255,.82); border-radius: 8px;
    }
    .stButton > button {
        min-height: 2.45rem; border-radius: 6px; border: 1px solid rgba(57,119,91,.28);
        color: var(--leaf-dark); background: #f6faf3; font-weight: 600;
    }
    .stButton > button:hover { color: white; border-color: var(--leaf); background: var(--leaf); }
    [data-testid="stSidebar"] .stButton > button { color: var(--leaf-dark) !important; background: #f6faf3; }
    [data-testid="stSidebar"] .stButton > button p { color: var(--leaf-dark) !important; }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] { color: #20362e !important; background: #e8c86b; border-color: #e8c86b; }
    [data-testid="stSidebar"] .stButton > button:hover { color: white !important; background: var(--leaf); }
    [data-testid="stSidebar"] .stButton > button:hover p { color: white !important; }
    [data-testid="stChatMessage"] {
        min-width: 0; max-width: 100%; overflow: hidden;
        border-radius: 8px; border: 1px solid rgba(32,54,46,.08); background: rgba(255,255,255,.82);
    }
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] { max-width: 100%; overflow-wrap: anywhere; }
    [data-testid="stChatMessage"] table { display: block; width: 100%; max-width: 100%; overflow-x: auto; }
    [data-testid="stChatMessage"] th, [data-testid="stChatMessage"] td { white-space: nowrap; }
    [data-testid="stChatMessage"] pre { max-width: 100%; overflow-x: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
    [data-testid="stChatInput"] { border-color: rgba(57,119,91,.3); border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=20)
def api_health() -> bool:
    try:
        return httpx.get(f"{API_URL}/health", timeout=3).is_success
    except httpx.HTTPError:
        return False


@st.cache_data(ttl=30)
def get_tools(query: str = "") -> list[dict]:
    response = httpx.get(
        f"{API_URL}/tools",
        params={"query": query} if query else None,
        timeout=5,
    )
    response.raise_for_status()
    return response.json().get("tools", [])


@st.cache_data(ttl=30)
def get_tool_schema(name: str) -> dict:
    response = httpx.get(f"{API_URL}/tools/{name}", timeout=5)
    response.raise_for_status()
    return response.json()


def get_saved_chats() -> list[dict]:
    response = httpx.get(f"{API_URL}/chats", timeout=10)
    response.raise_for_status()
    return response.json().get("chats", [])


def create_saved_chat(title: str = "Nova conversa") -> dict:
    response = httpx.post(f"{API_URL}/chats", json={"title": title}, timeout=10)
    response.raise_for_status()
    return response.json()


def get_saved_chat(chat_id: str) -> dict:
    response = httpx.get(f"{API_URL}/chats/{chat_id}", timeout=10)
    response.raise_for_status()
    return response.json()


def load_saved_chats() -> None:
    try:
        chats = get_saved_chats()
        if not chats:
            chats = [create_saved_chat("Conversa 1")]

        st.session_state.conversations = {chat["id"]: chat for chat in chats}
        active_id = st.session_state.active_conversation_id
        if active_id not in st.session_state.conversations:
            active_id = chats[0]["id"]
            st.session_state.active_conversation_id = active_id
        st.session_state.conversations[active_id] = get_saved_chat(active_id)
        st.session_state.chat_store_error = None
    except httpx.HTTPError:
        st.session_state.conversations = {}
        st.session_state.active_conversation_id = None
        st.session_state.chat_store_error = "Histórico indisponível. Verifique a configuração do Redis."


def create_conversation() -> None:
    try:
        conversation = create_saved_chat()
        st.session_state.active_conversation_id = conversation["id"]
        st.session_state.chat_store_error = None
    except httpx.HTTPError:
        st.session_state.chat_store_error = "Não foi possível criar a conversa. Verifique o Redis."
    st.session_state.pending_prompt = None
    st.session_state.last_chat_error = None


def select_conversation(conversation_id: str) -> None:
    st.session_state.active_conversation_id = conversation_id
    st.session_state.pending_prompt = None
    st.session_state.last_chat_error = None


def use_tool_example(prompt: str) -> None:
    st.session_state.app_section = "Pokédex e chat"
    st.session_state.pending_prompt = prompt


def choose_pokemon(name: str) -> None:
    st.session_state.selected_pokemon = name
    st.session_state.pending_prompt = f"Quero conhecer melhor o Pokémon {name}."


def send_message(prompt: str) -> None:
    chat_id = st.session_state.active_conversation_id
    if not chat_id:
        st.session_state.last_chat_error = "Crie uma conversa depois de configurar o Redis."
        return
    st.session_state.last_chat_error = None

    try:
        response = httpx.post(
            f"{API_URL}/chats/{chat_id}/messages",
            json={"message": prompt},
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "error":
            st.session_state.last_chat_error = payload.get("answer", "Erro ao processar a mensagem.")
    except httpx.HTTPError:
        st.session_state.last_chat_error = "Não consegui salvar a mensagem. Verifique a conexão com a API e o Redis."


if "conversations" not in st.session_state:
    st.session_state.conversations = {}
if "active_conversation_id" not in st.session_state:
    st.session_state.active_conversation_id = None
if "chat_store_error" not in st.session_state:
    st.session_state.chat_store_error = None
if "selected_pokemon" not in st.session_state:
    st.session_state.selected_pokemon = "Pikachu"
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "last_chat_error" not in st.session_state:
    st.session_state.last_chat_error = None
load_saved_chats()

with st.sidebar:
    st.markdown('<div class="brand-mark">PokéGarden</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-note">Pokédex · assistente de campo</div>', unsafe_allow_html=True)
    st.divider()
    st.radio("Seção", ["Pokédex e chat", "Tools"], key="app_section")
    st.divider()
    if api_health():
        st.success("API conectada", icon="✅")
    else:
        st.warning("API indisponível", icon="⚠️")
    st.caption("Modelo configurado no servidor")
    st.divider()
    st.button("Nova conversa", on_click=create_conversation, use_container_width=True)
    if st.session_state.chat_store_error:
        st.warning(st.session_state.chat_store_error)
    st.caption(f"{len(st.session_state.conversations)} conversas salvas")
    for conversation_id, conversation in reversed(list(st.session_state.conversations.items())):
        st.button(
            conversation["title"],
            key=f"conversation-{conversation_id}",
            on_click=select_conversation,
            args=(conversation_id,),
            use_container_width=True,
            type="primary" if conversation_id == st.session_state.active_conversation_id else "secondary",
        )

if st.session_state.app_section == "Tools":
    st.markdown('<div class="eyebrow">Catálogo extensível</div>', unsafe_allow_html=True)
    st.title("Tools disponíveis")
    tool_query = st.text_input("Buscar tools", placeholder="Nome, domínio ou descrição")
    try:
        tools = get_tools(tool_query.strip())
        if not tools:
            st.info("Nenhuma tool corresponde a esta busca.")
        else:
            st.caption(f"{len(tools)} tools ativas no catálogo")
            for tool in tools:
                with st.container(border=True):
                    title_col, version_col = st.columns([0.82, 0.18], vertical_alignment="center")
                    with title_col:
                        st.markdown(f'<div class="panel-title">{tool["name"]}</div>', unsafe_allow_html=True)
                    with version_col:
                        st.caption(f"v{tool['version']}")
                    st.write(tool["description"])
                    if tool.get("tags"):
                        st.caption(" · ".join(tool["tags"]))
                    example = TOOL_EXAMPLES.get(tool["name"])
                    if example:
                        st.caption("Exemplo de prompt")
                        st.code(example)
                        st.button(
                            "Testar no chat",
                            key=f"try-tool-{tool['name']}",
                            on_click=use_tool_example,
                            args=(example,),
                        )
                    with st.expander("Schema de entrada e saída"):
                        try:
                            schema = get_tool_schema(tool["name"])
                            input_col, output_col = st.columns(2)
                            with input_col:
                                st.caption("Entrada")
                                st.json(schema.get("input_schema", {}))
                            with output_col:
                                st.caption("Saída")
                                st.json(schema.get("output_schema", {}))
                        except httpx.HTTPError:
                            st.error("Não foi possível carregar o schema desta tool.")
    except httpx.HTTPError:
        st.error("Não foi possível carregar o catálogo. Verifique a conexão com a API.")
    st.stop()

left, right = st.columns([0.95, 1.05], gap="large")

with left:
    st.markdown('<div class="eyebrow">Pokédex · dados da PokéAPI</div>', unsafe_allow_html=True)
    st.title("Pokémon em destaque")
    query = st.text_input("Buscar", placeholder="Nome ou número", label_visibility="collapsed")
    filtered = [
        pokemon for pokemon in POKEMON
        if query.lower() in pokemon["name"].lower() or query in str(pokemon["id"])
    ]

    if filtered:
        rows = [st.columns(3, gap="small") for _ in range((len(filtered) + 2) // 3)]
        for index, pokemon in enumerate(filtered):
            column = rows[index // 3][index % 3]
            with column:
                with st.container(border=True):
                    image_url = (
                        "https://raw.githubusercontent.com/PokeAPI/sprites/master/"
                        f"sprites/pokemon/other/official-artwork/{pokemon['id']}.png"
                    )
                    st.image(image_url, width=150)
                    st.markdown(
                        f'<div class="pokemon-title">#{pokemon["id"]:03d} · {pokemon["name"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<span class="type-pill">{pokemon["type"]}</span>',
                        unsafe_allow_html=True,
                    )
                    st.write("")
                    st.button(
                        "Conversar",
                        key=f"pokemon-{pokemon['id']}",
                        on_click=choose_pokemon,
                        args=(pokemon["name"],),
                        use_container_width=True,
                    )
    else:
        st.info("Nenhum Pokémon encontrado nesta seleção.")

with right:
    st.markdown('<div class="eyebrow">Assistente · contexto da conversa ativo</div>', unsafe_allow_html=True)
    st.title("Seu diário de treinador")
    conversation = st.session_state.conversations.get(st.session_state.active_conversation_id, {})
    messages = conversation.get("messages", [])
    selected = next(
        (pokemon for pokemon in POKEMON if pokemon["name"] == st.session_state.selected_pokemon),
        POKEMON[3],
    )
    context_col, context_text = st.columns([0.3, 0.7], vertical_alignment="center")
    with context_col:
        st.image(
            "https://raw.githubusercontent.com/PokeAPI/sprites/master/"
            f"sprites/pokemon/other/official-artwork/{selected['id']}.png",
            width=100,
        )
    with context_text:
        st.markdown(f'<div class="pokemon-title">#{selected["id"]:03d} · {selected["name"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<span class="type-pill">{selected["type"]}</span>', unsafe_allow_html=True)

    if not messages and st.session_state.active_conversation_id:
        st.caption("Conversa pronta")
        for prompt in (
            f"Quais são os pontos fortes de {selected['name']}?",
            f"Com quem {selected['name']} evolui ou combina bem?",
        ):
            st.button(
                prompt,
                key=f"suggestion-{len(prompt)}",
                on_click=send_message,
                args=(prompt,),
                use_container_width=True,
            )

    pending = st.session_state.pending_prompt
    if pending:
        st.session_state.pending_prompt = None
        send_message(pending)
        st.rerun()

    with st.container(height=560, border=False):
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if st.session_state.last_chat_error:
        st.error("A API retornou um erro. Confira os créditos e a configuração do modelo.")

    prompt = st.chat_input("Pergunte sobre Pokémon, tipos ou estratégias")
    if prompt:
        send_message(prompt)
        st.rerun()