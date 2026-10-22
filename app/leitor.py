"""Leitura do disco: percorre todas as pastas a partir de uma raiz e soma o que cada uma ocupa.

Cada pasta é lida de uma vez com GetFileInformationByHandleEx(FileIdBothDirectoryInfo), que devolve, sem abrir
arquivo por arquivo, o tamanho, o espaço alocado no disco, os atributos, a etiqueta de reparse e o FileId. Com isso:
- "em disco" é o espaço alocado de verdade (arquivo comprimido, esparso ou na nuvem conta o que ocupa, não o nominal);
- link físico (o mesmo FileId em dois lugares, comum no WinSxS) conta uma vez só;
- junção e link simbólico não são seguidos (senão a mesma pasta seria somada duas vezes ou entraria em laço).

Vários threads leem pastas ao mesmo tempo; o ctypes solta o GIL nas chamadas do Windows, então o disco trabalha em
paralelo. Sistema de arquivos que não aceita essa chamada (alguns pendrives) cai no os.scandir.
"""
from __future__ import annotations

import ctypes
import heapq
import os
import queue
import shutil
import struct
import threading
import time
from ctypes import wintypes as w

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_adv = ctypes.WinDLL("advapi32", use_last_error=True)

_k32.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
_k32.CreateFileW.restype = w.HANDLE
_k32.GetFileInformationByHandleEx.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD]
_k32.GetFileInformationByHandleEx.restype = w.BOOL
_k32.CloseHandle.argtypes = [w.HANDLE]
_k32.CloseHandle.restype = w.BOOL
_k32.GetCurrentProcess.restype = w.HANDLE
_k32.GetLogicalDrives.restype = w.DWORD
_adv.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
_adv.OpenProcessToken.restype = w.BOOL
_adv.LookupPrivilegeValueW.argtypes = [w.LPCWSTR, w.LPCWSTR, w.LPVOID]
_adv.LookupPrivilegeValueW.restype = w.BOOL
_adv.AdjustTokenPrivileges.argtypes = [w.HANDLE, w.BOOL, w.LPVOID, w.DWORD, w.LPVOID, w.LPVOID]
_adv.AdjustTokenPrivileges.restype = w.BOOL

_INVALIDO = w.HANDLE(-1).value
_FILE_LIST_DIRECTORY = 0x1
_COMPARTILHAR_TUDO = 0x7
_OPEN_EXISTING = 3
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FileIdBothDirectoryInfo = 10
_ERRO_SEM_MAIS_ARQUIVOS = 18
_ERROS_NAO_SUPORTADO = {1, 50, 87, 124}

_ATTR_PASTA = 0x10
_ATTR_REPARSE = 0x400
# junção/ponto de montagem e link simbólico: apontam para outro lugar, que já é (ou não deve ser) somado por lá
_TAGS_NAO_SEGUIR = {0xA0000003, 0xA000000C}

# FILE_ID_BOTH_DIR_INFO: NextEntryOffset, (FileIndex + 4 datas), EndOfFile, AllocationSize, FileAttributes,
# FileNameLength, EaSize (a etiqueta de reparse, quando é reparse), (nome curto), FileId; o nome começa no 104
_ENTRADA = struct.Struct("<I36xqqIII28xq")
_INICIO_NOME = 104
_BUFFER = 256 * 1024


class Pasta:
    __slots__ = ("nome", "pai", "caminho", "pastas", "arquivos", "tam", "disco", "n_arquivos", "n_pastas",
                 "sem_acesso", "link")

    def __init__(self, nome: str, pai: "Pasta | None", caminho: str):
        self.nome = nome
        self.pai = pai
        self.caminho = caminho
        self.pastas: list[Pasta] = []
        # (nome, tamanho, em disco, FileId); depois da soma o FileId vira -1 no link físico já contado em outro lugar
        self.arquivos: list[tuple] = []
        self.tam = 0
        self.disco = 0
        self.n_arquivos = 0
        self.n_pastas = 0
        self.sem_acesso = False
        self.link = False


class Leitura:
    """Uma leitura completa de um disco ou pasta. `iniciar()` roda em segundo plano; `progresso()` dá os números."""

    def __init__(self, raiz: str, threads: int = 16):
        if len(raiz) == 2 and raiz[1] == ":":
            raiz += "\\"  # "C:" sozinho é a pasta atual do C:, não a raiz
        raiz = os.path.abspath(raiz)
        self.raiz = Pasta(raiz, None, raiz)
        self.threads = threads
        self.parar = threading.Event()
        self.terminou = threading.Event()
        self.lidos_arquivos = 0
        self.lidas_pastas = 0
        self.lido_disco = 0
        self.pastas_sem_acesso = 0
        self.atual = raiz
        self.inicio = 0.0
        self.duracao = 0.0
        self.cancelada = False
        self.erro: str | None = None
        self._trava = threading.Lock()
        self._fila: queue.SimpleQueue = queue.SimpleQueue()
        self._pendentes = 0
        try:
            self.uso = shutil.disk_usage(raiz)
        except OSError:
            self.uso = None

    # ---------- leitura ----------

    def iniciar(self) -> None:
        threading.Thread(target=self._rodar, daemon=True, name="leitura").start()

    def _rodar(self) -> None:
        self.inicio = time.perf_counter()
        try:
            self._pendentes = 1
            self._fila.put(self.raiz)
            trabalhadores = [threading.Thread(target=self._trabalhar, daemon=True) for _ in range(self.threads)]
            for t in trabalhadores:
                t.start()
            for t in trabalhadores:
                t.join()
            self.cancelada = self.parar.is_set()
            if not self.cancelada:
                somar(self.raiz)
        except Exception as e:  # noqa: BLE001  qualquer falha vira mensagem na janela, não um app travado
            self.erro = f"{type(e).__name__}: {e}"
        finally:
            self.duracao = time.perf_counter() - self.inicio
            self.terminou.set()

    def _trabalhar(self) -> None:
        buf = ctypes.create_string_buffer(_BUFFER)
        while True:
            pasta = self._fila.get()
            if pasta is None:
                return
            if not self.parar.is_set():
                try:
                    self._ler(pasta, buf)
                except Exception:  # noqa: BLE001  uma pasta estranha não derruba a leitura inteira
                    pasta.sem_acesso = True
            with self._trava:
                self._pendentes -= 1
                if pasta.sem_acesso:
                    self.pastas_sem_acesso += 1
                if self._pendentes == 0:
                    for _ in range(self.threads):
                        self._fila.put(None)

    def _ler(self, pasta: Pasta, buf) -> None:
        self.atual = pasta.caminho
        h = _k32.CreateFileW("\\\\?\\" + pasta.caminho, _FILE_LIST_DIRECTORY, _COMPARTILHAR_TUDO, None,
                             _OPEN_EXISTING, _FILE_FLAG_BACKUP_SEMANTICS, None)
        if h == _INVALIDO or h is None:
            pasta.sem_acesso = True
            return
        novas: list[Pasta] = []
        n_arq = 0
        soma = 0
        try:
            primeira = True
            while True:
                if not _k32.GetFileInformationByHandleEx(h, _FileIdBothDirectoryInfo, buf, _BUFFER):
                    erro = ctypes.get_last_error()
                    if erro == _ERRO_SEM_MAIS_ARQUIVOS:
                        break
                    if primeira and erro in _ERROS_NAO_SUPORTADO:
                        _k32.CloseHandle(h)
                        h = None
                        self._ler_scandir(pasta)
                        return
                    pasta.sem_acesso = True
                    break
                primeira = False
                pos = 0
                while True:
                    prox, tam, disco, attr, n_nome, etiqueta, fid = _ENTRADA.unpack_from(buf, pos)
                    nome = buf[pos + _INICIO_NOME:pos + _INICIO_NOME + n_nome].decode("utf-16-le")
                    if attr & _ATTR_PASTA:
                        if nome != "." and nome != "..":
                            filha = Pasta(nome, pasta, _juntar(pasta.caminho, nome))
                            if attr & _ATTR_REPARSE and etiqueta in _TAGS_NAO_SEGUIR:
                                filha.link = True
                            pasta.pastas.append(filha)
                            if not filha.link:
                                novas.append(filha)
                    else:
                        pasta.arquivos.append((nome, tam, disco, fid))
                        n_arq += 1
                        soma += disco
                    if prox == 0:
                        break
                    pos += prox
        finally:
            if h is not None:
                _k32.CloseHandle(h)
        self._contar(novas, n_arq, soma)

    def _ler_scandir(self, pasta: Pasta) -> None:
        novas: list[Pasta] = []
        n_arq = 0
        soma = 0
        try:
            with os.scandir("\\\\?\\" + pasta.caminho) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if e.is_dir(follow_symlinks=False):
                        filha = Pasta(e.name, pasta, _juntar(pasta.caminho, e.name))
                        if st.st_file_attributes & _ATTR_REPARSE and st.st_reparse_tag in _TAGS_NAO_SEGUIR:
                            filha.link = True
                        pasta.pastas.append(filha)
                        if not filha.link:
                            novas.append(filha)
                    else:
                        pasta.arquivos.append((e.name, st.st_size, st.st_size, 0))
                        n_arq += 1
                        soma += st.st_size
        except OSError:
            pasta.sem_acesso = True
        self._contar(novas, n_arq, soma)

    def _contar(self, novas: list[Pasta], n_arq: int, soma: int) -> None:
        with self._trava:
            self._pendentes += len(novas)
            self.lidas_pastas += 1
            self.lidos_arquivos += n_arq
            self.lido_disco += soma
        for p in novas:
            self._fila.put(p)

    # ---------- resultado ----------

    def progresso(self) -> dict:
        usado = self.uso.used if self.uso else 0
        decorrido = (self.duracao if self.terminou.is_set() else time.perf_counter() - self.inicio) if self.inicio else 0
        return {"arquivos": self.lidos_arquivos, "pastas": self.lidas_pastas, "disco": self.lido_disco,
                "usado": usado, "atual": self.atual, "segundos": decorrido, "sem_acesso": self.pastas_sem_acesso}

    def nao_encontrado(self) -> int:
        """Espaço usado no disco que não apareceu em arquivo nenhum (metadados do NTFS, pastas sem acesso...)."""
        if not self.uso or self.raiz.caminho.rstrip("\\") != os.path.splitdrive(self.raiz.caminho)[0]:
            return 0
        return max(0, self.uso.used - self.raiz.disco)

    def maiores_arquivos(self, n: int = 500) -> list[tuple]:
        """(em disco, tamanho, caminho da pasta, nome) dos n arquivos que mais ocupam."""
        def todos():
            pilha = [self.raiz]
            while pilha:
                p = pilha.pop()
                pilha.extend(p.pastas)
                for a in p.arquivos:
                    yield a[2], a[1], p.caminho, a[0]
        return heapq.nlargest(n, todos(), key=lambda t: t[0])


def _juntar(pai: str, nome: str) -> str:
    return pai + nome if pai.endswith("\\") else pai + "\\" + nome


def somar(raiz: Pasta) -> None:
    """Soma de baixo para cima, conta link físico uma vez só e ordena tudo do maior para o menor."""
    ordem: list[Pasta] = []
    pilha = [raiz]
    vistos: set[int] = set()
    while pilha:
        p = pilha.pop()
        ordem.append(p)
        arqs = p.arquivos
        for i, a in enumerate(arqs):
            fid = a[3]
            if fid:
                if fid in vistos:
                    arqs[i] = (a[0], a[1], 0, -1)
                else:
                    vistos.add(fid)
        pilha.extend(reversed(p.pastas))
    vistos.clear()
    for p in reversed(ordem):
        tam = disco = 0
        n_arq = len(p.arquivos)
        for a in p.arquivos:
            if a[3] != -1:
                tam += a[1]
                disco += a[2]
        n_pas = len(p.pastas)
        for f in p.pastas:
            tam += f.tam
            disco += f.disco
            n_arq += f.n_arquivos
            n_pas += f.n_pastas
        p.tam, p.disco, p.n_arquivos, p.n_pastas = tam, disco, n_arq, n_pas
        p.pastas.sort(key=lambda f: f.disco, reverse=True)
        p.arquivos.sort(key=lambda a: a[2], reverse=True)


# ---------- disco e permissão ----------

def discos() -> list[dict]:
    """As unidades com letra que dá para ler (HD, SSD, pendrive, rede), com nome e uso."""
    mascara = _k32.GetLogicalDrives()
    tipos = {2: "Removível", 3: "Local", 4: "Rede", 6: "RAM"}
    saida = []
    for i in range(26):
        if not mascara & (1 << i):
            continue
        raiz = f"{chr(65 + i)}:\\"
        tipo = _k32.GetDriveTypeW(raiz)
        if tipo not in tipos:
            continue
        nome = ctypes.create_unicode_buffer(261)
        fs = ctypes.create_unicode_buffer(261)
        if not _k32.GetVolumeInformationW(raiz, nome, 261, None, None, None, fs, 261):
            continue
        try:
            uso = shutil.disk_usage(raiz)
        except OSError:
            continue
        saida.append({"raiz": raiz, "nome": nome.value, "fs": fs.value, "tipo": tipos[tipo],
                      "total": uso.total, "usado": uso.used, "livre": uso.free})
    return saida


def eh_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", w.DWORD), ("HighPart", w.LONG)]


class _PRIVILEGIO(ctypes.Structure):
    _fields_ = [("PrivilegeCount", w.DWORD), ("Luid", _LUID), ("Attributes", w.DWORD)]


def ligar_privilegio_de_backup() -> bool:
    """Como administrador, o privilégio de backup deixa listar qualquer pasta (System Volume Information inclusive)."""
    token = w.HANDLE()
    if not _adv.OpenProcessToken(_k32.GetCurrentProcess(), 0x0020 | 0x0008, ctypes.byref(token)):
        return False
    try:
        luid = _LUID()
        if not _adv.LookupPrivilegeValueW(None, "SeBackupPrivilege", ctypes.byref(luid)):
            return False
        priv = _PRIVILEGIO(1, luid, 0x2)
        _adv.AdjustTokenPrivileges(token, False, ctypes.byref(priv), 0, None, None)
        return ctypes.get_last_error() == 0
    finally:
        _k32.CloseHandle(token)
