"""Testes do leitor: soma, link físico contado uma vez, junção não seguida e o caminho do os.scandir.

Rodar: python -m unittest discover -s testes
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import leitor, principal  # noqa: E402


def ler(pasta) -> leitor.Leitura:
    l = leitor.Leitura(str(pasta), threads=4)
    l.iniciar()
    assert l.terminou.wait(60)
    assert l.erro is None, l.erro
    return l


class TestLeitor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        (self.raiz / "a" / "b").mkdir(parents=True)
        (self.raiz / "a" / "um.bin").write_bytes(b"x" * 10_000)
        (self.raiz / "a" / "b" / "dois.bin").write_bytes(b"y" * 50_000)
        (self.raiz / "tres.txt").write_bytes(b"z" * 123)
        (self.raiz / "vazia").mkdir()
        (self.raiz / "acentuação e 日本").mkdir()
        (self.raiz / "acentuação e 日本" / "ç.bin").write_bytes(b"w" * 777)

    def tearDown(self):
        self.tmp.cleanup()

    def test_soma_bate_com_os_walk(self):
        l = ler(self.raiz)
        esperado = sum(os.path.getsize(os.path.join(r, a)) for r, _, arqs in os.walk(self.raiz) for a in arqs)
        self.assertEqual(l.raiz.tam, esperado)
        self.assertEqual(l.raiz.n_arquivos, 4)
        self.assertEqual(l.raiz.n_pastas, 4)
        self.assertGreaterEqual(l.raiz.disco, l.raiz.tam - 123 - 777)  # arquivo minúsculo pode morar dentro da MFT

    def test_ordem_do_maior_para_o_menor(self):
        l = ler(self.raiz)
        self.assertEqual(l.raiz.pastas[0].nome, "a")
        self.assertEqual(l.raiz.pastas[0].tam, 60_000)
        self.assertEqual([a[0] for a in l.raiz.pastas[0].arquivos], ["um.bin"])

    def test_link_fisico_conta_uma_vez(self):
        os.link(self.raiz / "a" / "b" / "dois.bin", self.raiz / "dois-de-novo.bin")
        l = ler(self.raiz)
        self.assertEqual(l.raiz.tam, 10_000 + 50_000 + 123 + 777)
        repetidos = [a for p in (l.raiz, l.raiz.pastas[0].pastas[0]) for a in p.arquivos if a[3] == -1]
        self.assertEqual(len(repetidos), 1)

    def test_juncao_nao_e_seguida(self):
        subprocess.run(["cmd", "/c", "mklink", "/J", str(self.raiz / "atalho"), str(self.raiz / "a")],
                       check=True, capture_output=True)
        l = ler(self.raiz)
        atalho = next(p for p in l.raiz.pastas if p.nome == "atalho")
        self.assertTrue(atalho.link)
        self.assertEqual(atalho.tam, 0)
        self.assertEqual(l.raiz.tam, 10_000 + 50_000 + 123 + 777)

    def test_scandir_da_o_mesmo_resultado(self):
        l = leitor.Leitura(str(self.raiz), threads=1)
        l._ler_scandir(l.raiz)
        nomes = sorted(a[0] for a in l.raiz.arquivos)
        self.assertEqual(nomes, ["tres.txt"])
        self.assertEqual(sorted(p.nome for p in l.raiz.pastas), ["a", "acentuação e 日本", "vazia"])

    def test_maiores_arquivos(self):
        l = ler(self.raiz)
        maiores = l.maiores_arquivos(2)
        self.assertEqual([m[3] for m in maiores][:1], ["dois.bin"])
        self.assertTrue(maiores[0][2].endswith("\\a\\b"))

    def test_pasta_nao_tem_espaco_sumido(self):
        self.assertEqual(ler(self.raiz).nao_encontrado(), 0)

    def test_parar_no_meio(self):
        l = leitor.Leitura(str(self.raiz), threads=2)
        l.parar.set()
        l.iniciar()
        self.assertTrue(l.terminou.wait(30))
        self.assertTrue(l.cancelada)

    def test_discos_tem_o_c(self):
        self.assertIn("C:\\", [d["raiz"] for d in leitor.discos()])


class TestFormato(unittest.TestCase):
    def test_tamanho(self):
        self.assertEqual(principal.tamanho(500), "500 bytes")
        self.assertEqual(principal.tamanho(1536), "1,5 KB")
        self.assertEqual(principal.tamanho(250 * 2**30), "250 GB")
        self.assertEqual(principal.tamanho(1.7 * 2**40), "1,7 TB")

    def test_numero_e_porcento(self):
        self.assertEqual(principal.numero(1652077), "1.652.077")
        self.assertEqual(principal.porcento(0.574), "57,4 %")


if __name__ == "__main__":
    unittest.main()
