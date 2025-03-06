#!/usr/bin/env python
"""
Script para configurar o pre-commit no projeto TrendPulse.
"""
import os
import sys
import subprocess
import argparse

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Configura o pre-commit para o TrendPulse.")
    parser.add_argument(
        "--install-only", action="store_true", help="Apenas instala o pre-commit sem configurar"
    )
    parser.add_argument(
        "--force", action="store_true", help="Força a reinstalação mesmo se já estiver instalado"
    )
    return parser.parse_args()

def check_pre_commit_installed():
    """Verifica se o pre-commit está instalado."""
    try:
        subprocess.run(["pre-commit", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def install_pre_commit():
    """Instala o pre-commit."""
    print("Instalando pre-commit...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "pre-commit"])
    if result.returncode != 0:
        print("❌ Falha ao instalar pre-commit.")
        return False
    print("✅ pre-commit instalado com sucesso!")
    return True

def setup_pre_commit():
    """Configura o pre-commit no repositório."""
    print("Configurando pre-commit no repositório...")
    
    # Verifica se o arquivo .pre-commit-config.yaml existe
    if not os.path.exists(".pre-commit-config.yaml"):
        print("❌ Arquivo .pre-commit-config.yaml não encontrado.")
        return False
    
    # Instala os hooks do pre-commit
    result = subprocess.run(["pre-commit", "install"])
    if result.returncode != 0:
        print("❌ Falha ao instalar hooks do pre-commit.")
        return False
    
    # Instala os hooks específicos para o commit-msg
    result = subprocess.run(["pre-commit", "install", "--hook-type", "commit-msg"])
    if result.returncode != 0:
        print("❌ Falha ao instalar hooks de commit-msg.")
        return False
    
    print("✅ pre-commit configurado com sucesso!")
    return True

def main():
    """Main function."""
    args = parse_args()
    
    # Verifica se o pre-commit já está instalado
    if check_pre_commit_installed() and not args.force:
        print("pre-commit já está instalado. Use --force para reinstalar.")
    else:
        if not install_pre_commit():
            return 1
    
    # Configura o pre-commit se não for apenas instalação
    if not args.install_only:
        if not setup_pre_commit():
            return 1
        
        # Executa o pre-commit em todos os arquivos
        print("\nExecutando pre-commit em todos os arquivos...")
        subprocess.run(["pre-commit", "run", "--all-files"])
    
    print("\n🎉 Configuração concluída! O pre-commit será executado automaticamente antes de cada commit.")
    print("   Para executar manualmente: pre-commit run --all-files")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 