"""Como os números aparecem na janela (vírgula decimal, ponto de milhar)."""


def tamanho(n: float) -> str:
    if n < 1024:
        return f"{int(n)} bytes"
    for unidade in ("KB", "MB", "GB", "TB", "PB"):
        n /= 1024
        if n < 1000 or unidade == "PB":
            return (f"{n:.1f} {unidade}" if n < 100 else f"{n:.0f} {unidade}").replace(".", ",")
    return ""


def numero(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def porcento(frac: float) -> str:
    return f"{frac * 100:.1f} %".replace(".", ",")
