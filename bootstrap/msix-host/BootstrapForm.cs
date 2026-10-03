namespace Bago.Bootstrap.Host;

internal sealed class BootstrapForm : Form
{
    private readonly Label _status;
    private readonly Button _install;

    internal BootstrapForm(BootstrapPolicy policy, string packageRoot, Func<string> install)
    {
        FormClosing += (_, e) => BootstrapLogger.Write("form_closing", $"reason={e.CloseReason} cancel={e.Cancel}");
        FormClosed += (_, e) => BootstrapLogger.Write("form_closed", $"reason={e.CloseReason}");
        Text = "BAGO Bootstrap";
        Width = 680;
        Height = 330;
        StartPosition = FormStartPosition.CenterScreen;
        var message = new Label
        {
            Dock = DockStyle.Top,
            Height = 175,
            Padding = new Padding(24),
            TextAlign = ContentAlignment.MiddleLeft,
            Text = $"BAGO seed host has loaded the packaged authority in-process.\r\n\r\nPublisher: {policy.Publisher}\r\nRelease manifest: {policy.ReleaseManifestSha256}\r\n\r\nThe install action is bound to the same AuthorizationBoundary and ExecutionGateway.",
        };
        _status = new Label { Dock = DockStyle.Top, Height = 42, Padding = new Padding(24, 4, 24, 4), Text = "Listo para iniciar la instalación autorizada." };
        _install = new Button { Text = "Instalar BAGO", Dock = DockStyle.Top, Height = 48, Enabled = true };
        _install.Click += (_, _) =>
        {
            _install.Enabled = false;
            _status.Text = "Esperando confirmación nativa y ejecutando el helper autorizado...";
            try
            {
                var receipt = install();
                _status.Text = $"Instalación completada. Receipt: {receipt}";
            }
            catch (Exception ex)
            {
                _status.Text = $"Instalación rechazada o fallida: {ex.Message}";
                BootstrapLogger.Write("install_error", ex.Message, ex);
                _install.Enabled = true;
            }
        };
        Controls.Add(_install);
        Controls.Add(_status);
        Controls.Add(message);
    }
}
