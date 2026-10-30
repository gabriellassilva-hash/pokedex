import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlite3

from src.client.cache import Cache


@pytest.fixture
def temp_cache(tmp_path):
    """Fixture para cache temporário."""
    db_path = tmp_path / "test_cache.db"
    cache = Cache(db_path=str(db_path), ttl_seconds=3600)
    return cache


def test_cache_initialization(temp_cache):
    """Testa inicialização do cache e criação do banco de dados."""
    assert temp_cache.db_path.exists()
    
    # Verificar que a tabela foi criada
    conn = sqlite3.connect(temp_cache.db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cache'"
    )
    result = cursor.fetchone()
    conn.close()
    
    assert result is not None
    assert result[0] == "cache"


def test_cache_set_and_get(temp_cache):
    """Testa armazenamento e recuperação de entrada no cache."""
    key = "test_key"
    data = {"name": "test", "value": 123}
    source_url = "https://example.com/test"
    
    # Armazenar
    temp_cache.set(key, data, source_url)
    
    # Recuperar
    result = temp_cache.get(key)
    
    assert result is not None
    assert result["data"] == data
    assert result["source_url"] == source_url
    assert result["cached"] is True
    assert "fetched_at" in result


def test_cache_ttl_expiration(temp_cache):
    """Testa expiração por TTL."""
    key = "test_key"
    data = {"name": "test"}
    source_url = "https://example.com/test"
    
    # Armazenar
    temp_cache.set(key, data, source_url)
    
    # Recuperar imediatamente (deve funcionar)
    result = temp_cache.get(key)
    assert result is not None
    
    # Modificar cache para simular entrada expirada
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=4000)).isoformat()
    conn = sqlite3.connect(temp_cache.db_path)
    conn.execute(
        "UPDATE cache SET fetched_at = ? WHERE key = ?",
        (old_time, key)
    )
    conn.commit()
    conn.close()
    
    # Tentar recuperar entrada expirada
    result = temp_cache.get(key)
    assert result is None


def test_cache_miss(temp_cache):
    """Testa cache miss (chave não existente)."""
    result = temp_cache.get("nonexistent_key")
    assert result is None


def test_cache_overwrite(temp_cache):
    """Testa sobrescrita de entrada existente."""
    key = "test_key"
    data1 = {"version": 1}
    data2 = {"version": 2}
    source_url = "https://example.com/test"
    
    # Armazenar primeira versão
    temp_cache.set(key, data1, source_url)
    result1 = temp_cache.get(key)
    assert result1["data"] == data1
    
    # Sobrescrever
    temp_cache.set(key, data2, source_url)
    result2 = temp_cache.get(key)
    assert result2["data"] == data2


def test_cache_clear(temp_cache):
    """Testa limpeza do cache."""
    # Armazenar múltiplas entradas
    for i in range(5):
        temp_cache.set(f"key_{i}", {"value": i}, f"https://example.com/{i}")
    
    # Verificar que existem
    assert temp_cache.get("key_0") is not None
    assert temp_cache.get("key_4") is not None
    
    # Limpar
    temp_cache.clear()
    
    # Verificar que não existem mais
    assert temp_cache.get("key_0") is None
    assert temp_cache.get("key_4") is None


def test_cache_persistence(temp_cache, tmp_path):
    """Testa persistência do cache entre instâncias."""
    key = "persistent_key"
    data = {"persistent": True}
    source_url = "https://example.com/persistent"
    
    # Armazenar na primeira instância
    temp_cache.set(key, data, source_url)
    
    # Criar nova instância com mesmo caminho
    cache2 = Cache(db_path=str(temp_cache.db_path), ttl_seconds=3600)
    
    # Recuperar na segunda instância
    result = cache2.get(key)
    
    assert result is not None
    assert result["data"] == data
