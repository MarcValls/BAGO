# BAGO 4.5.0 - Manager v1 + Landing Fullscreen

### Changes
- Manager v1: new "System Status" tab with:
  - BAGO supervisor monitor (start / stop / restart)
  - zombie connection cleanup (TIME_WAIT / CloseWait / FinWait2)
  - Manager health panel (probes for 5 critical services)
- Landing page: hero fills the screen on every device (centered flex layout)
- Distribution: direct Manager Installer download from GitHub Releases

### Assets
- BAGO-Installation-Manager-4.5.0-win-x64.exe - Manager installer (Electron)
- bago-v4.5.0.zip - v4 source bundle
- bago-v4.5.0.zip.sha256 - SHA256 checksum

### Quick install
1. Download the Manager .exe
2. Run the installer
3. The Manager detects whether BAGO is installed and offers install / repair / update
4. Open the "System" tab to manage the supervisor and clean zombie connections

### Notes
- This release uses ASCII only to avoid rendering issues.
- The remote installer stays pinned to tag v4.5.0.
