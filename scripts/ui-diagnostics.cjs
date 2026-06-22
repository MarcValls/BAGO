const { app } = require('electron');
const path = require('path');

const ROOT_DIR = path.join(__dirname, '..');
const { createManagerWindow } = require(path.join(ROOT_DIR, 'electron', 'window-service.cjs'));
const { REACT_HTML } = require(path.join(ROOT_DIR, 'electron', 'environment.cjs'));

// Capture all renderer console messages and main-process errors
const diagnostics = {
  react_html: REACT_HTML,
  console: [],
  uncaughtExceptions: [],
  unhandledRejections: [],
  didFailLoads: [],
};

process.on('uncaughtException', (err) => {
  diagnostics.uncaughtExceptions.push({ message: err.message, stack: err.stack });
  console.error(JSON.stringify({ main_uncaught_exception: err.message }));
});

process.on('unhandledRejection', (reason) => {
  const msg = reason instanceof Error ? reason.message : String(reason);
  diagnostics.unhandledRejections.push(msg);
  console.error(JSON.stringify({ main_unhandled_rejection: msg }));
});

app.whenReady().then(() => {
  const win = createManagerWindow();

  win.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    const entry = { level, message, line, sourceId };
    diagnostics.console.push(entry);
    const levelName = ['debug', 'log', 'warn', 'error'][level] || level;
    console.error(JSON.stringify({ renderer_console: levelName, message, source: sourceId, line }));
  });

  win.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    const entry = { errorCode, errorDescription, validatedURL };
    diagnostics.didFailLoads.push(entry);
    console.error(JSON.stringify({ did_fail_load: entry }));
  });

  // Give the UI time to settle, then dump diagnostics and exit
  setTimeout(() => {
    console.log(JSON.stringify({ diagnostics_complete: true, diagnostics }, null, 2));
    app.exit(diagnostics.uncaughtExceptions.length || diagnostics.didFailLoads.length ? 1 : 0);
  }, 10000);
});

app.on('window-all-closed', () => app.quit());
