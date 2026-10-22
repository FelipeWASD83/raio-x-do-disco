"""Abre o Raio-X do Disco (é o que o atalho do Menu Iniciar chama, pelo pythonw do .venv).

Também aplica a atualização baixada pelo app e volta para a versão anterior se a nova não abrir.
Erros vão para dados/log.txt, já que o pythonw não tem console. Argumentos são repassados para o app
(`--escanear C:` abre já lendo o disco, que é como ele se reabre como administrador).
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from app import atualizador, config  # noqa: E402

LOG = config.DADOS / "log.txt"


def _aplicar():
    try:
        return atualizador.aplicar_pendente(RAIZ)
    except atualizador.ErroAtualizacao as e:
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(f"Atualização não aplicada: {e}\n")
        return None


def _rodar(argumentos) -> int:
    with open(LOG, "w", encoding="utf-8") as log:
        return subprocess.call([sys.executable, "-m", "app.principal", *argumentos], cwd=RAIZ, stdout=log, stderr=log)


def main():
    config.DADOS.mkdir(parents=True, exist_ok=True)
    acabou_de_atualizar = _aplicar()
    argumentos = sys.argv[1:]
    while True:
        atualizador.ABRIU.unlink(missing_ok=True)
        codigo = _rodar(argumentos)
        if codigo == atualizador.SAIR_PARA_ATUALIZAR:
            acabou_de_atualizar = _aplicar()
            argumentos = []
            continue
        if codigo != 0 and acabou_de_atualizar and not atualizador.ABRIU.exists():
            # a versão nova nem chegou a mostrar a janela: volta para a anterior e abre ela
            if atualizador.reverter(RAIZ):
                acabou_de_atualizar = None
                continue
        break


if __name__ == "__main__":
    main()
