"""Caminhos e versão do Raio-X do Disco."""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
ICONE = RAIZ / "icone" / "icone.ico"


def info_versao() -> dict:
    try:
        return json.loads((RAIZ / "versao.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


VERSAO = info_versao().get("versao", "0.0.0")
