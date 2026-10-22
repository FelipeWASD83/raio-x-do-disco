# Changelog

## 2.0.0 (21/10/2026)

**Novo**

- Aba Mapa, no estilo do SpaceSniffer, que abre sozinha quando a leitura termina: cada pasta é um bloco do
  tamanho do espaço que ocupa, com o nome e o tamanho no topo e o que tem dentro desenhado lá dentro. O que é
  pequeno demais para desenhar vira um bloco só ("312 itens menores").
- Um clique numa pasta do mapa mostra, na lista ao lado, os arquivos de dentro dela, inclusive das subpastas,
  do maior para o menor (até 1000), com a subpasta de cada um. Clicar num arquivo do mapa marca ele na lista.
- Dois cliques entram na pasta; a trilha em cima (C:\ › Program Files › Steam) volta para qualquer nível, e o
  Backspace sobe um.
- Passar o mouse mostra embaixo do mapa o caminho completo, o tamanho e quanto aquilo pesa no disco.
- Na tela larga a lista fica ao lado do mapa; no monitor em pé, embaixo. A divisória pode ser arrastada.

**Mudou**

- O botão de reabrir como administrador desceu para a linha do uso do disco, e o texto do resultado quebra
  linha em vez de cortar: no monitor em pé eles não cabiam.

## 1.0.0 (21/10/2026)

**Novo**

- Escolhe um disco e lê tudo o que tem nele: o C: inteiro (1,6 milhão de arquivos, 1,7 TB) em uns 20 a 35 s.
- Aba Pastas: árvore do maior para o menor, com espaço em disco, porcentagem da pasta de cima, barra,
  tamanho e quantidade de arquivos.
- Aba Maiores arquivos: os 500 arquivos que mais ocupam, com a pasta de cada um.
- Na raiz do disco, uma linha com o espaço usado que não aparece em arquivo nenhum.
- Conta o espaço ocupado de verdade, não soma duas vezes link físico e não entra em atalho de pasta.
- Botão para reabrir como administrador e ler também as pastas protegidas do sistema.
- Atualização pelo GitHub dentro do app, com volta automática se a versão nova não abrir.
- Atalho no Menu Iniciar com ícone próprio.
