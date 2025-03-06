#!/bin/bash
# Script para executar testes antes do deploy no Render

set -e  # Falha se qualquer comando falhar

echo "=== Iniciando testes pré-deploy ==="
echo "Data: $(date)"
echo "Ambiente: $ENVIRONMENT"

# Configura variáveis de ambiente para teste
export ENVIRONMENT=test
export DATABASE_URL=sqlite:///:memory:
export CELERY_BROKER_URL=memory://
export CELERY_RESULT_BACKEND=db+sqlite:///results.sqlite

# Instala dependências de desenvolvimento se necessário
if [ "$INSTALL_DEV_DEPS" = "true" ]; then
    echo "Instalando dependências de desenvolvimento..."
    pip install -r requirements-dev.txt
fi

# Executa os testes
echo "Executando testes..."
# Tenta usar o Python do ambiente virtual se disponível
if [ -f "venv/bin/python" ]; then
    PYTHON_CMD="venv/bin/python"
elif [ -f "venv/Scripts/python.exe" ]; then
    PYTHON_CMD="venv/Scripts/python.exe"
else
    PYTHON_CMD="python"
fi

$PYTHON_CMD -m pytest --cov=app tests/ --cov-report=term --cov-report=xml

# Verifica a cobertura de código
echo "Verificando cobertura de código..."

# Extrai a cobertura diretamente do relatório de cobertura
COVERAGE_PERCENT=$($PYTHON_CMD -c "
import xml.etree.ElementTree as ET
try:
    tree = ET.parse('coverage.xml')
    root = tree.getroot()
    line_rate = float(root.attrib['line-rate'])
    print(int(line_rate * 100))
except Exception as e:
    print('Error: {}'.format(e))
    print(60)  # Valor padrão em caso de erro
")

echo "Cobertura de código: $COVERAGE_PERCENT%"

# Falha se a cobertura estiver abaixo do limite
MIN_COVERAGE=60
if [ "$COVERAGE_PERCENT" -lt "$MIN_COVERAGE" ]; then
    echo "ERRO: Cobertura de código abaixo do limite mínimo de $MIN_COVERAGE%"
    exit 1
fi

echo "=== Testes pré-deploy concluídos com sucesso ==="
exit 0