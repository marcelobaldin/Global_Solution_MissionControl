#!/usr/bin/env python3
"""
MissionControl - Instalador Automatico
Cria ambiente virtual, instala dependencias e executa o sistema.

Global Solution 2026 - FIAP
Marcelo Bastianello Baldin - RM568746
"""

import subprocess
import sys
import os
import platform


def main():
    print()
    print("=" * 60)
    print("  MissionControl - Instalador Automatico")
    print("  Global Solution 2026 - FIAP")
    print("=" * 60)
    print()

    if sys.version_info < (3, 9):
        print(f"  ERRO: Python 3.9 ou superior necessario.")
        print(f"  Versao atual: {sys.version}")
        print(f"  Baixe em: https://www.python.org/downloads/")
        sys.exit(1)

    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Sistema: {platform.system()} {platform.machine()}")

    pasta = os.path.dirname(os.path.abspath(__file__))
    venv_path = os.path.join(pasta, 'venv_missioncontrol')

    app_path = os.path.join(pasta, 'src', 'sistema.py')
    if not os.path.exists(app_path):
        print(f"\n  ERRO: src/sistema.py nao encontrado em:")
        print(f"  {pasta}")
        sys.exit(1)

    # 1. Criar venv
    if not os.path.exists(venv_path):
        print("\n[1/3] Criando ambiente virtual...")
        subprocess.run([sys.executable, '-m', 'venv', venv_path], check=True)
        print("  Ambiente virtual criado.")
    else:
        print("\n[1/3] Ambiente virtual ja existe.")

    if platform.system() == 'Windows':
        pip_path = os.path.join(venv_path, 'Scripts', 'pip')
        python_path = os.path.join(venv_path, 'Scripts', 'python')
    else:
        pip_path = os.path.join(venv_path, 'bin', 'pip')
        python_path = os.path.join(venv_path, 'bin', 'python')

    # 2. Instalar dependencias
    print("\n[2/3] Instalando dependencias...")
    deps = ['flask', 'fpdf2']
    subprocess.run([pip_path, 'install', '--quiet'] + deps,
                   check=True, capture_output=True)
    print(f"  {len(deps)} pacotes instalados: {', '.join(deps)}")

    # 3. Executar
    print("\n[3/3] Iniciando MissionControl...")
    print()
    print("=" * 60)
    print("  Acesse no navegador: http://localhost:5050")
    print()
    print("  Credenciais:")
    print("  +----------+-----------+---------+")
    print("  | Perfil   | Usuario   | Senha   |")
    print("  +----------+-----------+---------+")
    print("  | Operador | usuario   | senha   |")
    print("  +----------+-----------+---------+")
    print()
    print("  Para encerrar: Ctrl+C")
    print("=" * 60)
    print()

    try:
        subprocess.run([python_path, app_path])
    except KeyboardInterrupt:
        print("\n  MissionControl encerrado.")


if __name__ == '__main__':
    main()
