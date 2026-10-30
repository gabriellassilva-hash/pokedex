import asyncio

import pytest

from src.client.chat_store import ChatStore, ChatStoreUnavailable


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.lists = {}
        self.sorted_sets = {}

    async def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def zadd(self, key, mapping):
        self.sorted_sets.setdefault(key, {}).update(mapping)

    async def zrevrange(self, key, start, end):
        items = sorted(self.sorted_sets.get(key, {}).items(), key=lambda item: item[1], reverse=True)
        return [item[0] for item in items[start:]]

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def lrange(self, key, start, end):
        values = self.lists.get(key, [])
        return values[start:] if end == -1 else values[start:end + 1]

    async def llen(self, key):
        return len(self.lists.get(key, []))


def test_chat_store_persists_and_lists_messages():
    store = ChatStore(redis_url="redis://unused", redis_client=FakeRedis())

    async def exercise_store():
        created = await store.create_chat()
        await store.add_message(created["id"], "user", "Quem é Pikachu?")
        await store.add_message(created["id"], "assistant", "Pikachu é elétrico.")
        loaded = await store.get_chat(created["id"])
        listed = await store.list_chats()
        return created, loaded, listed

    created, loaded, listed = asyncio.run(exercise_store())

    assert loaded["title"] == "Quem é Pikachu?"
    assert loaded["message_count"] == 2
    assert [message["role"] for message in loaded["messages"]] == ["user", "assistant"]
    assert listed[0]["id"] == created["id"]
    assert listed[0]["message_count"] == 2


def test_chat_store_requires_redis_url():
    store = ChatStore(redis_url="")

    with pytest.raises(ChatStoreUnavailable, match="REDIS_URL"):
        asyncio.run(store.list_chats())