$ErrorActionPreference = 'Stop'

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'Esta versión del centro requiere Windows.'
}

try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()
} catch {
    $interfaceError = "No se pudo iniciar la interfaz de Windows.`n$($_.Exception.Message)"
    try {
        [System.Windows.Forms.MessageBox]::Show(
            $interfaceError, 'Centro de aplicaciones', 'OK', 'Error'
        ) | Out-Null
    } catch {
        Write-Error $interfaceError
    }
    exit 1
}

$script:Apps = [System.Collections.Generic.List[object]]::new()
$script:ScanWarnings = 0

function Get-StartMenuDirectories {
    $appData = if ($env:APPDATA) { $env:APPDATA } else { Join-Path $env:USERPROFILE 'AppData\Roaming' }
    $programData = if ($env:PROGRAMDATA) { $env:PROGRAMDATA } else { 'C:\ProgramData' }
    return @(
        (Join-Path $appData 'Microsoft\Windows\Start Menu\Programs'),
        (Join-Path $programData 'Microsoft\Windows\Start Menu\Programs')
    )
}

function Get-AppCategory([string]$ShortcutPath) {
    $parentNames = (Split-Path -Parent $ShortcutPath).Split([IO.Path]::DirectorySeparatorChar)
    if ($parentNames | Where-Object { $_ -match '^(?i:juegos|games)$' }) { return 'Juegos' }
    if ($parentNames | Where-Object { $_ -match '^(?i:accesorios|accessories|system tools|herramientas del sistema)$' }) {
        return 'Utilidades'
    }
    return 'Aplicaciones'
}

function Find-Applications {
    $seen = @{}
    foreach ($directory in Get-StartMenuDirectories) {
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) { continue }
        $scanErrors = @()
        try {
            $shortcuts = Get-ChildItem -LiteralPath $directory -Filter '*.lnk' -File -Recurse `
                -ErrorAction SilentlyContinue -ErrorVariable +scanErrors
            $script:ScanWarnings += $scanErrors.Count
            foreach ($shortcut in $shortcuts) {
                if ($shortcut.Name -match '^(?i:uninstall(?:\.exe)?\.lnk)$') { continue }
                $identity = $shortcut.FullName.ToLowerInvariant()
                if ($seen.ContainsKey($identity)) { continue }
                $seen[$identity] = $true
                $script:Apps.Add([pscustomobject]@{
                    Name = $shortcut.BaseName.Replace('_', ' ')
                    Category = Get-AppCategory $shortcut.FullName
                    Path = $shortcut.FullName
                })
            }
        } catch {
            $script:ScanWarnings++
        }
    }
    $sorted = @($script:Apps | Sort-Object { $_.Name }, { $_.Path })
    $script:Apps.Clear()
    foreach ($app in $sorted) { $script:Apps.Add($app) }
}

function Update-AppList {
    $listView.BeginUpdate()
    $listView.Items.Clear()
    $queryText = $searchBox.Text.Trim()
    $selectedCategory = [string]$categoryBox.SelectedItem
    foreach ($app in $script:Apps) {
        if ($selectedCategory -ne 'Todas' -and $app.Category -ne $selectedCategory) { continue }
        if ($queryText -and $app.Name.IndexOf($queryText, [StringComparison]::OrdinalIgnoreCase) -lt 0) { continue }
        $row = [System.Windows.Forms.ListViewItem]::new($app.Name)
        [void]$row.SubItems.Add($app.Category)
        $row.Tag = $app.Path
        [void]$listView.Items.Add($row)
    }
    $listView.EndUpdate()

    if ($listView.Items.Count -gt 0) {
        $statusLabel.Text = "$($listView.Items.Count) aplicaciones"
        if ($script:ScanWarnings -gt 0) {
            $statusLabel.Text += " · No se pudieron leer $($script:ScanWarnings) carpetas"
        }
    } else {
        $statusLabel.Text = 'No se encontraron aplicaciones en el menú Inicio.'
        if ($script:ScanWarnings -gt 0) {
            $statusLabel.Text += " No se pudieron leer $($script:ScanWarnings) carpetas."
        }
    }
}

function Open-SelectedApp {
    if ($listView.SelectedItems.Count -eq 0) { return }
    $item = $listView.SelectedItems[0]
    $shortcutPath = [string]$item.Tag
    if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) {
        [System.Windows.Forms.MessageBox]::Show(
            'El acceso directo ya no existe. Actualiza la lista o vuelve a abrir el centro.',
            'Aplicación no disponible', 'OK', 'Warning'
        ) | Out-Null
        return
    }
    try {
        Start-Process -FilePath $shortcutPath -ErrorAction Stop
        $statusLabel.Text = "Abriendo $($item.Text)…"
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            "No se pudo abrir $($item.Text).`n$($_.Exception.Message)",
            'Error al abrir', 'OK', 'Error'
        ) | Out-Null
    }
}

try {
    Find-Applications

    $form = [System.Windows.Forms.Form]::new()
    $form.Text = 'Centro de aplicaciones'
    $form.StartPosition = 'CenterScreen'
    $form.Size = [System.Drawing.Size]::new(780, 600)
    $form.MinimumSize = [System.Drawing.Size]::new(540, 400)
    $form.BackColor = [System.Drawing.Color]::FromArgb(16, 19, 27)
    $form.ForeColor = [System.Drawing.Color]::FromArgb(237, 240, 247)
    $form.Font = [System.Drawing.Font]::new('Segoe UI', 10)

    $title = [System.Windows.Forms.Label]::new()
    $title.Text = 'CENTRO DE APLICACIONES'
    $title.Font = [System.Drawing.Font]::new('Segoe UI', 18, [System.Drawing.FontStyle]::Bold)
    $title.Location = [System.Drawing.Point]::new(24, 18)
    $title.Size = [System.Drawing.Size]::new(700, 34)
    $form.Controls.Add($title)

    $subtitle = [System.Windows.Forms.Label]::new()
    $subtitle.Text = 'Aplicaciones del menú Inicio de Windows'
    $subtitle.ForeColor = [System.Drawing.Color]::FromArgb(160, 171, 192)
    $subtitle.Location = [System.Drawing.Point]::new(26, 56)
    $subtitle.Size = [System.Drawing.Size]::new(700, 24)
    $form.Controls.Add($subtitle)

    $searchBox = [System.Windows.Forms.TextBox]::new()
    $searchBox.Location = [System.Drawing.Point]::new(26, 94)
    $searchBox.Size = [System.Drawing.Size]::new(500, 30)
    $searchBox.Anchor = 'Top, Left, Right'
    $searchBox.BackColor = [System.Drawing.Color]::FromArgb(30, 36, 49)
    $searchBox.ForeColor = [System.Drawing.Color]::White
    $searchBox.BorderStyle = 'FixedSingle'
    $form.Controls.Add($searchBox)

    $categoryBox = [System.Windows.Forms.ComboBox]::new()
    $categoryBox.Location = [System.Drawing.Point]::new(538, 94)
    $categoryBox.Size = [System.Drawing.Size]::new(205, 30)
    $categoryBox.Anchor = 'Top, Right'
    $categoryBox.DropDownStyle = 'DropDownList'
    $categoryBox.BackColor = [System.Drawing.Color]::FromArgb(30, 36, 49)
    $categoryBox.ForeColor = [System.Drawing.Color]::White
    [void]$categoryBox.Items.AddRange([object[]]@('Todas', 'Aplicaciones', 'Juegos', 'Utilidades'))
    $categoryBox.SelectedIndex = 0
    $form.Controls.Add($categoryBox)

    $listView = [System.Windows.Forms.ListView]::new()
    $listView.Location = [System.Drawing.Point]::new(26, 140)
    $listView.Size = [System.Drawing.Size]::new(717, 350)
    $listView.Anchor = 'Top, Bottom, Left, Right'
    $listView.View = 'Details'
    $listView.FullRowSelect = $true
    $listView.HideSelection = $false
    $listView.MultiSelect = $false
    $listView.BackColor = [System.Drawing.Color]::FromArgb(25, 30, 42)
    $listView.ForeColor = [System.Drawing.Color]::FromArgb(237, 240, 247)
    [void]$listView.Columns.Add('Aplicación', 500)
    [void]$listView.Columns.Add('Categoría', 180)
    $form.Controls.Add($listView)

    $statusLabel = [System.Windows.Forms.Label]::new()
    $statusLabel.Location = [System.Drawing.Point]::new(26, 510)
    $statusLabel.Size = [System.Drawing.Size]::new(540, 28)
    $statusLabel.Anchor = 'Bottom, Left, Right'
    $statusLabel.ForeColor = [System.Drawing.Color]::FromArgb(160, 171, 192)
    $form.Controls.Add($statusLabel)

    $openButton = [System.Windows.Forms.Button]::new()
    $openButton.Text = 'Abrir'
    $openButton.Location = [System.Drawing.Point]::new(638, 504)
    $openButton.Size = [System.Drawing.Size]::new(105, 36)
    $openButton.Anchor = 'Bottom, Right'
    $form.Controls.Add($openButton)

    $searchBox.Add_TextChanged({ Update-AppList })
    $categoryBox.Add_SelectedIndexChanged({ Update-AppList })
    $openButton.Add_Click({ Open-SelectedApp })
    $listView.Add_DoubleClick({ Open-SelectedApp })
    $listView.Add_KeyDown({
        if ($_.KeyCode -eq [System.Windows.Forms.Keys]::Enter) {
            Open-SelectedApp
            $_.SuppressKeyPress = $true
        }
    })
    $form.Add_Shown({ $searchBox.Focus() })

    Update-AppList
    [void]$form.ShowDialog()
} catch {
    [System.Windows.Forms.MessageBox]::Show(
        "No se pudo abrir el Centro de aplicaciones.`n$($_.Exception.Message)",
        'Centro de aplicaciones', 'OK', 'Error'
    ) | Out-Null
    exit 1
}
