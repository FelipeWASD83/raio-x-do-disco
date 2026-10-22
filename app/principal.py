"""Janela do Raio-X do Disco: escolhe o disco, lê tudo e mostra o que está ocupando espaço."""
from __future__ import annotations

import argparse
import ctypes
import heapq
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from app import atualizador, config, leitor, mapa
from app.formato import numero, porcento, tamanho

LIMITE = 1000  # itens por pasta na árvore; o resto vira uma linha só com a soma
LIMITE_PAINEL = 1000  # arquivos na lista da pasta clicada no mapa
LARGURA_EM_PE = 1300  # janela mais estreita que isso (o monitor em pé) põe a lista embaixo do mapa
AZUL = "#2f6fd6"
CINZA_LIVRE = "#dfe3e8"


def _disco_de(x) -> int:
    return x.disco if isinstance(x, leitor.Pasta) else x[2]


class Imagens:
    """Ícone e barra de porcentagem de cada linha da árvore, numa imagem só: o Treeview só aceita imagem na primeira
    coluna e não colore coluna. Uma imagem por tipo e por ponto percentual, desenhada na primeira vez que aparece."""

    LARG_BARRA = 64
    CORES = {"pasta": AZUL, "arquivo": AZUL, "pasta_aviso": "#b4bac3", "arquivo_aviso": "#b4bac3",
             "sumido": "#d98a1c", "resto": "#b4bac3"}

    def __init__(self, raiz_tk: tk.Tk):
        self.tk = raiz_tk
        self.e = max(1, round(float(raiz_tk.tk.call("tk", "scaling")) / 1.3333))
        self._feitas: dict[tuple, tk.PhotoImage] = {}

    def __call__(self, tipo: str, frac: float) -> tk.PhotoImage:
        chave = (tipo, round(max(0.0, min(1.0, frac)) * 100))
        img = self._feitas.get(chave)
        if img is None:
            img = self._feitas[chave] = self._desenhar(*chave)
        return img

    def _desenhar(self, tipo: str, pct: int) -> tk.PhotoImage:
        e = self.e
        img = tk.PhotoImage(master=self.tk, width=(16 + 8 + self.LARG_BARRA + 8) * e, height=16 * e)

        def ret(cor, x1, y1, x2, y2):
            img.put(cor, to=(x1 * e, y1 * e, x2 * e, y2 * e))

        if tipo.startswith("pasta"):
            ret("#b8841f", 1, 2, 7, 5)
            ret("#e9b443", 2, 3, 6, 5)
            ret("#b8841f", 1, 4, 15, 14)
            ret("#f4c95d", 2, 5, 14, 13)
            ret("#f8d97f", 2, 5, 14, 7)
        elif tipo.startswith("arquivo"):
            ret("#9aa1ab", 3, 1, 11, 15)
            ret("#9aa1ab", 3, 4, 14, 15)
            ret("#ffffff", 4, 2, 10, 14)
            ret("#ffffff", 4, 5, 13, 14)
            ret("#c9ced6", 10, 2, 11, 5)
            ret("#c9ced6", 10, 4, 13, 5)
            ret("#d5d9df", 6, 8, 11, 9)
            ret("#d5d9df", 6, 10, 11, 11)
        elif tipo == "sumido":
            ret("#d98a1c", 3, 2, 13, 14)
            ret("#ffffff", 7, 4, 9, 10)
            ret("#ffffff", 7, 11, 9, 13)
        x0 = 16 + 8
        ret("#e4e8ee", x0, 5, x0 + self.LARG_BARRA, 11)
        cheio = round(self.LARG_BARRA * pct / 100)
        if cheio:
            ret(self.CORES[tipo], x0, 5, x0 + cheio, 11)
        return img


class App:
    def __init__(self, raiz_tk: tk.Tk, escanear: str | None = None):
        self.tk = raiz_tk
        self.codigo_saida = 0
        self.leitura: leitor.Leitura | None = None
        self.pastas_da_arvore: dict[str, leitor.Pasta] = {}
        self._contador = 0
        self._discos: list[dict] = []
        self._raiz_escolhida = ""
        self._info_att: dict | None = None
        self._att_pronta = None
        self._pasta_painel = None
        self.admin = leitor.eh_admin()
        if self.admin:
            leitor.ligar_privilegio_de_backup()

        raiz_tk.title(f"Raio-X do Disco {config.VERSAO}" + ("  (administrador)" if self.admin else ""))
        try:
            raiz_tk.iconbitmap(default=str(config.ICONE))
        except tk.TclError:
            pass
        self._montar()
        self._carregar_discos()
        if escanear:
            alvo = escanear.rstrip("\\").upper()
            for i, d in enumerate(self._discos):
                if d["raiz"].rstrip("\\").upper() == alvo:
                    self.combo.current(i)
                    self._raiz_escolhida = d["raiz"]
                    self.tk.after(300, self.escanear)
        self.tk.after(800, self._marcar_que_abriu)
        self.procurar_atualizacao()

    # ---------- montagem ----------

    def _montar(self) -> None:
        estilo = ttk.Style()
        if "vista" in estilo.theme_names():
            estilo.theme_use("vista")
        base = tkfont.nametofont("TkDefaultFont")
        base.configure(size=10)
        for nome in ("TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(nome).configure(family=base.cget("family"), size=10)
        linha = base.metrics("linespace")
        estilo.configure("Treeview", rowheight=linha + 9)
        estilo.configure("Treeview.Heading", font=(base.cget("family"), 10, "bold"))
        estilo.configure("Titulo.TLabel", font=(base.cget("family"), 11, "bold"))
        estilo.configure("Fraco.TLabel", foreground="#6b7280")
        self.tk.geometry("1500x900")
        self.img = Imagens(self.tk)
        self.tk.minsize(1000, 600)

        topo = ttk.Frame(self.tk, padding=(14, 12, 14, 4))
        topo.pack(fill="x")
        ttk.Label(topo, text="Disco", style="Titulo.TLabel").pack(side="left", padx=(0, 8))
        self.combo = ttk.Combobox(topo, state="readonly", width=70, postcommand=self._carregar_discos)
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", self._escolheu_disco)
        self.bt_escanear = ttk.Button(topo, text="Escanear", command=self.escanear)
        self.bt_escanear.pack(side="left", padx=(10, 4))
        self.bt_parar = ttk.Button(topo, text="Parar", command=self.parar, state="disabled")
        self.bt_parar.pack(side="left")
        uso = ttk.Frame(self.tk, padding=(14, 4, 14, 0))
        uso.pack(fill="x")
        linha_uso = ttk.Frame(uso)
        linha_uso.pack(fill="x")
        self.lbl_uso = ttk.Label(linha_uso, text="")
        self.lbl_uso.pack(side="left")
        # aqui embaixo e não ao lado do Escanear: no monitor em pé (1080 de largura) não cabe na linha de cima
        if self.admin:
            ttk.Label(linha_uso, text="Administrador: lê até as pastas protegidas", style="Fraco.TLabel").pack(side="right")
        else:
            ttk.Button(linha_uso, text="Reabrir como administrador", command=self.reabrir_como_admin).pack(side="right")
        self.cv_uso = tk.Canvas(uso, height=12, highlightthickness=0, bd=0, background=CINZA_LIVRE)
        self.cv_uso.pack(fill="x", pady=(4, 0))
        self.cv_uso.bind("<Configure>", lambda e: self._desenhar_uso())

        prog = ttk.Frame(self.tk, padding=(14, 10, 14, 6))
        prog.pack(fill="x")
        self.barra_prog = ttk.Progressbar(prog, mode="determinate", maximum=1000)
        self.barra_prog.pack(fill="x")
        self.lbl_status = ttk.Label(prog, text="Escolha um disco e clique em Escanear.")
        self.lbl_status.pack(anchor="w", pady=(6, 0))
        self.lbl_caminho = ttk.Label(prog, text="", style="Fraco.TLabel")
        self.lbl_caminho.pack(anchor="w")
        prog.bind("<Configure>", lambda e: self.lbl_status.configure(wraplength=max(300, e.width - 30)))

        abas = ttk.Notebook(self.tk)
        abas.pack(fill="both", expand=True, padx=14, pady=(4, 6))
        self.abas = abas

        f0 = ttk.Frame(abas)
        abas.add(f0, text="  Mapa  ")
        self.divisao = tk.PanedWindow(f0, orient="horizontal", sashwidth=8, bd=0, sashrelief="flat",
                                      background="#e3e7ec")
        self.divisao.pack(fill="both", expand=True)
        self._em_pe: bool | None = None
        self.mapa = mapa.Mapa(self.divisao, self._selecionou_no_mapa)
        painel = ttk.Frame(self.divisao, padding=(10, 6, 0, 0))
        self.lbl_painel = ttk.Label(painel, text="Clique numa pasta do mapa para ver os arquivos dela.",
                                    style="Titulo.TLabel")
        self.lbl_painel.pack(anchor="w")
        self.lbl_painel2 = ttk.Label(painel, text="", style="Fraco.TLabel")
        self.lbl_painel2.pack(anchor="w", pady=(2, 6))
        caixa = ttk.Frame(painel)
        caixa.pack(fill="both", expand=True)
        self.lista_pasta = ttk.Treeview(caixa, columns=("disco", "tam", "nome", "onde"), show="headings",
                                        selectmode="browse")
        for col, titulo, larg, ancora, estica in (("disco", "Em disco", 95, "e", False), ("tam", "Tamanho", 95, "e", False),
                                                  ("nome", "Arquivo", 300, "w", True), ("onde", "Subpasta", 220, "w", True)):
            self.lista_pasta.heading(col, text=titulo, anchor=ancora)
            self.lista_pasta.column(col, width=larg, anchor=ancora, stretch=estica, minwidth=50)
        self.lista_pasta.tag_configure("aviso", foreground="#8a8f98")
        self._rolagem(caixa, self.lista_pasta)
        self._linhas_painel: list[tuple] = []
        self._cache_painel: dict[int, list] = {}
        self.divisao.add(self.mapa, minsize=300, stretch="always")
        self.divisao.add(painel, minsize=260, stretch="never")
        self._divisoria_arrastada = False
        self.divisao.bind("<B1-Motion>", lambda e: setattr(self, "_divisoria_arrastada", True), add="+")
        f0.bind("<Configure>", self._ajustar_divisao)

        f1 = ttk.Frame(abas)
        abas.add(f1, text="  Pastas  ")
        self.tree = ttk.Treeview(f1, columns=("disco", "pct", "tam", "arqs"), selectmode="browse")
        for col, titulo, larg, ancora, estica in (("#0", "Nome", 760, "w", True), ("disco", "Em disco", 110, "e", False),
                                                  ("pct", "% da pasta", 100, "e", False), ("tam", "Tamanho", 110, "e", False),
                                                  ("arqs", "Arquivos", 110, "e", False)):
            self.tree.heading(col, text=titulo, anchor=ancora)
            self.tree.column(col, width=larg, anchor=ancora, stretch=estica, minwidth=50)
        self.tree.tag_configure("aviso", foreground="#8a8f98")
        self.tree.tag_configure("sumido", foreground="#a15c00")
        self._rolagem(f1, self.tree)
        self.tree.bind("<<TreeviewOpen>>", self._abriu_pasta)

        f2 = ttk.Frame(abas)
        abas.add(f2, text="  Maiores arquivos  ")
        self.lista = ttk.Treeview(f2, columns=("disco", "tam", "nome", "pasta"), show="headings", selectmode="browse")
        for col, titulo, larg, ancora, estica in (("disco", "Em disco", 110, "e", False), ("tam", "Tamanho", 110, "e", False),
                                                  ("nome", "Arquivo", 420, "w", False), ("pasta", "Pasta", 700, "w", True)):
            self.lista.heading(col, text=titulo, anchor=ancora)
            self.lista.column(col, width=larg, anchor=ancora, stretch=estica, minwidth=50)
        self._rolagem(f2, self.lista)

        rodape = ttk.Frame(self.tk, padding=(14, 0, 14, 10))
        rodape.pack(fill="x")
        ttk.Label(rodape, text=f"Versão {config.VERSAO}", style="Fraco.TLabel").pack(side="left")
        self.lbl_att = ttk.Label(rodape, text="", style="Fraco.TLabel")
        self.lbl_att.pack(side="left", padx=10)
        self.bt_atualizar = ttk.Button(rodape, text="Atualizar agora", command=self.instalar_atualizacao)
        self.bt_procurar = ttk.Button(rodape, text="Procurar atualização",
                                      command=lambda: self.procurar_atualizacao(forcar=True))
        self.bt_procurar.pack(side="right")

    @staticmethod
    def _rolagem(pai, arvore) -> None:
        vy = ttk.Scrollbar(pai, orient="vertical", command=arvore.yview)
        vx = ttk.Scrollbar(pai, orient="horizontal", command=arvore.xview)
        arvore.configure(yscrollcommand=vy.set, xscrollcommand=vx.set)
        arvore.grid(row=0, column=0, sticky="nsew")
        vy.grid(row=0, column=1, sticky="ns")
        vx.grid(row=1, column=0, sticky="ew")
        pai.rowconfigure(0, weight=1)
        pai.columnconfigure(0, weight=1)

    # ---------- discos ----------

    def _carregar_discos(self) -> None:
        self._discos = leitor.discos()
        textos = []
        for d in self._discos:
            nome = d["nome"] or d["tipo"]
            textos.append(f"{d['raiz']}   {nome}   ·   {tamanho(d['usado'])} usados de {tamanho(d['total'])}   ·   "
                          f"{tamanho(d['livre'])} livres   ({d['tipo']}, {d['fs']})")
        self.combo["values"] = textos
        raizes = [d["raiz"] for d in self._discos]
        if self._raiz_escolhida in raizes:
            self.combo.current(raizes.index(self._raiz_escolhida))
        elif self._discos:
            sistema = next((i for i, r in enumerate(raizes) if r.upper().startswith("C:")), 0)
            self.combo.current(sistema)
            self._raiz_escolhida = raizes[sistema]
        self._mostrar_uso()

    def _escolheu_disco(self, _evento=None) -> None:
        i = self.combo.current()
        if 0 <= i < len(self._discos):
            self._raiz_escolhida = self._discos[i]["raiz"]
        self._mostrar_uso()

    def _disco_escolhido(self) -> dict | None:
        return next((d for d in self._discos if d["raiz"] == self._raiz_escolhida), None)

    def _mostrar_uso(self) -> None:
        d = self._disco_escolhido()
        if not d:
            self.lbl_uso.configure(text="Nenhum disco encontrado.")
            return
        frac = d["usado"] / d["total"] if d["total"] else 0
        self.lbl_uso.configure(text=f"{d['raiz']}  {d['nome'] or d['tipo']}:  {tamanho(d['total'])} no total,  "
                                    f"{tamanho(d['usado'])} usados ({porcento(frac)}),  {tamanho(d['livre'])} livres")
        self._desenhar_uso()

    def _desenhar_uso(self) -> None:
        d = self._disco_escolhido()
        self.cv_uso.delete("all")
        if not d or not d["total"]:
            return
        larg = self.cv_uso.winfo_width()
        cor = "#d64545" if d["livre"] / d["total"] < 0.1 else AZUL
        self.cv_uso.create_rectangle(0, 0, larg * d["usado"] / d["total"], 12, fill=cor, width=0)

    # ---------- leitura ----------

    def escanear(self) -> None:
        d = self._disco_escolhido()
        if not d or (self.leitura and not self.leitura.terminou.is_set()):
            return
        self._limpar()
        self.leitura = leitor.Leitura(d["raiz"], threads=8)
        self.leitura.iniciar()
        self.bt_escanear.configure(state="disabled")
        self.bt_parar.configure(state="normal")
        self.combo.configure(state="disabled")
        self.lbl_status.configure(text=f"Lendo {d['raiz']}...")
        self.tk.after(150, self._acompanhar)

    def parar(self) -> None:
        if self.leitura:
            self.leitura.parar.set()
            self.lbl_status.configure(text="Parando...")

    def _limpar(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.lista.delete(*self.lista.get_children())
        self.pastas_da_arvore.clear()
        self.mapa.limpar()
        self._limpar_painel()
        self._cache_painel.clear()
        self.leitura = None
        self.barra_prog["value"] = 0

    def _acompanhar(self) -> None:
        l = self.leitura
        if l is None:
            return
        p = l.progresso()
        if l.terminou.is_set():
            self._terminou()
            return
        if p["usado"]:
            self.barra_prog["value"] = min(990, p["disco"] / p["usado"] * 1000)
        if not l.parar.is_set():
            self.lbl_status.configure(text=f"Lendo...   {numero(p['arquivos'])} arquivos em {numero(p['pastas'])} pastas   ·   "
                                           f"{tamanho(p['disco'])} de {tamanho(p['usado'])}   ·   {p['segundos']:.0f} s")
            atual = p["atual"]
            self.lbl_caminho.configure(text=atual if len(atual) < 180 else "..." + atual[-177:])
        self.tk.after(150, self._acompanhar)

    def _terminou(self) -> None:
        l = self.leitura
        self.bt_escanear.configure(state="normal")
        self.bt_parar.configure(state="disabled")
        self.combo.configure(state="readonly")
        self.lbl_caminho.configure(text="")
        if l.erro:
            self.lbl_status.configure(text=f"A leitura deu erro: {l.erro}")
            self.barra_prog["value"] = 0
            return
        if l.cancelada:
            self.lbl_status.configure(text="Leitura interrompida.")
            self._limpar()
            return
        self.barra_prog["value"] = 1000
        r = l.raiz
        texto = (f"Pronto em {l.duracao:.0f} s:  {numero(r.n_arquivos)} arquivos em {numero(r.n_pastas)} pastas,  "
                 f"{tamanho(r.disco)} em disco.")
        if l.pastas_sem_acesso:
            n = l.pastas_sem_acesso
            texto += f"  {numero(n)} {'pasta' if n == 1 else 'pastas'} sem acesso"
            texto += "." if self.admin else " (reabra como administrador para ler essas também)."
        self.lbl_status.configure(text=texto)
        self._carregar_discos()

        nao_achado = l.nao_encontrado()
        self._total_raiz = r.disco + nao_achado
        self.pastas_da_arvore["r"] = r
        self.tree.insert("", "end", iid="r", text=r.caminho, open=True, image=self.img("pasta", 1),
                         values=(tamanho(self._total_raiz), porcento(1), tamanho(r.tam), numero(r.n_arquivos)))
        self._preencher("r")

        for disco, tam, pasta, nome in l.maiores_arquivos(500):
            self.lista.insert("", "end", values=(tamanho(disco), tamanho(tam), nome, pasta))

        self.abas.select(0)
        self.mapa.mostrar(r, nao_achado)
        self._selecionou_no_mapa(r, None)

    # ---------- mapa e lista da pasta clicada ----------

    def _ajustar_divisao(self, e) -> None:
        """Lista ao lado do mapa na tela larga, embaixo na estreita. A divisória acompanha o tamanho da janela até
        ele arrastá-la; daí fica onde ele pôs, até a janela trocar de larga para estreita ou o contrário."""
        em_pe = e.width < LARGURA_EM_PE
        if em_pe != self._em_pe:
            self._em_pe = em_pe
            self._divisoria_arrastada = False
            self.divisao.configure(orient="vertical" if em_pe else "horizontal")
        if self._divisoria_arrastada:
            return
        self.divisao.update_idletasks()
        if em_pe:
            self.divisao.sash_place(0, 0, int(e.height * 0.62))
        else:
            self.divisao.sash_place(0, e.width - min(760, int(e.width * 0.36)), 0)

    def _limpar_painel(self) -> None:
        self.lista_pasta.delete(*self.lista_pasta.get_children())
        self._linhas_painel = []
        self.lbl_painel.configure(text="Clique numa pasta do mapa para ver os arquivos dela.")
        self.lbl_painel2.configure(text="")

    def _arquivos_dentro(self, pasta: leitor.Pasta) -> list[tuple]:
        """Os maiores arquivos de dentro da pasta, inclusive das subpastas: (em disco, arquivo, pasta dele)."""
        lista = self._cache_painel.get(id(pasta))
        if lista is None:
            def todos():
                pilha = [pasta]
                while pilha:
                    p = pilha.pop()
                    pilha.extend(p.pastas)
                    for a in p.arquivos:
                        yield a[2], a, p
            lista = heapq.nlargest(LIMITE_PAINEL, todos(), key=lambda t: t[0])
            self._cache_painel[id(pasta)] = lista
        return lista

    def _selecionou_no_mapa(self, pasta: leitor.Pasta, arquivo: tuple | None) -> None:
        if self._linhas_painel and self._pasta_painel is pasta:
            self._marcar_no_painel(arquivo)
            return
        self._pasta_painel = pasta
        self.lista_pasta.delete(*self.lista_pasta.get_children())
        lista = self._arquivos_dentro(pasta)
        self._linhas_painel = []
        base = len(pasta.caminho.rstrip("\\"))
        for disco, a, dono in lista:
            sub = dono.caminho[base:].lstrip("\\")
            nome, tags = a[0], ()
            if a[3] == -1:
                nome += "   (link físico, já contado)"
                tags = ("aviso",)
            iid = self.lista_pasta.insert("", "end", values=(tamanho(disco), tamanho(a[1]), nome, sub), tags=tags)
            self._linhas_painel.append((a, iid))
        nome = pasta.nome if pasta.pai is not None else pasta.caminho
        self.lbl_painel.configure(text=f"{nome}   ·   {tamanho(pasta.disco)}")
        texto = f"{numero(pasta.n_arquivos)} arquivos aqui dentro, contando as subpastas"
        if pasta.n_arquivos > LIMITE_PAINEL:
            texto += f"; mostrando os {numero(LIMITE_PAINEL)} maiores"
        self.lbl_painel2.configure(text=texto)
        self._marcar_no_painel(arquivo)

    def _marcar_no_painel(self, arquivo: tuple | None) -> None:
        iid = next((i for a, i in self._linhas_painel if a is arquivo), None) if arquivo is not None else None
        if iid:
            self.lista_pasta.selection_set(iid)
            self.lista_pasta.see(iid)
        else:
            self.lista_pasta.selection_set(())
            if self._linhas_painel:
                self.lista_pasta.see(self._linhas_painel[0][1])

    # ---------- árvore ----------

    def _novo_iid(self) -> str:
        self._contador += 1
        return f"i{self._contador}"

    def _abriu_pasta(self, _evento=None) -> None:
        iid = self.tree.focus()
        filhos = self.tree.get_children(iid)
        if len(filhos) == 1 and filhos[0].endswith("#"):
            self._preencher(iid)

    def _preencher(self, iid: str) -> None:
        p = self.pastas_da_arvore[iid]
        self.tree.delete(*self.tree.get_children(iid))
        eh_raiz = iid == "r"
        total = (self._total_raiz if eh_raiz else p.disco) or 1
        itens = list(heapq.merge(p.pastas, p.arquivos, key=_disco_de, reverse=True))
        nao_achado = self.leitura.nao_encontrado() if eh_raiz and self.leitura else 0
        sumido_pendente = nao_achado > 0
        for x in itens[:LIMITE]:
            if sumido_pendente and _disco_de(x) < nao_achado:
                self._linha_sumida(iid, nao_achado, total)
                sumido_pendente = False
            if isinstance(x, leitor.Pasta):
                self._linha_pasta(iid, x, total)
            else:
                self._linha_arquivo(iid, x, total)
        if sumido_pendente:
            self._linha_sumida(iid, nao_achado, total)
        resto = itens[LIMITE:]
        if resto:
            soma = sum(_disco_de(x) for x in resto)
            self.tree.insert(iid, "end", iid=self._novo_iid(), text=f"... mais {numero(len(resto))} itens menores",
                             image=self.img("resto", soma / total),
                             values=(tamanho(soma), porcento(soma / total), "", ""), tags=("aviso",))

    def _linha_pasta(self, pai: str, p: leitor.Pasta, total: int) -> None:
        nome = p.nome
        tags = ()
        if p.link:
            nome += "   (atalho para outra pasta, não somado aqui)"
            tags = ("aviso",)
        elif p.sem_acesso:
            nome += "   (sem acesso)"
            tags = ("aviso",)
        frac = p.disco / total
        iid = self._novo_iid()
        self.tree.insert(pai, "end", iid=iid, text=nome, image=self.img("pasta_aviso" if tags else "pasta", frac),
                         tags=tags, values=(tamanho(p.disco), porcento(frac), tamanho(p.tam), numero(p.n_arquivos)))
        if p.pastas or p.arquivos:
            self.pastas_da_arvore[iid] = p
            self.tree.insert(iid, "end", iid=iid + "#", text="")

    def _linha_arquivo(self, pai: str, a: tuple, total: int) -> None:
        nome, tam, disco, fid = a
        tags = ()
        if fid == -1:
            nome += "   (link físico: o mesmo arquivo já foi contado em outro lugar)"
            tags = ("aviso",)
        frac = disco / total
        self.tree.insert(pai, "end", iid=self._novo_iid(), text=nome, tags=tags,
                         image=self.img("arquivo_aviso" if tags else "arquivo", frac),
                         values=(tamanho(disco), porcento(frac), tamanho(tam), ""))

    def _linha_sumida(self, pai: str, n: int, total: int) -> None:
        frac = n / total
        texto = "Fora dos arquivos listados: metadados do NTFS, pontos de restauração"
        texto += ", pastas sem acesso" if not self.admin else ""
        self.tree.insert(pai, "end", iid=self._novo_iid(), text=texto, tags=("sumido",), image=self.img("sumido", frac),
                         values=(tamanho(n), porcento(frac), "", ""))

    # ---------- administrador ----------

    def reabrir_como_admin(self) -> None:
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            exe = exe[:-10] + "pythonw.exe"  # sem janela preta de console atrás
        parametros = f'"{config.RAIZ / "iniciar.pyw"}"'
        if self._raiz_escolhida:
            parametros += f" --escanear {self._raiz_escolhida.rstrip(chr(92))}"
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, parametros, str(config.RAIZ), 1)
        if r > 32:
            self.tk.destroy()
        else:
            self.lbl_status.configure(text="Não abriu como administrador (o Windows pediu permissão e ela foi negada).")

    # ---------- atualização ----------

    def _marcar_que_abriu(self) -> None:
        try:
            atualizador.PASTA.mkdir(parents=True, exist_ok=True)
            atualizador.ABRIU.touch()
        except OSError:
            pass

    def procurar_atualizacao(self, forcar: bool = False) -> None:
        self.bt_procurar.configure(state="disabled")
        self.lbl_att.configure(text="Procurando atualização..." if forcar else "")
        self._info_att = None

        def trabalho():
            self._info_att = atualizador.checar(forcar)

        threading.Thread(target=trabalho, daemon=True).start()
        self.tk.after(300, self._esperar_checagem)

    def _esperar_checagem(self) -> None:
        info = self._info_att
        if info is None:
            self.tk.after(300, self._esperar_checagem)
            return
        self.bt_procurar.configure(state="normal")
        if info.get("erro"):
            self.lbl_att.configure(text=info["erro"])
        elif info.get("nova"):
            self.lbl_att.configure(text=f"Versão {info['ultima']} disponível.")
            self.bt_atualizar.pack(side="right", padx=6)
        else:
            self.lbl_att.configure(text="Você está na versão mais nova.")

    def instalar_atualizacao(self) -> None:
        if self.leitura and not self.leitura.terminou.is_set():
            self.lbl_att.configure(text="Espere a leitura terminar (ou pare) antes de atualizar.")
            return
        self.bt_atualizar.configure(state="disabled")
        self.lbl_att.configure(text="Baixando a versão nova...")
        self._att_pronta = None

        def trabalho():
            try:
                atualizador.baixar_e_preparar()
                self._att_pronta = ""
            except atualizador.ErroAtualizacao as e:
                self._att_pronta = str(e)
            except Exception as e:  # noqa: BLE001  falha de rede ou disco aparece na janela
                self._att_pronta = f"Não deu para baixar ({e})."

        threading.Thread(target=trabalho, daemon=True).start()
        self.tk.after(300, self._esperar_download)

    def _esperar_download(self) -> None:
        if self._att_pronta is None:
            self.tk.after(300, self._esperar_download)
            return
        if self._att_pronta:
            self.lbl_att.configure(text=self._att_pronta)
            self.bt_atualizar.configure(state="normal")
            return
        self.codigo_saida = atualizador.SAIR_PARA_ATUALIZAR
        self.tk.destroy()


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--escanear", help="já abre lendo esta unidade (ex.: C:)")
    a = args.parse_args()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    raiz = tk.Tk()
    app = App(raiz, a.escanear)
    raiz.mainloop()
    if app.leitura:
        app.leitura.parar.set()
    sys.exit(app.codigo_saida)


if __name__ == "__main__":
    main()
