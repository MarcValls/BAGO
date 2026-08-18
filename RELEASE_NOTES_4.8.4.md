# BAGO 4.8.4 - Release Notes

**Release Date:** 2026-08-10  
**Version:** 4.8.4  
**Status:** ✅ Production Ready

## Installation

### Quick Start

1. Download `bago-4.8.4-distribution.zip` from [GitHub Releases](https://github.com/MarcValls/BAGO/releases/tag/v4.8.4)
2. Download `Install-BAGO-4.8.4.ps1` from this repository
3. Extract the ZIP and place it in the same directory as the installer script
4. Run PowerShell as Administrator:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
   .\Install-BAGO-4.8.4.ps1
   ```

### Installation Package Contents

- **bago-4.8.4-distribution.zip** (Distribution Package)
  - BAGO.exe (Electron application with runtime)
  - Backend services and dependencies
  - Frontend assets
  - SHA256: `1d2caf21dc6a5b8eeb182d1e29808e2fc2a08956dfb9468dc6c5c75333247808`

### System Requirements

- **OS:** Windows 10 / Windows 11 (x64)
- **Disk Space:** ~600 MB (full installation)
- **RAM:** 4 GB minimum / 8 GB recommended
- **Internet:** Required for initial GitHub integration setup

## What's New in 4.8.4

### Stability Improvements
- Enhanced MCP (Model Context Protocol) integration
- Improved error handling for network disconnections
- Better resource cleanup on application exit

### Features
- Full GitHub integration with repository cloning
- Reasoning depth control (Normal, Medium, High, Maximum)
- Terminal integration for direct command execution
- Workspace-based development environment

### Components

| Component | Version | Status |
|-----------|---------|--------|
| Frontend (Electron) | 4.8.4 | ✅ Stable |
| Backend Services | 4.8.4 | ✅ Stable |
| MCP Integration | 4.8.4 | ✅ Stable |

## Upgrading from Previous Versions

If you have BAGO 4.8.2 or 4.8.3 installed:

1. Close BAGO completely
2. Run the new installer `Install-BAGO-4.8.4.ps1`
3. The installer will upgrade your installation to 4.8.4
4. Existing configurations and workspace data are preserved

## Known Issues

None reported at this time.

## Security

- All MCP operations require explicit confirmation for write operations
- GitHub authentication uses OAuth 2.0 via `gh` CLI
- No credentials stored in plaintext
- All network communication is encrypted (HTTPS)

## Support

For issues or questions:
1. Check [GitHub Issues](https://github.com/MarcValls/BAGO/issues)
2. Review [Installation Guide](./INSTALLER-DELIVERY.md)
3. Check troubleshooting section below

## Troubleshooting

### Installation Issues

**Problem:** "SmartScreen protected your PC"
- **Solution:** Click "More info" → "Run anyway"
- Note: This is normal for unsigned installers on first run

**Problem:** PowerShell execution policy error
- **Solution:** Run as Administrator and execute:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
  ```

**Problem:** ZIP extraction fails
- **Solution:** Ensure sufficient disk space and the ZIP is not corrupted
- Verify SHA256: `1d2caf21dc6a5b8eeb182d1e29808e2fc2a08956dfb9468dc6c5c75333247808`

### Runtime Issues

**Problem:** BAGO won't start after installation
- **Solution:** 
  1. Verify `.NET Framework 4.8` or higher is installed
  2. Check Windows Defender or antivirus isn't blocking the process
  3. Try reinstalling from fresh download

**Problem:** GitHub integration not working
- **Solution:**
  1. Ensure `gh` CLI is installed and configured
  2. Run `gh auth login` in terminal
  3. Restart BAGO after authentication

## Changelog

### Version History

- **4.8.4** (Current) - Stability release
- **4.8.3** - MCP integration improvements
- **4.8.2** - Initial distribution build
- **4.8.1** - Beta releases
- **4.8.0** - Initial release

## Archive SHA256

For verification:
```
1d2caf21dc6a5b8eeb182d1e29808e2fc2a08956dfb9468dc6c5c75333247808  bago-4.8.4-distribution.zip
```

Verify your download:
```powershell
(Get-FileHash -Path "bago-4.8.4-distribution.zip" -Algorithm SHA256).Hash
```

---

**Next Release:** TBD  
**Support:** [GitHub Issues](https://github.com/MarcValls/BAGO/issues)
