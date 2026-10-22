# Raio-X do Disco

Escolhe um disco, lê tudo o que tem nele e mostra o que está ocupando espaço: um mapa de blocos no estilo do
SpaceSniffer (cada pasta do tamanho do espaço que ocupa), as pastas em lista do maior para o menor e os 500
maiores arquivos.

## Como usar

1. Abra pelo atalho **Raio-X do Disco** no Menu Iniciar.
2. Escolha o disco na lista de cima (ela mostra quanto cada um tem usado e livre) e clique em **Escanear**.
   O C: inteiro leva uns 20 a 35 segundos.
3. A aba **Mapa** abre sozinha: cada bloco é uma pasta ou um arquivo, do tamanho do espaço que ocupa.
   - **Um clique** numa pasta mostra na lista ao lado os arquivos de dentro dela (inclusive das subpastas),
     do maior para o menor. Clicar num arquivo marca ele na lista.
   - **Dois cliques** entram na pasta. A trilha em cima volta para qualquer nível; o **Backspace** sobe um.
   - Passando o mouse, a linha embaixo do mapa mostra o caminho completo e o tamanho.
   - Na janela estreita (monitor em pé) a lista vai para baixo do mapa. A divisória pode ser arrastada.
4. Na aba **Pastas**, a mesma coisa em forma de lista: clique na setinha para abrir, já do maior para o menor.
   A barra azul é quanto aquilo ocupa da pasta de cima.
5. Na aba **Maiores arquivos** ficam os 500 arquivos que mais ocupam no disco inteiro, com a pasta de cada um.

**Reabrir como administrador** (botão no canto) lê também as pastas que o Windows esconde de usuário comum,
como os pontos de restauração. Sem isso o resultado continua certo, só que essas pastas aparecem como
"sem acesso" e o espaço delas entra na linha laranja.

## O que cada coisa quer dizer

- **Em disco**: o espaço que o arquivo ocupa de verdade. É o número que importa para liberar espaço.
- **Tamanho**: o tamanho do arquivo. Pode ser maior que "em disco" (arquivo comprimido pelo Windows, ou do
  OneDrive que está só na nuvem) ou um pouco menor (o disco guarda em blocos).
- **Bloco ou linha laranja** (na raiz do disco): o que está usado no disco mas não aparece em arquivo nenhum
  (o índice do NTFS, pontos de restauração, pastas sem acesso).
- **Atalho para outra pasta, não somado aqui**: junção ou link simbólico. O conteúdo já é contado no lugar
  de verdade.
- **Link físico**: o mesmo arquivo aparecendo em duas pastas (o Windows faz muito isso no `WinSxS`). Conta
  uma vez só.

O app só lê: não apaga, não move e não muda nada no disco.

## Atualização

No rodapé, **Procurar atualização** confere se tem versão nova no GitHub. Se tiver, aparece **Atualizar
agora**: o app baixa, confere o pacote, fecha e abre já na versão nova (se a nova não abrir, volta sozinho
para a anterior).

## Instalar em outro PC

Precisa do Python 3.13 instalado. Baixe o pacote da release, rode `instalar.bat` e abra com
`.venv\Scripts\pythonw.exe iniciar.pyw`.
