import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.config import settings


class ChatStoreUnavailable(RuntimeError):
    """Raised when persistent chat storage is not configured or reachable."""


class ChatStore:
    def __init__(self, redis_url: str | None = None, redis_client: Any | None = None):
        self.redis_url = settings.redis_url if redis_url is None else redis_url
        self._redis_client = redis_client

    def _client(self) -> Any:
        if self._redis_client is not None:
            return self._redis_client
        if not self.redis_url:
            raise ChatStoreUnavailable("REDIS_URL não está configurada")
        self._redis_client = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis_client

    async def close(self) -> None:
        client = self._redis_client
        self._redis_client = None
        if client is not None:
            close = getattr(client, "aclose", None)
            if close is not None:
                await close()

    @staticmethod
    def _meta_key(chat_id: str) -> str:
        return f"pokegarden:chat:{chat_id}:meta"

    @staticmethod
    def _messages_key(chat_id: str) -> str:
        return f"pokegarden:chat:{chat_id}:messages"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    async def create_chat(self, title: str = "Nova conversa") -> dict[str, Any]:
        now = self._now()
        chat_id = uuid4().hex
        metadata = {
            "id": chat_id,
            "title": title,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        try:
            client = self._client()
            await client.hset(self._meta_key(chat_id), mapping=metadata)
            await client.zadd("pokegarden:chats", {chat_id: now.timestamp()})
        except RedisError as error:
            raise ChatStoreUnavailable("Não foi possível acessar o Redis") from error
        return {**metadata, "message_count": 0}

    async def list_chats(self) -> list[dict[str, Any]]:
        try:
            client = self._client()
            chat_ids = await client.zrevrange("pokegarden:chats", 0, -1)
            chats = []
            for chat_id in chat_ids:
                metadata = await client.hgetall(self._meta_key(chat_id))
                if metadata:
                    message_count = await client.llen(self._messages_key(chat_id))
                    chats.append({**metadata, "message_count": message_count})
            return chats
        except RedisError as error:
            raise ChatStoreUnavailable("Não foi possível acessar o Redis") from error

    async def get_chat(self, chat_id: str) -> dict[str, Any] | None:
        try:
            client = self._client()
            metadata = await client.hgetall(self._meta_key(chat_id))
            if not metadata:
                return None
            encoded_messages = await client.lrange(self._messages_key(chat_id), 0, -1)
            messages = [json.loads(message) for message in encoded_messages]
            return {**metadata, "message_count": len(messages), "messages": messages}
        except RedisError as error:
            raise ChatStoreUnavailable("Não foi possível acessar o Redis") from error

    async def add_message(self, chat_id: str, role: str, content: str) -> dict[str, Any] | None:
        try:
            client = self._client()
            metadata = await client.hgetall(self._meta_key(chat_id))
            if not metadata:
                return None

            now = self._now()
            message = {"role": role, "content": content, "created_at": now.isoformat()}
            await client.rpush(self._messages_key(chat_id), json.dumps(message, ensure_ascii=False))

            updates = {"updated_at": now.isoformat()}
            if role == "user" and metadata.get("title") == "Nova conversa":
                updates["title"] = content[:60]
            await client.hset(self._meta_key(chat_id), mapping=updates)
            await client.zadd("pokegarden:chats", {chat_id: now.timestamp()})
            return message
        except RedisError as error:
            raise ChatStoreUnavailable("Não foi possível acessar o Redis") from error


chat_store = ChatStore()