# BAGO — Procedimiento de Desactivación

> Fecha de aprendizaje: 2026-05-08  
> Aprendido por: BAGO durante sesión con VERNY  
> Trigger original: "COPILOT elimina BAGO engine" → "Desactivalo y ocultalo" → "protegelo con contraseña"

---

## Concepto

Cuando el usuario pide **desactivar, ocultar o proteger BAGO**, el objetivo es:

1. Crear un backup cifrado de toda la carpeta BAGO
2. Eliminar la carpeta original del disco
3. Ocultar el backup con nombre neutro + atributos de sistema
4. Guardar la contraseña en un lugar accesible para el usuario

La carpeta BAGO se ha de poder **restaurar en cualquier momento** con la contraseña.

---

## Procedimiento Completo

### 1. Comprimir y cifrar con WinRAR

```powershell
$rar = "C:\Program Files\WinRAR\WinRAR.exe"
$src = "C:\Users\verny\BAGO"
$dest = "$env:USERPROFILE\BAGO_hidden.rar"
$pass = "CONTRASEÑA_GENERADA_ALEATORIAMENTE"

# -hp = cifra cabeceras + contenido (máxima protección)
# -r = recursivo, -ep1 = preserva estructura relativa
& $rar a -hp"$pass" -r -ep1 "$dest" "$src\*" 2>&1
```

**Nota:** Usar `-hp` (no `-p`) para que el propio listado de archivos también esté cifrado.

### 2. Verificar integridad del RAR antes de borrar

```powershell
& $rar t -hp"$pass" "$dest" 2>&1 | Select-Object -Last 3
```

Solo eliminar la carpeta original si WinRAR confirma que el archivo es válido.

### 3. Eliminar carpeta original

```powershell
Remove-Item -Path "C:\Users\verny\BAGO" -Recurse -Force
```

### 4. Ocultar el RAR con nombre neutro

```powershell
# Renombrar a nombre no obvio
Rename-Item -Path "$env:USERPROFILE\BAGO_hidden.rar" -NewName "system_backup_05.rar"

# Aplicar atributos oculto + sistema
attrib +h +s "$env:USERPROFILE\system_backup_05.rar"
```

### 5. Guardar contraseña en Desktop

```powershell
$desktop = [Environment]::GetFolderPath("Desktop")
Set-Content -Path "$desktop\BAGO_KEY.txt" -Value @"
BAGO — archivo protegido
Contraseña: $pass
Archivo: $env:USERPROFILE\system_backup_05.rar  (oculto)
Para restaurar: WinRAR → Extraer → Contraseña arriba → Destino: C:\Users\verny\BAGO
"@
```

---

## Restauración

```powershell
$rar = "C:\Program Files\WinRAR\WinRAR.exe"
$pass = "EAfK1shndvra40WR"  # leer de BAGO_KEY.txt
$src  = "$env:USERPROFILE\system_backup_05.rar"
$dest = "C:\Users\verny\"

& $rar x -hp"$pass" "$src" "$dest" 2>&1
```

O desde GUI: WinRAR → Abrir archivo → Extraer aquí → Introducir contraseña.

---

## Variantes Reconocidas

| Comando del usuario | Acción |
|---|---|
| "elimina BAGO" | Preguntar si desea backup antes de eliminar |
| "desactívalo" / "ocúltalo" | Comprimir + eliminar + ocultar RAR |
| "protégelo con contraseña" | Añadir cifrado `-hp` al proceso |
| "BAGO off" | Equivalente a desactivar |
| "restaura BAGO" | Extraer desde RAR con contraseña |

---

## Notas de implementación

- Generar contraseña aleatoria segura (16+ chars alfanuméricos):  
  `$pass = -join ((65..90)+(97..122)+(48..57) | Get-Random -Count 16 | % {[char]$_})`
- Siempre verificar RAR antes de borrar fuente
- El archivo RAR actual en este PC: `%USERPROFILE%\system_backup_05.rar`
- Contraseña actual guardada en: `Escritorio\BAGO_KEY.txt`
- WinRAR disponible en: `C:\Program Files\WinRAR\WinRAR.exe`
