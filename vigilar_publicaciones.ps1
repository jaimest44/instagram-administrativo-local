# Comprueba cada noche que las dos cuentas han publicado el carrusel del dia.
# Si falta alguno, relanza la publicacion; si sigue faltando, muestra un aviso en Windows.
# Lo lanza la tarea "Instagram - vigilar publicaciones" (22:15). Registro en salida\vigilancia.log

param([string]$Fecha = (Get-Date).ToString("yyyy-MM-dd"), [string]$Franja, [switch]$SoloComprobar)

$repos = @(
  @{ repo = "jaimest44/instagram-administrativo-local"; cuenta = "@administrativo_local_andalucia" },
  @{ repo = "jaimest44/instagram-local-andalucia";      cuenta = "@localandalucia" }
)
$gh  = "C:\Program Files\GitHub CLI\gh.exe"
$log = Join-Path $PSScriptRoot "salida\vigilancia.log"
$hoy = $Fecha
# a media tarde se vigila la publicacion de mediodia; por la noche, la de la noche
if (-not $PSBoundParameters.ContainsKey("Franja")) { $Franja = $(if ((Get-Date).Hour -lt 18) { "mediodia" } else { "noche" }) }
$clave = $(if ($Franja -eq "mediodia") { "${hoy}_mediodia" } else { $hoy })
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

function Publicado($repo) {
  $b64 = & $gh api "repos/$repo/contents/estado/publicadas.json" --jq .content 2>$null
  if (-not $b64) { return $false }
  $json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(($b64 -join "")))
  return ($json | ConvertFrom-Json).PSObject.Properties.Name -contains $clave
}

function Hay-Cola($repo) {
  & $gh api "repos/$repo/contents/cola/$clave/meta.json" --silent 2>$null
  return $LASTEXITCODE -eq 0
}

function Avisar($texto) {
  Add-Type -AssemblyName System.Windows.Forms
  $n = New-Object System.Windows.Forms.NotifyIcon
  $n.Icon = [System.Drawing.SystemIcons]::Warning
  $n.Visible = $true
  $n.ShowBalloonTip(30000, "Instagram: falta una publicación", $texto, "Warning")
  Start-Sleep -Seconds 30
  $n.Dispose()
}

if ($SoloComprobar) {
  foreach ($r in $repos) { "{0}  {1}: publicado={2}  carrusel en cola={3}" -f $clave, $r.cuenta, (Publicado $r.repo), (Hay-Cola $r.repo) }
  return
}

$pendientes = @()
foreach ($r in $repos) {
  if (Publicado $r.repo) {
    Add-Content $log "$clave $(Get-Date -f HH:mm) OK $($r.cuenta)"
  } elseif (-not (Hay-Cola $r.repo)) {
    Add-Content $log "$clave $(Get-Date -f HH:mm) SIN COLA $($r.cuenta)"
    Avisar "$($r.cuenta) no tiene carrusel preparado para $clave. Ejecuta actualizar_cola.bat."
  } else {
    Add-Content $log "$clave $(Get-Date -f HH:mm) FALTA $($r.cuenta): relanzando"
    & $gh workflow run publicar.yml -R $r.repo -f modo=publicar
    $pendientes += $r
  }
}

if ($pendientes.Count) {
  Start-Sleep -Seconds 240
  foreach ($r in $pendientes) {
    if (Publicado $r.repo) {
      Add-Content $log "$clave $(Get-Date -f HH:mm) OK tras relanzar $($r.cuenta)"
    } else {
      Add-Content $log "$clave $(Get-Date -f HH:mm) ERROR $($r.cuenta)"
      Avisar "$($r.cuenta) no ha publicado $clave ni tras reintentarlo. Mira GitHub > Actions."
    }
  }
}
