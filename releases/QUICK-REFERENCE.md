# BAGO 4.8.2 - Quick Reference

## 🚀 Installation - Choose One Method

### Easiest: Double-Click EXE
```
bago-4.8.2-setup.exe  →  (double-click)  →  Installation starts
```
✓ Automatic admin elevation
✓ No configuration needed
✓ Full progress shown

### PowerShell Script
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1
```
✓ Scriptable with parameters
✓ Best for automation
✓ Full control

### Batch/Command Line
```cmd
install-bago-setup.cmd
```
✓ No PowerShell needed
✓ Works in batch scripts
✓ Legacy compatible

### Alternative VBS
```
install-bago-setup.vbs  →  (double-click)
```
✓ Alternative GUI launcher
✓ Works if PowerShell restricted

---

## 📋 What Each Installer File Does

| File | Purpose | Usage |
|------|---------|-------|
| **bago-4.8.2-setup.exe** | Main installer | Double-click |
| **Install-BAGO.ps1** | PowerShell installer | `powershell -File ...` |
| **install-bago-setup.cmd** | Batch wrapper | Run in cmd.exe |
| **install-bago-setup.vbs** | VBS launcher | Double-click |
| **Uninstall-BAGO.ps1** | Uninstaller | `powershell -File ...` |

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
- [ ] Internet connection (for downloads)

After installation:
- [ ] BAGO.exe appears in `%LOCALAPPDATA%\BAGO`
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
powershell -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1 `
  -InstallDir "C:\MyCustomPath\BAGO"
```

---

## ⚡ Quick Commands

### Run Installer (PowerShell)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1
```

### Run Installer (Batch)
```cmd
install-bago-setup.cmd
```

### Uninstall
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Uninstall-BAGO.ps1
```

### Verify Installation
```powershell
Test-Path "$env:LOCALAPPDATA\BAGO\electron-viewer\dist\win-unpacked\BAGO.exe"
```

### Launch BAGO
```powershell
& "$env:LOCALAPPDATA\BAGO\electron-viewer\dist\win-unpacked\BAGO.exe"
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
powershell -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1
```

### Prerequisites Missing
**Solution**: Install from official websites:
- Git: https://git-scm.com
- Node.js: https://nodejs.org (20+)
- Python: https://python.org (3.14+)

### Installation Too Slow
**Note**: This is normal. Installation takes 10-15 minutes.
- Cloning repo: ~30 seconds
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
├── .git/                      (Git repository)
├── backend/                   (Python backend)
├── electron-viewer/           (Electron app)
│   └── dist/win-unpacked/BAGO.exe
├── frontend/                  (React frontend)
├── node_modules/              (npm dependencies)
├── package.json
└── ...other files...
```

---

## 🎯 Your Next Steps

1. **Choose installation method**
   - Easiest: Double-click EXE
   - Most control: Run PowerShell script

2. **Run installer**
   - Takes 10-15 minutes
   - Don't close window during installation

3. **Launch BAGO**
   - From Start Menu
   - From Desktop shortcut
   - Or: Search for "BAGO" in Windows

4. **Enjoy BAGO 4.8.2!**

---

## 📞 Support

- **Issues**: https://github.com/MarcValls/BAGO/issues
- **Discussions**: https://github.com/MarcValls/BAGO/discussions

---

**Version**: BAGO 4.8.2 (August 7, 2026)

**Status**: ✓ Ready to Install

**All methods produce identical installations** — use whichever suits you.
