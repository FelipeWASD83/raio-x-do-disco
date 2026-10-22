"""Testes do mapa de blocos: área proporcional, nada sobreposto, tudo dentro da pasta de cima e os limites.

Rodar: python -m unittest discover -s testes
"""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import leitor, mapa  # noqa: E402

EPS = 1e-6


def sobrepoe(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax + aw > bx + EPS and bx + bw > ax + EPS and ay + ah > by + EPS and by + bh > ay + EPS


def arvore(semente: int, niveis: int = 3, pastas: int = 6, arquivos: int = 40) -> leitor.Pasta:
    """Uma árvore de mentira, já somada pelo mesmo `somar()` da leitura de verdade."""
    rnd = random.Random(semente)
    raiz = leitor.Pasta("X:\\", None, "X:\\")

    def encher(p, nivel):
        for i in range(rnd.randint(0, arquivos)):
            t = int(rnd.paretovariate(1.2) * 4096)
            p.arquivos.append((f"a{i}.bin", t, t, rnd.randint(1, 10**12)))
        if nivel < niveis:
            for i in range(rnd.randint(1, pastas)):
                f = leitor.Pasta(f"p{nivel}_{i}", p, leitor._juntar(p.caminho, f"p{nivel}_{i}"))
                p.pastas.append(f)
                encher(f, nivel + 1)

    encher(raiz, 0)
    leitor.somar(raiz)
    return raiz


class TestQuadrados(unittest.TestCase):
    def test_area_proporcional_e_sem_sobrepor(self):
        rnd = random.Random(1)
        for _ in range(50):
            valores = sorted((rnd.uniform(0.01, 100) for _ in range(rnd.randint(1, 60))), reverse=True)
            w, h = rnd.uniform(10, 2000), rnd.uniform(10, 1500)
            rets = mapa.quadrados(valores, 5, 7, w, h)
            self.assertEqual(len(rets), len(valores))
            total = sum(valores)
            for v, (x, y, rw, rh) in zip(valores, rets):
                self.assertAlmostEqual(rw * rh, v / total * w * h, delta=1e-6 * w * h)
                self.assertGreaterEqual(x, 5 - EPS)
                self.assertGreaterEqual(y, 7 - EPS)
                self.assertLessEqual(x + rw, 5 + w + 1e-6)
                self.assertLessEqual(y + rh, 7 + h + 1e-6)
            for i in range(len(rets)):
                for j in range(i + 1, len(rets)):
                    self.assertFalse(sobrepoe(rets[i], rets[j]), (i, j))

    def test_um_so_ocupa_tudo(self):
        [(x, y, w, h)] = mapa.quadrados([42], 0, 0, 300, 200)
        for real, esperado in zip((x, y, w, h), (0, 0, 300, 200)):
            self.assertAlmostEqual(real, esperado, places=6)

    def test_quase_quadrados(self):
        rets = mapa.quadrados([1] * 16, 0, 0, 400, 400)
        for _, _, w, h in rets:
            self.assertAlmostEqual(w / h, 1, delta=0.01)

    def test_vazio_e_retangulo_zero(self):
        self.assertEqual(mapa.quadrados([], 0, 0, 100, 100), [])
        self.assertEqual(mapa.quadrados([1, 2], 0, 0, 0, 100), [(0, 0, 0.0, 0.0)] * 2)


class TestMontar(unittest.TestCase):
    def test_filhos_dentro_da_pasta_e_sem_sobrepor(self):
        for semente in range(6):
            raiz = arvore(semente)
            blocos = mapa.montar(raiz, 1600, 900, 20)
            por_pasta = {}
            for b in blocos:
                if b.tipo == "pasta":
                    por_pasta[id(b.obj)] = b
            filhos = {}
            for b in blocos:
                if b is blocos[0]:
                    continue
                pai = b.obj.pai if b.tipo == "pasta" else b.pasta
                filhos.setdefault(id(pai), []).append(b)
                caixa = por_pasta[id(pai)]
                self.assertTrue(caixa.aberto)
                self.assertGreaterEqual(b.x, caixa.x + mapa.MARGEM - EPS)
                self.assertGreaterEqual(b.y, caixa.y + 20 - EPS)
                self.assertLessEqual(b.x + b.w, caixa.x + caixa.w - mapa.MARGEM + 1e-6)
                self.assertLessEqual(b.y + b.h, caixa.y + caixa.h - mapa.MARGEM + 1e-6)
            for lista in filhos.values():
                rets = [(b.x, b.y, b.w, b.h) for b in lista]
                for i in range(len(rets)):
                    for j in range(i + 1, len(rets)):
                        self.assertFalse(sobrepoe(rets[i], rets[j]))

    def test_tamanho_do_bloco_segue_o_espaco(self):
        raiz = arvore(3)
        blocos = mapa.montar(raiz, 1600, 900, 20)
        topo = [b for b in blocos if b is not blocos[0] and (b.pasta is raiz or (b.tipo == "pasta" and b.obj.pai is raiz))]
        area = (1600 - 2 * mapa.MARGEM) * (900 - 20 - mapa.MARGEM)
        for b in topo:
            self.assertAlmostEqual(b.w * b.h, b.disco / raiz.disco * area, delta=area * 1e-6)
        self.assertEqual(sum(b.disco for b in topo if b.w * b.h >= 16), raiz.disco)

    def test_menores_junta_o_resto(self):
        raiz = leitor.Pasta("X:\\", None, "X:\\")
        raiz.arquivos = [("grande", 10**9, 10**9, 1)] + [(f"m{i}", 100, 100, i + 2) for i in range(500)]
        leitor.somar(raiz)
        blocos = mapa.montar(raiz, 800, 600, 20)
        menores = [b for b in blocos if b.tipo == "menores"]
        self.assertEqual(len(menores), 1)
        self.assertEqual(menores[0].qtd, 500)
        self.assertEqual(menores[0].disco, 50_000)

    def test_espaco_sumido_na_raiz(self):
        raiz = arvore(2)
        blocos = mapa.montar(raiz, 1600, 900, 20, extra=raiz.disco)
        sumido = [b for b in blocos if b.tipo == "sumido"]
        self.assertEqual(len(sumido), 1)
        self.assertEqual(blocos[0].disco, 2 * raiz.disco)

    def test_limite_de_blocos(self):
        raiz = arvore(5, niveis=5, pastas=8, arquivos=80)
        self.assertLessEqual(len(mapa.montar(raiz, 3440, 1300, 20, limite=500)), 500 + mapa.MAX_FILHOS)
        cheio = mapa.montar(raiz, 3440, 1300, 20)
        self.assertLessEqual(len(cheio), mapa.LIMITE_BLOCOS + mapa.MAX_FILHOS)

    def test_pasta_vazia(self):
        raiz = leitor.Pasta("X:\\", None, "X:\\")
        leitor.somar(raiz)
        self.assertEqual(len(mapa.montar(raiz, 800, 600, 20)), 1)


if __name__ == "__main__":
    unittest.main()
