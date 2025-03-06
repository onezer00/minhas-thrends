# Testes do TrendPulse

Este diretório contém os testes automatizados para o TrendPulse. Os testes são organizados em duas categorias principais:

- **Testes Unitários**: Testam componentes individuais isoladamente
- **Testes de Integração**: Testam a interação entre diferentes componentes

## Estrutura de Diretórios

```
tests/
├── unit/              # Testes unitários
│   ├── app/           # Testes para módulos específicos da aplicação
│   ├── test_*.py      # Testes unitários gerais
├── integration/       # Testes de integração
│   ├── test_*.py      # Testes de integração
├── conftest.py        # Fixtures e configurações compartilhadas
└── README.md          # Este arquivo
```

## Executando os Testes

### Usando o script run_tests.py

O projeto inclui um script `run_tests.py` na raiz que facilita a execução dos testes:

```bash
# Executar todos os testes
python run_tests.py

# Executar apenas testes unitários
python run_tests.py --unit

# Executar apenas testes de integração
python run_tests.py --integration

# Gerar relatório de cobertura
python run_tests.py --coverage

# Gerar relatório de cobertura em HTML
python run_tests.py --coverage --html

# Gerar relatório de cobertura em XML (para CI)
python run_tests.py --coverage --xml

# Executar verificações de pré-commit
python run_tests.py --pre-commit

# Gerar um relatório de testes em texto
python run_tests.py --report

# Aumentar verbosidade
python run_tests.py -v
```

### Usando pytest diretamente

Você também pode usar o pytest diretamente:

```bash
# Executar todos os testes
pytest

# Executar testes com marcador específico
pytest -m unit
pytest -m integration

# Executar um arquivo de teste específico
pytest tests/unit/test_models.py

# Executar um teste específico
pytest tests/unit/test_models.py::test_trend_creation

# Gerar relatório de cobertura
pytest --cov=app tests/

# Gerar relatório de cobertura em HTML
pytest --cov=app tests/ --cov-report=html
```

## Integração Contínua (CI)

Os testes são executados automaticamente pelo GitHub Actions a cada push ou pull request. O fluxo de trabalho está configurado em `.github/workflows/test.yml` e inclui:

1. Execução de todos os testes
2. Geração de relatório de cobertura
3. Upload do relatório para o Codecov
4. Notificação para o Render para deploy (apenas na branch principal)

## Pré-commit

O projeto usa pre-commit para verificar o código antes de cada commit. Para configurar:

```bash
# Instalar e configurar o pre-commit
python setup_pre_commit.py

# Executar manualmente em todos os arquivos
pre-commit run --all-files
```

## Boas Práticas para Testes

1. **Nomeação**: Todos os arquivos de teste devem começar com `test_` e as funções de teste também.
2. **Isolamento**: Cada teste deve ser independente e não depender do estado de outros testes.
3. **Fixtures**: Use fixtures do pytest para configurar o ambiente de teste.
4. **Mocks**: Use mocks para isolar o código sendo testado de suas dependências.
5. **Cobertura**: Tente manter a cobertura de código acima de 80%.
6. **Documentação**: Documente o propósito de cada teste e o que está sendo testado.

## Troubleshooting

### Testes Falhando

1. **Erro de conexão com banco de dados**: Os testes usam um banco SQLite em memória. Verifique se as fixtures estão configuradas corretamente.
2. **Erro de conexão com Redis**: Os testes usam um broker em memória. Verifique se as variáveis de ambiente estão configuradas corretamente.
3. **Testes assíncronos**: Certifique-se de que o plugin `pytest-asyncio` está instalado e que os testes assíncronos estão marcados com `@pytest.mark.asyncio`.

### Problemas de Cobertura

1. **Baixa cobertura**: Verifique se todos os caminhos do código estão sendo testados, incluindo tratamento de erros.
2. **Código não testável**: Refatore o código para torná-lo mais testável, separando responsabilidades e usando injeção de dependência.

### Testes Lentos

1. **Paralelização**: Use `pytest-xdist` para executar testes em paralelo: `pytest -n auto`.
2. **Mocks**: Use mocks para evitar chamadas a APIs externas durante os testes.
3. **Fixtures de sessão**: Use `scope="session"` para fixtures que podem ser reutilizadas entre testes. 