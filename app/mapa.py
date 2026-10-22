"""Mapa de blocos no estilo do SpaceSniffer: cada pasta é um retângulo do tamanho do espaço que ocupa, com o nome
no topo e o que tem dentro desenhado lá dentro, até o bloco ficar pequeno demais para ler.

`montar()` só calcula os retângulos (dá para testar sem janela); a classe `Mapa` desenha num Canvas e cuida do
mouse: passar por cima mostra o caminho, um clique seleciona, dois cliques entram na pasta, Backspace volta.
"""
from __future__ import annotations

import functools
import heapq
import math
import time
import tkinter as tk
from collections import deque
from tkinter import font as tkfont
from tkinter import ttk

from app import leitor
from app.formato import porcento, tamanho

MARGEM = 3                # borda da pasta em volta do que tem dentro
AREA_MINIMA = 14 * 14     # bloco menor que isso (em pixels) entra no "itens menores"
MAX_FILHOS = 250          # por pasta
LIMITE_BLOCOS = 6000      # no mapa inteiro: acima disso o Canvas começa a pesar no redesenho

# cor do cabeçalho por nível (a raiz é o nível 0); arquivo usa a cor da pasta dele bem clareada
CORES_NIVEL = ["#3b6ea8", "#2f8f83", "#7d8f2f", "#b0782b", "#a64e63", "#6d5aa6"]
COR_MENORES = "#cfd4db"
COR_SUMIDO = "#e09a3a"
COR_REALCE = "#ffffff"
COR_SELECAO = "#ff7a1a"


class Bloco:
    __slots__ = ("x", "y", "w", "h", "tipo", "obj", "pasta", "nivel", "disco", "qtd", "aberto")

    def __init__(self, x, y, w, h, tipo, obj, pasta, nivel, disco, qtd=0):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.tipo = tipo          # "pasta", "arquivo", "menores" ou "sumido"
        self.obj = obj            # a Pasta, ou a tupla do arquivo
        self.pasta = pasta        # a pasta onde o bloco mora (para arquivo e "menores")
        self.nivel = nivel
        self.disco = disco
        self.qtd = qtd            # quantos itens o "menores" junta
        self.aberto = False       # pasta com cabeçalho e o conteúdo desenhado dentro


def _disco_de(x) -> int:
    return x.disco if isinstance(x, leitor.Pasta) else x[2]


def quadrados(valores: list[float], x: float, y: float, w: float, h: float) -> list[tuple]:
    """Treemap "squarified" (Bruls, Huizing e van Wijk): divide o retângulo em pedaços com área proporcional a
    cada valor e o mais perto de quadrado possível. Valores positivos, de preferência do maior para o menor;
    devolve (x, y, w, h) na mesma ordem."""
    total = float(sum(valores))
    if total <= 0 or w <= 0 or h <= 0:
        return [(x, y, 0.0, 0.0)] * len(valores)
    escala = w * h / total
    areas = [v * escala for v in valores]
    saida: list[tuple] = []
    i, n = 0, len(areas)
    while i < n:
        lado = min(w, h)
        if lado <= 1e-9:
            saida.extend([(x, y, 0.0, 0.0)] * (n - i))
            break
        j, soma, maior, menor, pior = i, 0.0, 0.0, math.inf, math.inf
        while j < n:
            a = areas[j]
            s2, ma, mi = soma + a, max(maior, a), min(menor, a)
            p = max(lado * lado * ma / (s2 * s2), (s2 * s2) / (lado * lado * mi))
            if j > i and p > pior:
                break
            soma, maior, menor, pior = s2, ma, mi, p
            j += 1
        if w >= h:
            largura = soma / h
            yy = y
            for a in areas[i:j]:
                alt = a / largura
                saida.append((x, yy, largura, alt))
                yy += alt
            x += largura
            w -= largura
        else:
            altura = soma / w
            xx = x
            for a in areas[i:j]:
                larg = a / altura
                saida.append((xx, y, larg, altura))
                xx += larg
            y += altura
            h -= altura
        i = j
    return saida


def montar(raiz: leitor.Pasta, w: float, h: float, alt_cabecalho: float, extra: int = 0,
           limite: int = LIMITE_BLOCOS) -> list[Bloco]:
    """Os blocos do mapa com `raiz` ocupando w×h. `extra` é o espaço usado fora dos arquivos (só na raiz do disco).
    Vai nível por nível, para o limite de blocos cortar os detalhes mais fundos, não pastas inteiras do topo."""
    blocos: list[Bloco] = []
    fila = deque([(raiz, 0.0, 0.0, float(w), float(h), 0, extra)])
    while fila:
        p, x, y, w, h, nivel, extra = fila.popleft()
        total = p.disco + extra
        b = Bloco(x, y, w, h, "pasta", p, p.pai, nivel, total)
        blocos.append(b)
        if w < 30 or h < alt_cabecalho + 10 or total <= 0 or len(blocos) + len(fila) >= limite:
            continue
        ix, iy, iw, ih = x + MARGEM, y + alt_cabecalho, w - 2 * MARGEM, h - alt_cabecalho - MARGEM
        if iw < 8 or ih < 8:
            continue
        b.aberto = True
        area = iw * ih
        sumido = [(None, extra, extra, -2)] if extra > 0 else []
        itens, soma, reais = [], 0, 0
        orcamento = limite - len(blocos) - len(fila)
        for item in heapq.merge(p.pastas, p.arquivos, sumido, key=_disco_de, reverse=True):
            d = _disco_de(item)
            if d <= 0 or len(itens) >= min(MAX_FILHOS, orcamento) or d / total * area < AREA_MINIMA:
                break
            itens.append(item)
            soma += d
            if not (isinstance(item, tuple) and item[0] is None):
                reais += 1
        resto = total - soma
        resto_qtd = len(p.pastas) + len(p.arquivos) - reais
        valores = [_disco_de(i) for i in itens] + ([resto] if resto > 0 else [])
        if not valores:
            continue
        rets = quadrados(valores, ix, iy, iw, ih)
        for item, (rx, ry, rw, rh) in zip(itens, rets):
            if isinstance(item, leitor.Pasta):
                fila.append((item, rx, ry, rw, rh, nivel + 1, 0))
            elif item[0] is None:
                blocos.append(Bloco(rx, ry, rw, rh, "sumido", None, p, nivel + 1, item[2]))
            else:
                blocos.append(Bloco(rx, ry, rw, rh, "arquivo", item, p, nivel + 1, item[2]))
        if resto > 0:
            rx, ry, rw, rh = rets[-1]
            if rw * rh >= 16:
                blocos.append(Bloco(rx, ry, rw, rh, "menores", None, p, nivel + 1, resto, resto_qtd))
    return blocos


@functools.lru_cache(maxsize=256)
def _misturar(cor: str, alvo: str, t: float) -> str:
    a = [int(cor[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(alvo[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


class Mapa(ttk.Frame):
    """O mapa com a trilha de pastas em cima e a linha do que está embaixo do mouse."""

    def __init__(self, pai, ao_selecionar, **kw):
        super().__init__(pai, **kw)
        self.ao_selecionar = ao_selecionar  # (pasta, arquivo ou None)
        base = tkfont.nametofont("TkDefaultFont")
        self.fonte = tkfont.Font(family=base.cget("family"), size=9)
        self.fonte_cab = tkfont.Font(family=base.cget("family"), size=9, weight="bold")
        self.alt_cab = self.fonte_cab.metrics("linespace") + 5
        amostra = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJ0123456789"
        self.larg_letra = self.fonte_cab.measure(amostra) / len(amostra) * 1.06
        self.alt_linha = self.fonte.metrics("linespace")

        # altura fixa: se a trilha crescesse ao ganhar botão, o mapa encolheria e seria desenhado duas vezes
        teste = ttk.Button(self, text="Xg", style="Toolbutton")
        self.trilha = ttk.Frame(self, height=teste.winfo_reqheight() + 2)
        teste.destroy()
        self.trilha.pack_propagate(False)
        self.trilha.pack(fill="x", pady=(6, 4))
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, background="#eef1f5", cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        self.lbl_info = ttk.Label(self, text="", style="Fraco.TLabel")
        self.lbl_info.pack(fill="x", pady=(4, 0))

        self.raiz: leitor.Pasta | None = None
        self.extra_raiz = 0
        self.atual: leitor.Pasta | None = None
        self.blocos: list[Bloco] = []
        self._por_item: dict[int, Bloco] = {}
        self._sob_mouse: Bloco | None = None
        self.selecionado: tuple | None = None  # (pasta, arquivo ou None)
        self._agendado = None
        self.ultimo_desenho_ms = 0.0

        self.canvas.bind("<Configure>", lambda e: self._agendar())
        self.canvas.bind("<Motion>", self._mexeu)
        self.canvas.bind("<Leave>", lambda e: self._realcar(None))
        self.canvas.bind("<Button-1>", self._clicou)
        self.canvas.bind("<Double-Button-1>", self._dois_cliques)
        self.canvas.bind("<BackSpace>", lambda e: self.voltar())
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self._mostrar_vazio()

    # ---------- o que mostrar ----------

    def mostrar(self, raiz: leitor.Pasta, extra: int) -> None:
        self.raiz, self.extra_raiz = raiz, extra
        self.selecionado = None
        self.ir_para(raiz)

    def limpar(self) -> None:
        self.raiz = self.atual = None
        self.blocos = []
        self.selecionado = None
        self._montar_trilha()
        self._mostrar_vazio()

    def ir_para(self, pasta: leitor.Pasta) -> None:
        self.atual = pasta
        self._montar_trilha()
        self.desenhar()

    def voltar(self) -> None:
        if self.atual is not None and self.atual is not self.raiz and self.atual.pai is not None:
            self.ir_para(self.atual.pai)

    def _montar_trilha(self) -> None:
        for w in self.trilha.winfo_children():
            w.destroy()
        if self.atual is None:
            return
        caminho = []
        p = self.atual
        while p is not None:
            caminho.append(p)
            if p is self.raiz:
                break
            p = p.pai
        caminho.reverse()
        for i, p in enumerate(caminho):
            nome = p.nome if p.pai is not None else p.caminho
            if i == len(caminho) - 1:
                ttk.Label(self.trilha, text=nome, style="Titulo.TLabel").pack(side="left")
            else:
                ttk.Button(self.trilha, text=nome, style="Toolbutton", cursor="hand2",
                           command=lambda p=p: self.ir_para(p)).pack(side="left")
                ttk.Label(self.trilha, text="›", style="Fraco.TLabel").pack(side="left", padx=2)
        ttk.Label(self.trilha, text="dois cliques entram na pasta   ·   Backspace volta",
                  style="Fraco.TLabel").pack(side="right")

    # ---------- desenho ----------

    def _agendar(self) -> None:
        if self._agendado:
            self.after_cancel(self._agendado)
        self._agendado = self.after(80, self.desenhar)

    def _mostrar_vazio(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(20, 20, anchor="nw", fill="#6b7280", font=self.fonte_cab,
                                text="Escaneie um disco para ver o mapa.")

    def _texto_cabe(self, texto: str, largura: float) -> str | None:
        cabe = int((largura - 8) / self.larg_letra)
        if cabe < 3:
            return None
        return texto if len(texto) <= cabe else texto[:cabe - 1] + "…"

    def desenhar(self) -> None:
        self._agendado = None
        if self.atual is None:
            return
        inicio = time.perf_counter()
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20 or h < 20:
            return
        extra = self.extra_raiz if self.atual is self.raiz else 0
        nivel0 = 0
        p = self.atual
        while p is not self.raiz and p.pai is not None:
            nivel0 += 1
            p = p.pai
        self.blocos = montar(self.atual, w, h, self.alt_cab, extra)
        self._por_item = {}
        cor_pasta: dict[int, str] = {}
        for b in self.blocos:
            x1, y1, x2, y2 = b.x, b.y, b.x + b.w, b.y + b.h
            if b.tipo == "pasta":
                cor = CORES_NIVEL[(b.nivel + nivel0) % len(CORES_NIVEL)]
                cor_pasta[id(b.obj)] = cor
                item = c.create_rectangle(x1, y1, x2, y2, fill=cor, outline=_misturar(cor, "#000000", 0.35))
                if b.aberto:
                    # o miolo levemente mais claro deixa ver onde a pasta termina mesmo com pouca coisa dentro
                    c.create_rectangle(x1 + MARGEM, y1 + self.alt_cab, x2 - MARGEM, y2 - MARGEM,
                                       fill=_misturar(cor, "#ffffff", 0.55), outline="")
                nome = b.obj.nome if b.obj.pai is not None else b.obj.caminho
                txt = self._texto_cabe(f"{nome}   {tamanho(b.disco)}", b.w)
                if txt and b.h >= self.alt_linha + 2:
                    meio = y1 + self.alt_cab / 2 if b.aberto else y1 + b.h / 2
                    self._por_item[c.create_text(x1 + 4, meio, anchor="w", text=txt, fill="#ffffff",
                                                 font=self.fonte_cab)] = b
            else:
                if b.tipo == "arquivo":
                    base = cor_pasta.get(id(b.pasta), CORES_NIVEL[0])
                    cor, borda, nome = _misturar(base, "#ffffff", 0.78), _misturar(base, "#ffffff", 0.4), b.obj[0]
                elif b.tipo == "menores":
                    cor, borda, nome = COR_MENORES, "#b4bac3", f"{b.qtd} itens menores"
                else:
                    cor, borda, nome = COR_SUMIDO, "#b7731c", "Fora dos arquivos (NTFS, sem acesso)"
                item = c.create_rectangle(x1, y1, x2, y2, fill=cor, outline=borda)
                if b.h >= self.alt_linha + 4:
                    txt = self._texto_cabe(nome, b.w)
                    if txt:
                        dois = b.h >= 2 * self.alt_linha + 8
                        if dois:
                            txt += "\n" + tamanho(b.disco)
                        self._por_item[c.create_text(x1 + 4, y1 + 3, anchor="nw", text=txt, fill="#1d2733",
                                                     font=self.fonte)] = b
            self._por_item[item] = b
        self._realce = c.create_rectangle(0, 0, 0, 0, outline=COR_REALCE, width=2, state="hidden")
        self._selecao = c.create_rectangle(0, 0, 0, 0, outline=COR_SELECAO, width=3, state="hidden")
        self._sob_mouse = None
        self._marcar_selecao()
        self.ultimo_desenho_ms = (time.perf_counter() - inicio) * 1000

    # ---------- mouse ----------

    def bloco_em(self, x: float, y: float) -> Bloco | None:
        for item in reversed(self.canvas.find_overlapping(x, y, x, y)):
            b = self._por_item.get(item)
            if b is not None:
                return b
        return None

    def _mexeu(self, e) -> None:
        self._realcar(self.bloco_em(e.x, e.y))

    def _realcar(self, b: Bloco | None) -> None:
        if b is self._sob_mouse or not self.blocos:
            return
        self._sob_mouse = b
        if b is None:
            self.canvas.itemconfigure(self._realce, state="hidden")
            self.lbl_info.configure(text="")
            return
        self.canvas.coords(self._realce, b.x + 1, b.y + 1, b.x + b.w - 1, b.y + b.h - 1)
        self.canvas.itemconfigure(self._realce, state="normal")
        self.canvas.tag_raise(self._realce)
        self.canvas.tag_raise(self._selecao)
        self.lbl_info.configure(text=self.descrever(b))

    def descrever(self, b: Bloco) -> str:
        if b.tipo == "pasta":
            onde = b.obj.caminho
            extra = f"{b.obj.n_arquivos:,} arquivos".replace(",", ".")
        elif b.tipo == "arquivo":
            onde = leitor._juntar(b.pasta.caminho, b.obj[0])
            extra = "arquivo"
        elif b.tipo == "menores":
            onde = b.pasta.caminho
            extra = f"{b.qtd} itens pequenos demais para desenhar"
        else:
            onde = self.raiz.caminho
            extra = "usado no disco fora de qualquer arquivo (metadados do NTFS, pontos de restauração, pastas sem acesso)"
        total = (self.raiz.disco + self.extra_raiz) or 1
        return f"{onde}   ·   {tamanho(b.disco)}   ·   {porcento(b.disco / total)} de {self.raiz.caminho}   ·   {extra}"

    def _clicou(self, e) -> None:
        self.canvas.focus_set()
        b = self.bloco_em(e.x, e.y)
        if b is None or b.tipo == "sumido":
            return
        if b.tipo == "pasta":
            self.selecionado = (b.obj, None)
        elif b.tipo == "arquivo":
            self.selecionado = (b.pasta, b.obj)
        else:
            self.selecionado = (b.pasta, None)
        self._marcar_selecao()
        self.ao_selecionar(*self.selecionado)

    def _dois_cliques(self, e) -> None:
        b = self.bloco_em(e.x, e.y)
        if b is None or b.tipo == "sumido":
            return
        alvo = b.obj if b.tipo == "pasta" else b.pasta
        if alvo is not self.atual:
            self.ir_para(alvo)

    def _marcar_selecao(self) -> None:
        if not self.selecionado:
            self.canvas.itemconfigure(self._selecao, state="hidden")
            return
        pasta, arquivo = self.selecionado
        alvo = next((b for b in self.blocos if (arquivo is not None and b.obj is arquivo)
                     or (arquivo is None and b.tipo == "pasta" and b.obj is pasta)), None)
        if alvo is None:
            self.canvas.itemconfigure(self._selecao, state="hidden")
            return
        self.canvas.coords(self._selecao, alvo.x + 1.5, alvo.y + 1.5, alvo.x + alvo.w - 1.5, alvo.y + alvo.h - 1.5)
        self.canvas.itemconfigure(self._selecao, state="normal")
        self.canvas.tag_raise(self._selecao)
