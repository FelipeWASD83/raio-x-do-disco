# CLAUDE.md: raio-x-do-disco

App de janela em Python (tkinter, só biblioteca padrão) que lê um disco inteiro e mostra o que ocupa espaço,
no estilo do TreeSize/WizTree. Roda só no PC do Felipe. Versão em `versao.json` e no topo do `CHANGELOG.md`
(andam juntos). Criado em 21/10/2026; repositório **público** (MIT).

## Como roda

```
atalho do Menu Iniciar ─► .venv\Scripts\pythonw.exe iniciar.pyw   (aplica atualização pendente, volta se falhar)
                              └─► pythonw -m app.principal        (janela; saída em dados/log.txt)
```

O `.venv` não tem pacote nenhum: existe só para o atalho ter um `pythonw` de caminho fixo (o
`criar-atalhos.ps1` junta o `alvo` com a pasta do projeto).

- `app/leitor.py`: a leitura. Cada pasta é lida com `GetFileInformationByHandleEx(FileIdBothDirectoryInfo)`
  por ctypes: uma chamada devolve, para todos os itens da pasta, tamanho, **espaço alocado**, atributos,
  etiqueta de reparse e FileId, sem abrir arquivo por arquivo. 8 threads (medido: 8 é mais rápido que 4, 16
  ou 32; o gargalo é a abertura de pasta no Windows, o parse em Python é ~10% do tempo). Sistema de arquivos
  que recusa essa chamada cai no `os.scandir`. `somar()` roda no fim: link físico (FileId repetido) conta uma
  vez só, na ordem da árvore, e tudo fica ordenado do maior para o menor.
- `app/principal.py`: a janela. A árvore é preenchida sob demanda (só monta os filhos quando a pasta é
  aberta, no máximo 1000 por pasta, o resto vira uma linha com a soma). O ícone e a barra de cada linha são
  uma imagem só (`Imagens`), porque o Treeview só aceita imagem na primeira coluna e não colore coluna.
- `app/atualizador.py`: cópia adaptada do `camera-ia/app/atualizador.py` (releases do GitHub, SHA-256, pasta
  `anterior` para voltar). Não toca em `dados/` nem `.venv/`. Cópia com `.git` (esta pasta) não se atualiza
  pelo app: é git pull.
- `publicar-versao.ps1`: publica a release (decisão do Felipe, como o push).
- Testes: `.venv\Scripts\python.exe -m unittest discover -s testes` (pasta temporária com link físico,
  junção, nome com acento e japonês; conferem a soma contra o `os.walk`).

## Decisões que não se desfazem sem motivo

- **Não segue junção nem link simbólico** (etiquetas `0xA0000003` e `0xA000000C`), mas entra nas outras
  pastas com reparse (OneDrive e afins), senão a pasta do OneDrive sumiria da soma.
- **"Em disco" é o AllocationSize**, não o tamanho: é o que libera espaço. A linha laranja da raiz é
  `usado no disco - soma em disco` (MFT, diário do NTFS, pastas sem acesso).
- **Como administrador** liga o `SeBackupPrivilege`, que deixa listar qualquer pasta (com
  `FILE_FLAG_BACKUP_SEMANTICS`). O botão "Reabrir como administrador" relança o `iniciar.pyw` por
  `ShellExecuteW runas` com `--escanear <letra>`.
- **Só lê.** Apagar, mover ou abrir no Explorador não existem de propósito (não foram pedidos).

## Como testar sem aparecer na tela dele

A janela pode ser fotografada sem aparecer: criar o `App` com `-alpha 0` e a janela com
`WS_EX_LAYERED | WS_EX_TRANSPARENT` (não pega clique), na tela, e capturar com `PrintWindow(hwnd, hdc, 2)`.
Fora da tela (`+30000+30000`) o Tk não pinta e a foto sai branca.

## Medido (21/10/2026, sem administrador)

C: com 1,65 milhão de arquivos e 352 mil pastas (1,7 TB): 34 s com o disco frio, 19 a 23 s nas leituras
seguintes; somar e ordenar no fim leva 0,6 s. 197 pastas sem acesso e 42 GB na linha laranja sem
administrador.

Não testado: o caminho como administrador (o UAC pede confirmação dele) e a atualização de ponta a ponta
(não tem release publicada).
