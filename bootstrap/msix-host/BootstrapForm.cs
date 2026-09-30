namespace Bago.Bootstrap.Host;

internal sealed class BootstrapForm : Form
{
    internal BootstrapForm(BootstrapPolicy policy)
    {
        Text = "BAGO Bootstrap";
        Width = 560;
        Height = 250;
        StartPosition = FormStartPosition.CenterScreen;
        Controls.Add(new Label
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(24),
            TextAlign = ContentAlignment.MiddleLeft,
            Text = $"BAGO seed host is running with the packaged authority loaded in-process.\r\n\r\nPublisher: {policy.Publisher}\r\nRelease manifest: {policy.ReleaseManifestSha256}\r\n\r\nInstallation is disabled until package-bound native approval and authenticated helper handoff are implemented.",
        });
    }
}
