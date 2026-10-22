# Publica a versão atual do Raio-X do Disco como release no GitHub (é ela que o "Procurar atualização" do app baixa).
# Antes: subir a versão em versao.json e no CHANGELOG.md, commitar e dar push.
# Precisa do gh logado (gh auth login) com permissão no repositório. Publicar é decisão do Felipe.
$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
Set-Location $raiz

function Rodar([string]$exe, [string[]]$argumentos) {
    # No PowerShell 5.1, com 'Stop', qualquer linha que o git ou o gh escrevam no stderr vira erro fatal,
    # mesmo quando deu certo. Aqui quem decide é o código de saída.
    $ErrorActionPreference = 'Continue'
    $saida = & $exe @argumentos 2>&1 | ForEach-Object { "$_" }
    return [pscustomobject]@{ codigo = $LASTEXITCODE; saida = (($saida -join "`n").Trim()) }
}

$info = Get-Content (Join-Path $raiz 'versao.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$versao = $info.versao
$repo = $info.repositorio
$changelog = Get-Content (Join-Path $raiz 'CHANGELOG.md') -Raw -Encoding UTF8
if ($changelog -notmatch "## $([regex]::Escape($versao)) ") { throw "O CHANGELOG.md não tem a seção da versão $versao." }

if ((Rodar git @('status', '--porcelain')).saida) { throw 'Há mudanças não commitadas. Commite antes de publicar.' }
$r = Rodar git @('fetch', '-q', 'origin')
if ($r.codigo -ne 0) { throw "Não deu para falar com o GitHub (git fetch): $($r.saida)" }
$local = (Rodar git @('rev-parse', 'HEAD')).saida
$r = Rodar git @('rev-parse', '@{u}')
if ($r.codigo -ne 0) { throw 'Este ramo não está ligado ao GitHub. Rode: git push -u origin main' }
if ($local -ne $r.saida) { throw 'O commit atual ainda não foi enviado (git push) ou está atrás do GitHub.' }
if ((Rodar gh @('release', 'view', "v$versao", '--repo', $repo)).codigo -eq 0) { throw "A release v$versao já existe." }

# notas da release: só a seção desta versão do CHANGELOG
$linhas = $changelog -split "`r?`n"
$achou = $linhas | Where-Object { $_ -match "^## $([regex]::Escape($versao)) " } | Select-Object -First 1
$inicio = [array]::IndexOf($linhas, $achou)
$notas = @()
for ($i = $inicio + 1; $i -lt $linhas.Length; $i++) {
    if ($linhas[$i] -match '^## ') { break }
    $notas += $linhas[$i]
}
$tmp = Join-Path $env:TEMP "raio-x-do-disco-release-$versao"
New-Item -ItemType Directory -Force $tmp | Out-Null
$arqNotas = Join-Path $tmp 'notas.md'
[IO.File]::WriteAllText($arqNotas, (($notas -join "`n").Trim()), [Text.UTF8Encoding]::new($false))
# o pacote leva só o que está no git: nada de .venv nem dados/
$zip = Join-Path $tmp "raio-x-do-disco-$versao.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
$r = Rodar git @('archive', '--format=zip', "--prefix=raio-x-do-disco-$versao/", '-o', $zip, 'HEAD')
if ($r.codigo -ne 0) { throw "Não deu para gerar o pacote: $($r.saida)" }

Write-Host "Publicando v$versao em $repo com $zip"
$r = Rodar gh @('release', 'create', "v$versao", $zip, '--repo', $repo, '--title', "Raio-X do Disco $versao", '--notes-file', $arqNotas, '--target', $local)
if ($r.codigo -ne 0) { throw "O gh não criou a release: $($r.saida)" }
Write-Host $r.saida
Write-Host 'Pronto. O app instalado já enxerga esta versão no Procurar atualização.'
