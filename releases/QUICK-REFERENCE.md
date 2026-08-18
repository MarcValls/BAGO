# BAGO 4.9.0 - Quick Reference

## 🚀 Installation - Choose One Method

### Easiest: Official NSIS EXE
```
BAGO-Installation-Manager-4.9.0-win-x64.exe  →  (double-click)  →  Installation starts
```
✓ Automatic admin elevation
✓ No configuration needed
✓ Full payload bundled

### Package-Driven PowerShell (Best for Automation)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 -PackageZip bago-v4.9.0.zip
```
✓ Fast, reproducible
✓ Scriptable with parameters
✓ Best for CI/CD

### Legacy PowerShell Script
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1
```
✓ Clones and builds from source
✓ Best for development

### Batch/Command Line
```cmd
install-bago-setup.cmd
```
✓ Legacy wrapper

### Alternative VBS
```
install-bago-setup.vbs  →  (double-click)
```
✓ Alternative GUI launcher

---

## 📋 What Each Installer File Does

| File | Purpose | Usage |
|------|---------|-------|
| **BAGO-Installation-Manager-4.9.0-win-x64.exe** | Official NSIS installer | Double-click |
| **bago-v4.9.0.zip** | Thin update package | Used by `install-v4.ps1` |
| **install-v4.ps1** | Package-driven installer | `powershell -File install-v4.ps1 -PackageZip bago-v4.9.0.zip` |
| **Install-BAGO.ps1** | Legacy source installer | `powershell -File Install-BAGO.ps1` |
| **install-bago-setup.cmd** | Batch wrapper | Run in cmd.exe |
| **install-bago-setup.vbs** | VBS launcher | Double-click |
| **Uninstall-BAGO.ps1** | Uninstaller | `powershell -File Uninstall-BAGO.ps1` |

---

## 📚 Documentation Files

| File | Read If | Purpose |
|------|---------|---------|
| **INSTALL.md** | You need quick start | 5-minute quick start guide |
| **README-INSTALLERS.md** | You want details | Complete installer guide |
| **INSTALLATION-METHODS.md** | You need to choose | Method comparison & scenarios |
| **DELIVERY.md** | You're distributing | Release summary & specs |

---

## ✅ Installation Checklist

Before installation:
- [ ] Have administrator access
- [ ] 2 GB free disk space
- [ ] Internet connection (for downloads, unless offline installer)

After installation:
- [ ] `BAGO.exe` appears in `%LOCALAPPDATA%\BAGO`
- [ ] Start Menu shortcut appears
- [ ] Desktop shortcut appears
- [ ] Can launch from Start Menu or desktop

---

## 🔧 Installation Paths

### Default Location
```
C:\Users\YourUsername\AppData\Local\BAGO
```

### Custom Location (PowerShell only)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 `
  -PackageZip bago-v4.9.0.zip -InstallDir "C:\MyCustomPath\BAGO"
```

---

## ⚡ Quick Commands

### Run Official Installer (PowerShell package-driven)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 -PackageZip bago-v4.9.0.zip
```

### Run Legacy Installer (PowerShell)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1
```

### Run Legacy Installer (Batch)
```cmd
install-bago-setup.cmd
```

### Uninstall
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Uninstall-BAGO.ps1
```

### Verify Installation
```powershell
Test-Path "$env:LOCALAPPDATA\BAGO\BAGO.exe"
```

### Launch BAGO
```powershell
& "$env:LOCALAPPDATA\BAGO\BAGO.exe"
```

### Check Prerequisites
```powershell
git --version
node --version
python --version
```

---

## 🐛 Troubleshooting

### Installation Won't Start
**Solution**: Right-click EXE → "Run as administrator"

### PowerShell Script Won't Run
**Solution**: Copy-paste the entire command exactly:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 -PackageZip bago-v4.9.0.zip
```

### Prerequisites Missing
**Solution**: Install from official websites:
- Git: https://git-scm.com
- Node.js: https://nodejs.org (20+)
- Python: https://python.org (3.14+)

### Installation Too Slow
**Note**: This is normal. Installation takes 5-10 minutes with the official installer, or 10-15 minutes from source.
- Extracting payload: ~30 seconds
- npm installs: ~15 seconds each
- Backend install: ~5 seconds
- Build process: ~2 seconds
- Electron packaging: ~15 seconds

### Port Already in Use
**Solution**: Close applications using ports 5000 or 3000

---

## 📦 What Gets Installed

```
%LOCALAPPDATA%\BAGO\
├── backend/                   (Python backend)
│   └── .bago/bin/bago.py      (runtime wrapper)
├── frontend/                  (React frontend)
├── BAGO.exe                   (Electron app)
├── node_modules/              (npm dependencies)
├── package.json
└── ...other files...
```

---

## 🎯 Your Next Steps

1. **Choose installation method**
   - Easiest: Double-click official EXE
   - Automation: `install-v4.ps1 -PackageZip bago-v4.9.0.zip`

2. **Run installer**
   - Takes 5-10 minutes
   - Don't close window during installation

3. **Launch BAGO**
   - From Start Menu
   - From Desktop shortcut
   - Or: Search for "BAGO" in Windows

4. **Enjoy BAGO 4.9.0!**

---

## 📞 Support

- **Issues**: https://github.com/MarcValls/BAGO/issues
- **Discussions**: https://github.com/MarcValls/BAGO/discussions

---

**Version**: BAGO 4.9.0 (August 18, 2026)

**Status**: ✓ Ready to Install

**Official and package-driven methods produce identical installations** — use whichever suits you.
