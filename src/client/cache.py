import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from src.config import settings


class Cache:
    """Cache persistente em SQLite com suporte a TTL."""

    def __init__(self, db_path: Optional[str] = None, ttl_seconds: Optional[int] = None):
        self.db_path = Path(db_path or settings.cache_db_path)
        self.ttl_seconds = ttl_seconds or settings.cache_ttl_seconds
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """Garante que o banco de dados e a tabela existam."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    source_url TEXT NOT NULL
                )
            """)
            conn.commit()

    def get(self, key: str) -> Optional[dict[str, Any]]:
        """
        Recupera entrada do cache se existir e não estiver expirada.
        
        Args:
            key: Chave de cache
            
        Returns:
            Dicionário com 'data', 'fetched_at', 'source_url', 'cached' ou None se não encontrado/expirado
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data, fetched_at, source_url FROM cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            data_str, fetched_at_str, source_url = row
            fetched_at = datetime.fromisoformat(fetched_at_str)
            
            # Verificar TTL
            if datetime.now(timezone.utc) - fetched_at > timedelta(seconds=self.ttl_seconds):
                return None
            
            return {
                "data": json.loads(data_str),
                "fetched_at": fetched_at_str,
                "source_url": source_url,
                "cached": True
            }

    def set(self, key: str, data: dict[str, Any], source_url: str) -> None:
        """
        Armazena entrada no cache.
        
        Args:
            key: Chave de cache
            data: Dados a serem armazenados
            source_url: URL de origem dos dados
        """
        fetched_at = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, data, fetched_at, source_url)
                VALUES (?, ?, ?, ?)
                """,
                (key, json.dumps(data), fetched_at, source_url)
            )
            conn.commit()

    def clear(self) -> None:
        """Limpa todas as entradas do cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()


# Instância global de cache
cache = Cache()
