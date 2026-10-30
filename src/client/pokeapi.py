import asyncio
import re
from typing import Any

import httpx

from src.client.cache import cache
from src.config import settings


class PokeAPIClient:
    """Cliente HTTP resiliente para PokéAPI com retry e cache."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int = 3
    ):
        self.base_url = base_url or settings.pokeapi_base_url
        self.timeout = timeout or settings.request_timeout_seconds
        self.max_retries = max_retries

    def _normalize_name(self, name_or_id: str | int) -> str:
        """
        Normaliza nome ou ID para consulta.
        
        Converte para minúsculas, remove espaços extras, e trata caracteres especiais.
        Ex: "Nidoran♀" -> "nidoran-f"
        """
        if isinstance(name_or_id, int):
            return str(name_or_id)
        
        # Converter para minúsculas e trim
        normalized = str(name_or_id).strip().lower()
        
        # Substituir caracteres especiais comuns
        normalized = re.sub(r"[♀]", "-f", normalized)
        normalized = re.sub(r"[♂]", "-m", normalized)
        normalized = re.sub(r"[éèêë]", "e", normalized)
        normalized = re.sub(r"[áàâãä]", "a", normalized)
        normalized = re.sub(r"[óòôõö]", "o", normalized)
        normalized = re.sub(r"[íìîï]", "i", normalized)
        normalized = re.sub(r"[úùûü]", "u", normalized)
        normalized = re.sub(r"[ç]", "c", normalized)
        
        # Remover espaços internos
        normalized = re.sub(r"\s+", "-", normalized)
        
        return normalized

    def _validate_url(self, url: str) -> bool:
        """
        Valida se a URL pertence ao domínio permitido do PokéAPI.
        
        Args:
            url: URL a ser validada
            
        Returns:
            True se permitida, False caso contrário
        """
        allowed_domain = self.base_url.rstrip("/")
        return url.startswith(allowed_domain)

    async def _fetch_with_retry(
        self,
        url: str,
        client: httpx.AsyncClient
    ) -> dict[str, Any] | None:
        """
        Executa requisição HTTP com retry e exponential backoff.
        
        Args:
            url: URL para requisição
            client: Cliente httpx
            
        Returns:
            Dados JSON ou None em caso de erro irrecuperável
        """
        for attempt in range(self.max_retries):
            try:
                response = await client.get(url, timeout=self.timeout)
                
                # Sucesso
                if response.status_code == 200:
                    return response.json()
                
                # 404 - Não encontrado (não retry)
                if response.status_code == 404:
                    return None
                
                # 429 - Rate limit (retry com backoff)
                if response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        backoff = 2 ** attempt
                        await asyncio.sleep(backoff)
                        continue
                    return None
                
                # 5xx - Erro de servidor (retry com backoff)
                if 500 <= response.status_code < 600:
                    if attempt < self.max_retries - 1:
                        backoff = 2 ** attempt
                        await asyncio.sleep(backoff)
                        continue
                    return None
                
                # Outros erros 4xx (não retry)
                return None
                
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    await asyncio.sleep(backoff)
                    continue
                return None
            
            except Exception:
                return None
        
        return None

    async def get(
        self,
        endpoint: str,
        name_or_id: str | int | None = None,
        use_cache: bool = True
    ) -> dict[str, Any]:
        """
        Busca dados do PokéAPI com cache e validação de domínio.
        
        Args:
            endpoint: Endpoint da API (ex: "pokemon", "type")
            name_or_id: Nome ou ID do recurso
            use_cache: Se deve usar cache
            
        Returns:
            Dicionário com 'data', 'sources', e opcional 'error'
        """
        # Normalizar input
        if name_or_id is not None:
            normalized_id = self._normalize_name(name_or_id)
            cache_key = f"{endpoint}:{normalized_id}"
            url = f"{self.base_url}/{endpoint}/{normalized_id}"
        else:
            cache_key = endpoint
            url = f"{self.base_url}/{endpoint}"
        
        # Validar domínio
        if not self._validate_url(url):
            return {
                "data": None,
                "sources": [],
                "error": "URL não permitida: domínio bloqueado por segurança"
            }
        
        # Tentar cache primeiro
        if use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                return {
                    "data": cached["data"],
                    "sources": [{
                        "url": cached["source_url"],
                        "fetched_at": cached["fetched_at"],
                        "cached": True
                    }]
                }
        
        # Buscar da API
        async with httpx.AsyncClient() as client:
            data = await self._fetch_with_retry(url, client)
        
        if data is None:
            return {
                "data": None,
                "sources": [],
                "error": "Recurso não encontrado ou erro na requisição"
            }
        
        # Armazenar no cache
        cache.set(cache_key, data, url)
        
        return {
            "data": data,
            "sources": [{
                "url": url,
                "fetched_at": cache.get(cache_key)["fetched_at"] if cache.get(cache_key) else None,
                "cached": False
            }]
        }


# Instância global do cliente
pokeapi_client = PokeAPIClient()
