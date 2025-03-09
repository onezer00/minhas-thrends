import pytest
from unittest.mock import patch, MagicMock
import os
from app.main import (
    get_github_pages_url,
    is_origin_allowed
)

def test_get_github_pages_url():
    """Testa a função get_github_pages_url."""
    # Teste com variável de ambiente definida
    with patch.dict(os.environ, {"GITHUB_PAGES_URL": "https://example.github.io"}):
        assert get_github_pages_url() == "https://example.github.io"
    
    # Teste com variável de ambiente não definida
    # A implementação atual retorna "https://onezer00.github.io" como padrão
    with patch.dict(os.environ, {}, clear=True):
        # Ajustando o teste para a implementação atual
        assert get_github_pages_url() == "https://onezer00.github.io"

def test_is_origin_allowed():
    """Testa a função is_origin_allowed."""
    # Teste em ambiente de desenvolvimento
    with patch("app.main.IS_DEVELOPMENT", True):
        # Em desenvolvimento, TODAS as origens são permitidas
        assert is_origin_allowed("http://localhost:3000") == True
        assert is_origin_allowed("http://localhost:8080") == True
        assert is_origin_allowed("https://example.github.io") == True
        assert is_origin_allowed("https://other-domain.com") == True
        assert is_origin_allowed("null") == True
        
        # Em desenvolvimento, até mesmo origens vazias ou "No Origin" são permitidas
        assert is_origin_allowed("") == True
        assert is_origin_allowed(None) == True
        assert is_origin_allowed("No Origin") == True

    # Teste em ambiente de produção com lista de origens permitidas vazia
    with patch("app.main.IS_DEVELOPMENT", False), patch("app.main.ALLOWED_ORIGINS", []):
        # Em produção, com lista vazia, nenhuma origem deve ser permitida
        assert is_origin_allowed("http://localhost:3000") == False
        assert is_origin_allowed("http://localhost:8080") == False
        assert is_origin_allowed("https://example.github.io") == False
        assert is_origin_allowed("https://other-domain.com") == False
        
        # Origens vazias ou "No Origin" não são permitidas em produção
        assert is_origin_allowed("") == False
        assert is_origin_allowed(None) == False
        assert is_origin_allowed("No Origin") == False
        
        # Teste com origem "null" (requisições de arquivo local)
        assert is_origin_allowed("null") == False
    
    # Teste em ambiente de produção com lista de origens permitidas específica
    with patch("app.main.IS_DEVELOPMENT", False), patch("app.main.ALLOWED_ORIGINS", ["https://example.github.io"]):
        # Apenas as origens na lista devem ser permitidas
        assert is_origin_allowed("http://localhost:3000") == False
        assert is_origin_allowed("http://localhost:8080") == False
        assert is_origin_allowed("https://example.github.io") == True
        assert is_origin_allowed("https://other-domain.com") == False 