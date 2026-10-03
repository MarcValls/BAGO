using System.Runtime.InteropServices;
using Python.Runtime;

namespace Bago.Bootstrap.Host;

internal static class BootstrapLogger
{
    private static readonly string LogDirectory = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAGO", "logs");

    private static readonly string LogPath = Path.Combine(LogDirectory, "bootstrap-host.log");

    private static readonly object Lock = new();

    internal static void Write(string phase, string? message = null, Exception? ex = null)
    {
        try
        {
            Directory.CreateDirectory(LogDirectory);
            var line = $"{DateTime.UtcNow:O}\t{Environment.ProcessId}\t{phase}\t{message ?? ""}";
            if (ex is not null)
            {
                line += $"\nEXCEPTION: {ex.GetType().FullName}\n{ex}";
            }
            lock (Lock)
            {
                File.AppendAllText(LogPath, line + Environment.NewLine);
            }
        }
        catch
        {
            // Logging is best-effort; never block bootstrap authority on log failure.
        }
    }
}

internal static class Program
{
    [STAThread]
    private static int Main()
    {
        var args = Environment.GetCommandLineArgs();
        BootstrapLogger.Write("host_start", $"args={string.Join(' ', args)}");
        if (args.Length == 4 && args[1] == "--hash-package-tree")
        {
            BootstrapLogger.Write("hash_package_tree", $"root={args[2]} out={args[3]}");
            try
            {
                File.WriteAllText(args[3], BootstrapPolicy.HashPackageTree(args[2]));
                BootstrapLogger.Write("hash_package_tree_done");
                return 0;
            }
            catch (Exception ex)
            {
                BootstrapLogger.Write("hash_package_tree_error", ex.Message, ex);
                return 1;
            }
        }
        ApplicationConfiguration.Initialize();
        try
        {
            var packageRoot = PackageIdentity.RequirePackageRoot();
            BootstrapLogger.Write("package_identity", $"root={packageRoot}");

            var authorityRoot = Path.Combine(packageRoot, "authority");
            var pythonRoot = Path.Combine(packageRoot, "python");
            var payloadRoot = Path.Combine(packageRoot, "payload");
            var policyPath = Path.Combine(packageRoot, "bootstrap-policy.json");
            BootstrapLogger.Write("policy_load_start", $"path={policyPath}");
            var policy = BootstrapPolicy.LoadAndVerify(policyPath, authorityRoot, payloadRoot,
                Path.Combine(packageRoot, "release-manifest.json"), packageRoot);
            BootstrapLogger.Write("policy_load_done", $"publisher={policy.Publisher} version={policy.Version} manifest={policy.ReleaseManifestSha256}");

            Environment.SetEnvironmentVariable("BAGO_SESSION_MIRROR", "0");
            Environment.SetEnvironmentVariable("PYTHONHOME", pythonRoot);
            Environment.SetEnvironmentVariable("PYTHONPATH", null);
            Environment.SetEnvironmentVariable("PYTHONNET_PYDLL", null);
            Environment.SetEnvironmentVariable("PYTHONNOUSERSITE", "1");
            Environment.SetEnvironmentVariable("PYTHONDONTWRITEBYTECODE", "1");
            BootstrapLogger.Write("python_env", $"home={pythonRoot}");

            Runtime.PythonDLL = Path.Combine(pythonRoot, "python314.dll");
            PythonEngine.PythonHome = pythonRoot;
            PythonEngine.PythonPath = string.Join(Path.PathSeparator, new[]
            {
                Path.Combine(pythonRoot, "python314.zip"),
                Path.Combine(pythonRoot, "DLLs"),
                pythonRoot,
                authorityRoot,
                Path.Combine(authorityRoot, "core"),
                Path.Combine(authorityRoot, "api"),
            });
            BootstrapLogger.Write("pythonnet_init_start");
            PythonEngine.Initialize();
            BootstrapLogger.Write("pythonnet_init_done");
            dynamic authority;
            using (Py.GIL())
            {
                BootstrapLogger.Write("python_gil_acquired");
                dynamic sys = Py.Import("sys");
                sys.dont_write_bytecode = true;
                BootstrapLogger.Write("authority_verify_start", $"root={authorityRoot}");
                authority = Py.Import("msix_bootstrap");
                authority.verify_loaded_authority(authorityRoot, policy.ReleaseManifestSha256);
                BootstrapLogger.Write("authority_verify_done");
                BootstrapLogger.Write("session_create_start");
                var sessionId = authority.create_bootstrap_session(
                    Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAGO-bootstrap-state"));
                BootstrapLogger.Write("session_create_done", $"session_id={sessionId}");
            }

            BootstrapLogger.Write("form_run_start");
            Application.Run(new BootstrapForm(policy, packageRoot, () =>
            {
                using (Py.GIL())
                {
                    return (string)authority.install_from_package(packageRoot, policy.Publisher, policy.PackagePayloadSha256);
                }
            }));
            BootstrapLogger.Write("form_run_done");
            return 0;
        }
        catch (Exception ex)
        {
            BootstrapLogger.Write("host_fatal", $"message={ex.Message}", ex);
            MessageBox.Show(ex.Message, "BAGO Bootstrap", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        finally
        {
            BootstrapLogger.Write("shutdown", $"python_initialized={PythonEngine.IsInitialized}");
            if (PythonEngine.IsInitialized) PythonEngine.Shutdown();
            BootstrapLogger.Write("shutdown_done");
        }
    }
}

internal static class PackageIdentity
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern int GetCurrentPackagePath(ref uint length, char[]? path);

    internal static string RequirePackageRoot()
    {
        uint length = 0;
        _ = GetCurrentPackagePath(ref length, null);
        if (length == 0) throw new InvalidOperationException("BAGO Bootstrap must run from its MSIX package identity.");
        var buffer = new char[length];
        var result = GetCurrentPackagePath(ref length, buffer);
        if (result != 0) throw new InvalidOperationException($"Windows package identity lookup failed ({result}).");
        return new string(buffer, 0, checked((int)length)).TrimEnd('\0');
    }
}

public sealed record BootstrapPolicy(string Publisher, string PackageName, string Version, string ReleaseManifestSha256, string PackagePayloadSha256)
{
    internal static BootstrapPolicy LoadAndVerify(string path, string authorityRoot, string payloadRoot, string manifestPath, string packageRoot)
    {
        var policy = System.Text.Json.JsonSerializer.Deserialize<BootstrapPolicy>(File.ReadAllText(path))
            ?? throw new InvalidDataException("Bootstrap policy is empty.");
        foreach (var digest in new[] { policy.ReleaseManifestSha256 })
            if (digest.Length != 64 || digest.Any(c => !Uri.IsHexDigit(c)))
                throw new InvalidDataException("Release manifest identity must be SHA-256.");
        if (!File.Exists(Path.Combine(authorityRoot, "core", "msix_bootstrap.py")) || !Directory.Exists(payloadRoot))
            throw new InvalidDataException("Authenticated authority or release payload is missing.");
        var actualManifest = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(manifestPath))).ToLowerInvariant();
        if (!StringComparer.OrdinalIgnoreCase.Equals(actualManifest, policy.ReleaseManifestSha256))
            throw new InvalidDataException("Authenticated release manifest identity mismatch.");
        using var manifest = System.Text.Json.JsonDocument.Parse(File.ReadAllBytes(manifestPath));
        if (!StringComparer.OrdinalIgnoreCase.Equals(manifest.RootElement.GetProperty("package_payload_sha256").GetString(), policy.PackagePayloadSha256) ||
            !StringComparer.OrdinalIgnoreCase.Equals(HashPackageTree(packageRoot), policy.PackagePayloadSha256))
            throw new InvalidDataException("Packaged authority or payload changed after manifest creation.");
        var appx = System.Xml.Linq.XDocument.Load(Path.Combine(packageRoot, "AppxManifest.xml"));
        System.Xml.Linq.XNamespace ns = "http://schemas.microsoft.com/appx/manifest/foundation/windows10";
        var identity = appx.Root?.Element(ns + "Identity") ?? throw new InvalidDataException("Package identity missing.");
        if (identity.Attribute("Name")?.Value != policy.PackageName || identity.Attribute("Publisher")?.Value != policy.Publisher || identity.Attribute("Version")?.Value != policy.Version)
            throw new InvalidDataException("Package identity differs from its bound policy.");
        if (Environment.OSVersion.Version.Build < 19041)
            throw new PlatformNotSupportedException("BAGO MSIX Package Integrity requires Windows build 19041 or later.");
        return policy;
    }

    public static string HashPackageTree(string root)
    {
        using var hash = System.Security.Cryptography.IncrementalHash.CreateHash(System.Security.Cryptography.HashAlgorithmName.SHA256);
        foreach (var file in Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories)
                     .Where(p => !IsPackageMetadata(Path.GetRelativePath(root, p).Replace('\\', '/')))
                     .OrderBy(p => Path.GetRelativePath(root, p).Replace('\\', '/'), StringComparer.Ordinal))
        {
            var relative = Path.GetRelativePath(root, file).Replace('\\', '/');
            var name = System.Text.Encoding.UTF8.GetBytes(relative);
            hash.AppendData(BitConverter.GetBytes(System.Net.IPAddress.HostToNetworkOrder(name.Length)));
            hash.AppendData(name);
            var bytes = File.ReadAllBytes(file);
            hash.AppendData(BitConverter.GetBytes(System.Net.IPAddress.HostToNetworkOrder(bytes.Length)));
            hash.AppendData(System.Security.Cryptography.SHA256.HashData(bytes));
        }
        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }

    private static bool IsPackageMetadata(string relativePath) =>
        relativePath is "release-manifest.json" or "bootstrap-policy.json" or "AppxBlockMap.xml" or "AppxSignature.p7x" or "AppxMetadata/CodeIntegrity.cat";
}
