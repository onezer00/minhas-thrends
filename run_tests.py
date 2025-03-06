#!/usr/bin/env python
"""
Script para executar os testes do TrendPulse.
"""
import os
import sys
import argparse
import subprocess
import datetime

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Executa os testes do TrendPulse.")
    parser.add_argument(
        "--unit", action="store_true", help="Executa apenas os testes unitários"
    )
    parser.add_argument(
        "--integration", action="store_true", help="Executa apenas os testes de integração"
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Gera relatório de cobertura de código"
    )
    parser.add_argument(
        "--html", action="store_true", help="Gera relatório de cobertura em HTML"
    )
    parser.add_argument(
        "--xml", action="store_true", help="Gera relatório de cobertura em XML para CI"
    )
    parser.add_argument(
        "--pre-commit", action="store_true", help="Executa verificações de pré-commit"
    )
    parser.add_argument(
        "--report", action="store_true", help="Gera um relatório de testes em texto"
    )
    parser.add_argument(
        "--verbose", "-v", action="count", default=0, help="Aumenta o nível de verbosidade"
    )
    parser.add_argument(
        "pytest_args", nargs="*", help="Argumentos adicionais para o pytest"
    )
    return parser.parse_args()

def run_pre_commit_checks():
    """Executa verificações de pré-commit."""
    print("Executando verificações de pré-commit...")
    
    # Verifica formatação com black
    print("\n=== Verificando formatação com black ===")
    black_result = subprocess.run(["black", "--check", "app", "tests"])
    
    # Verifica imports com isort
    print("\n=== Verificando imports com isort ===")
    isort_result = subprocess.run(["isort", "--check", "app", "tests"])
    
    # Verifica estilo com flake8
    print("\n=== Verificando estilo com flake8 ===")
    flake8_result = subprocess.run(["flake8", "app", "tests"])
    
    # Verifica tipos com mypy (opcional)
    print("\n=== Verificando tipos com mypy ===")
    mypy_result = subprocess.run(["mypy", "app"])
    
    return all([
        black_result.returncode == 0,
        isort_result.returncode == 0,
        flake8_result.returncode == 0,
        mypy_result.returncode == 0
    ])

def generate_test_report(coverage_data=None):
    """Gera um relatório de testes em texto."""
    now = datetime.datetime.now()
    report_file = f"test_report_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"Relatório de Testes - TrendPulse\n")
        f.write(f"Data: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")
        
        # Adiciona informações de cobertura se disponíveis
        if coverage_data:
            f.write("Cobertura de Código:\n")
            f.write(f"Total: {coverage_data.get('total', 'N/A')}%\n")
            f.write("Por módulo:\n")
            for module, cov in coverage_data.get("modules", {}).items():
                f.write(f"  - {module}: {cov}%\n")
            f.write("\n")
        
        # Executa pytest para obter resumo dos testes
        f.write("Resumo dos Testes:\n")
        result = subprocess.run(
            ["pytest", "--collect-only", "-v"], 
            capture_output=True, 
            text=True
        )
        f.write(result.stdout)
        
    print(f"Relatório de testes gerado: {report_file}")
    return report_file

def main():
    """Main function."""
    args = parse_args()

    # Configura variáveis de ambiente para teste
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["CELERY_BROKER_URL"] = "memory://"
    os.environ["CELERY_RESULT_BACKEND"] = "db+sqlite:///results.sqlite"

    # Executa verificações de pré-commit se solicitado
    if args.pre_commit:
        if not run_pre_commit_checks():
            print("\n❌ Verificações de pré-commit falharam. Corrija os problemas antes de continuar.")
            return 1
        print("\n✅ Todas as verificações de pré-commit passaram!")

    # Constrói o comando pytest
    cmd = ["pytest"]

    # Adiciona verbosidade
    if args.verbose:
        cmd.extend(["-" + "v" * args.verbose])

    # Adiciona marcadores
    if args.unit and not args.integration:
        cmd.extend(["-m", "unit"])
    elif args.integration and not args.unit:
        cmd.extend(["-m", "integration"])

    # Adiciona cobertura
    coverage_formats = []
    if args.coverage:
        cmd.extend(["--cov=app"])
        coverage_formats.append("term")
        
        if args.html:
            coverage_formats.append("html")
        
        if args.xml:
            coverage_formats.append("xml")
            
        if coverage_formats:
            cmd.extend([f"--cov-report={format}" for format in coverage_formats])

    # Adiciona argumentos adicionais
    cmd.extend(args.pytest_args)

    # Executa o comando
    print(f"Executando: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    # Gera relatório de testes se solicitado
    if args.report:
        # Aqui você poderia extrair dados de cobertura do arquivo .coverage
        # Para simplificar, estamos apenas passando alguns dados de exemplo
        coverage_data = {
            "total": "N/A",
            "modules": {}
        }
        generate_test_report(coverage_data)

    return result.returncode

if __name__ == "__main__":
    sys.exit(main()) 