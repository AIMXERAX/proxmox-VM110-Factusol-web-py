param(
  [string]$ProjectPath = (Get-Location).Path,
  [string]$ExportDirName = 'Export',
  [int]$MaxExports = 5,
  [switch]$IncludeEnv,
  [switch]$RefreshRequirements
)

$ErrorActionPreference = 'Stop'

$project = (Resolve-Path -LiteralPath $ProjectPath).Path
Set-Location $project

$folderName = Split-Path $project -Leaf
$safeName = $folderName -replace '[^a-zA-Z0-9_-]', '_'
$date = Get-Date -Format 'yyyy-MM-dd_HH-mm'

$exportDir = Join-Path $project $ExportDirName
$tempRoot = Join-Path $project '.export_temp'
$zipName = "Export_${safeName}_$date.zip"
$zipPath = Join-Path $exportDir $zipName

function Write-Step([string]$Message) {
  Write-Host "==> $Message"
}

function Test-IsUnderProject([string]$Path) {
  $resolved = (Resolve-Path -LiteralPath $Path).Path
  return ($resolved -eq $project -or $resolved.StartsWith($project + [IO.Path]::DirectorySeparatorChar))
}

Write-Step "Preparando exportacion de $project"

if ($RefreshRequirements) {
  Write-Step 'Actualizando requirements.txt desde el entorno activo'
  python -m pip freeze --local | Out-File -FilePath (Join-Path $project 'requirements.txt') -Encoding utf8
}

$requirementsPath = Join-Path $project 'requirements.txt'
if (Test-Path -LiteralPath $requirementsPath) {
  Write-Step 'requirements.txt detectado'
} else {
  Write-Host 'Aviso: no existe requirements.txt. El ZIP se creara igual, pero la restauracion requerira instalar dependencias manualmente.'
}

if (Test-Path -LiteralPath $tempRoot) {
  if (-not (Test-IsUnderProject $tempRoot)) {
    throw "Ruta temporal insegura: $tempRoot"
  }
  Remove-Item -LiteralPath $tempRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $tempRoot | Out-Null

$excludeDirNames = @(
  '.git', '.hg', '.svn',
  '.vscode', '.idea',
  '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
  '.tox', '.nox',
  '.venv', 'venv', 'Include', 'Lib', 'Scripts',
  'node_modules',
  'build', 'dist', 'site',
  $ExportDirName,
  '.export_temp'
)

$excludeFileNames = @(
  'pyvenv.cfg',
  '.DS_Store',
  'Thumbs.db',
  'desktop.ini'
)

$excludeExt = @(
  '.pyc', '.pyo', '.pyd',
  '.log', '.tmp', '.bak',
  '.zip', '.7z', '.rar'
)

$files = Get-ChildItem -Path $project -Recurse -File -Force
$copied = 0
$skipped = 0
$requiredExportFiles = @('export_project.ps1', 'export_project.md')

foreach ($f in $files) {
  $full = $f.FullName
  $rel = $full.Substring($project.Length).TrimStart('\', '/')
  $parts = $rel -split '[\\/]'

  if ($parts | Where-Object { $excludeDirNames -contains $_ }) {
    $skipped++
    continue
  }
  if ($excludeFileNames -contains $f.Name) {
    $skipped++
    continue
  }
  if ($excludeExt -contains $f.Extension.ToLowerInvariant()) {
    $skipped++
    continue
  }
  if ($rel -like '*.egg-info*') {
    $skipped++
    continue
  }

  $dest = Join-Path $tempRoot $rel
  $destDir = Split-Path -Parent $dest
  if (-not (Test-Path -LiteralPath $destDir)) {
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
  }
  Copy-Item -LiteralPath $full -Destination $dest -Force
  $copied++
}

foreach ($requiredName in $requiredExportFiles) {
  $source = Join-Path $project $requiredName
  if (-not (Test-Path -LiteralPath $source)) {
    throw "Falta $requiredName en la raiz del proyecto. Este archivo es obligatorio para exportar y restaurar."
  }

  $dest = Join-Path $tempRoot $requiredName
  $alreadyCopied = Test-Path -LiteralPath $dest
  Copy-Item -LiteralPath $source -Destination $dest -Force
  if (-not $alreadyCopied) {
    $copied++
  }
}

if (-not (Test-Path -LiteralPath $exportDir)) {
  New-Item -ItemType Directory -Path $exportDir | Out-Null
}

Write-Step "Creando ZIP $zipName"
Compress-Archive -Path (Join-Path $tempRoot '*') -DestinationPath $zipPath -Force

$zip = Get-Item -LiteralPath $zipPath
Write-Host "ZIP creado: $($zip.FullName)"
Write-Host "Tamano (MB): $([Math]::Round($zip.Length / 1MB, 2))"
Write-Host "Archivos incluidos: $copied"
Write-Host "Archivos omitidos: $skipped"

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipRead = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
  $entryCount = $zipRead.Entries.Count
  Write-Host "Entradas en ZIP: $entryCount"

  $reqEntry = $zipRead.Entries | Where-Object { $_.FullName -eq 'requirements.txt' }
  if ($null -ne $reqEntry) {
    Write-Host 'requirements.txt incluido en ZIP: OK'
  } else {
    Write-Host 'requirements.txt incluido en ZIP: NO'
  }

  foreach ($requiredName in $requiredExportFiles) {
    $requiredEntry = $zipRead.Entries | Where-Object { $_.FullName -eq $requiredName }
    if ($null -eq $requiredEntry) {
      throw "$requiredName no fue incluido en el ZIP"
    }
    Write-Host "$requiredName incluido en ZIP: OK"
  }
}
finally {
  $zipRead.Dispose()
}

$oldExports = Get-ChildItem -Path $exportDir -Filter "Export_${safeName}_*.zip" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -Skip $MaxExports

foreach ($old in $oldExports) {
  Remove-Item -LiteralPath $old.FullName -Force
  Write-Host "Export antiguo eliminado: $($old.Name)"
}

Remove-Item -LiteralPath $tempRoot -Recurse -Force
