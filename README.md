# Raio-X do Disco

Escolhe um disco, lê tudo o que tem nele e mostra o que está ocupando espaço: as pastas do maior para o menor,
com quanto cada uma ocupa e quanto isso pesa dentro da pasta de cima, e a lista dos 500 maiores arquivos.

## Como usar

1. Abra pelo atalho **Raio-X do Disco** no Menu Iniciar.
2. Escolha o disco na lista de cima (ela mostra quanto cada um tem usado e livre) e clique em **Escanear**.
   O C: inteiro leva uns 20 a 35 segundos.
3. Na aba **Pastas**, clique na setinha de uma pasta para ver o que tem dentro, já do maior para o menor.
   A barra azul é quanto aquilo ocupa da pasta de cima.
4. Na aba **Maiores arquivos** ficam os 500 arquivos que mais ocupam, com a pasta de cada um.

**Reabrir como administrador** (botão no canto) lê também as pastas que o Windows esconde de usuário comum,
como os pontos de restauração. Sem isso o resultado continua certo, só que essas pastas aparecem como
"sem acesso" e o espaço delas entra na linha laranja.

## O que cada coisa quer dizer

- **Em disco**: o espaço que o arquivo ocupa de verdade. É o número que importa para liberar espaço.
- **Tamanho**: o tamanho do arquivo. Pode ser maior que "em disco" (arquivo comprimido pelo Windows, ou do
  OneDrive que está só na nuvem) ou um pouco menor (o disco guarda em blocos).
- **Linha laranja** (na raiz do disco): o que está usado no disco mas não aparece em arquivo nenhum
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
