using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;

// Standalone experiment. No Boundary, Permit, adapter or product mutation calls.
static class Probe
{
    // Principal captured by the original unelevated preflight, before GUI launch.
    const string ExpectedSidHash="856ee9250c184495ebfdc662a39f558ea74876018ba3a682ca3f5cc3967bcfa6";
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    struct UI { public uint Size; public IntPtr Parent; public string Message; public string Caption; public IntPtr Banner; }
    [StructLayout(LayoutKind.Sequential)]
    struct Str { public ushort Length, Maximum; public IntPtr Buffer; }
    [StructLayout(LayoutKind.Sequential)]
    struct Interactive { public uint Type; public Str Domain, User, Password; }
    [StructLayout(LayoutKind.Sequential)]
    struct Luid { public uint Low; public int High; }
    [StructLayout(LayoutKind.Sequential)]
    struct Source { [MarshalAs(UnmanagedType.ByValArray, SizeConst=8)] public byte[] Name; public Luid Id; }
    [StructLayout(LayoutKind.Sequential)]
    struct Quota { public nuint Paged, NonPaged, Min, Max, Pagefile; public long Time; }
    [DllImport("credui.dll", CharSet=CharSet.Unicode)]
    static extern uint CredUIPromptForWindowsCredentialsW(ref UI ui, uint error, ref uint package, IntPtr input, uint inputSize, out IntPtr output, out uint outputSize, IntPtr save, uint flags);
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool CredIsProtectedW(IntPtr credentials, out uint protection);
    [DllImport("secur32.dll")] static extern int LsaConnectUntrusted(out IntPtr handle);
    [DllImport("secur32.dll")] static extern int LsaLookupAuthenticationPackage(IntPtr handle, ref Str name, out uint package);
    [DllImport("secur32.dll")] static extern int LsaLogonUser(IntPtr handle, ref Str origin, int type, uint package, IntPtr information, uint length, IntPtr groups, ref Source source, out IntPtr profile, out uint profileLength, out Luid id, out IntPtr token, out Quota quota, out int subStatus);
    [DllImport("secur32.dll")] static extern int LsaDeregisterLogonProcess(IntPtr handle);
    [DllImport("secur32.dll")] static extern int LsaFreeReturnBuffer(IntPtr buffer);
    [DllImport("advapi32.dll")] static extern uint LsaNtStatusToWinError(int status);
    [DllImport("advapi32.dll", SetLastError=true)] static extern bool AllocateLocallyUniqueId(out Luid id);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);

    static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
    static unsafe void Wipe(IntPtr p, uint length) { if (p != IntPtr.Zero) CryptographicOperations.ZeroMemory(new Span<byte>((void*)p, checked((int)length))); }
    static Str Ansi(string value, out IntPtr allocation) {
        allocation = Marshal.StringToHGlobalAnsi(value);
        return new Str { Length=(ushort)value.Length, Maximum=(ushort)(value.Length+1), Buffer=allocation };
    }
    // Credential Provider serialization has self-relative string offsets. Validate
    // every range before rebasing a private copy for LSA. Never unpack/decrypt.
    static Str Rebase(Str s, IntPtr blob, uint length) {
        long offset=s.Buffer.ToInt64();
        if (s.Length%2!=0 || s.Maximum%2!=0 || s.Maximum<s.Length || offset<Marshal.SizeOf<Interactive>() || offset%2!=0 || offset+s.Maximum>length)
            throw new InvalidOperationException("UNSUPPORTED_SERIALIZATION_RANGE");
        s.Buffer=IntPtr.Add(blob, checked((int)offset));
        return s;
    }
    static int Main(string[] args) {
        var report=new Dictionary<string, object?> {
            ["started_utc"]=DateTime.UtcNow.ToString("O"), ["os"]=Environment.OSVersion.VersionString,
            ["mutations_enabled"]=false, ["selected_provider_clsid_verified"]=false,
            ["rendering_verified"]=false, ["verifier_authenticated"]=false,
            ["credential_plaintext_unpacked"]=false, ["secure_prompt_flags"]="0x1010",
            ["expected_sid_hash"]=ExpectedSidHash,
            ["launch_sid_hash"]=Hash(Encoding.UTF8.GetBytes(WindowsIdentity.GetCurrent().User!.Value))
        };
        string root=Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "../../../../"));
        if (new DirectoryInfo(root).Name!="ieb-proof-20261001") return 90;
        string run=Path.Combine(root,"credui-"+Guid.NewGuid().ToString("N")); Directory.CreateDirectory(run);
        report["binary_sha256"]=Hash(File.ReadAllBytes(typeof(Probe).Assembly.Location));
        report["source_sha256"]=Hash(File.ReadAllBytes(Path.Combine(root,"CredUiProbe","Program.cs")));
        string descriptor="BAGO IEB: PRUEBA SIN CAMBIOS EN BAGO. Nonce "+Guid.NewGuid().ToString("N")+
            "\nPrincipal SID SHA256 "+report["expected_sid_hash"]+"; Negotiate; flags 0x1010";
        report["descriptor"]=descriptor; report["descriptor_sha256"]=Hash(Encoding.UTF8.GetBytes(descriptor));
        string display=descriptor+"\nSHA256 "+report["descriptor_sha256"]+"\nUn intento: Windows crea sesion de autenticacion; un fallo puede contar para bloqueo de cuenta.";
        report["display_text"]=display;
        IntPtr lsa=IntPtr.Zero, name=IntPtr.Zero, blob=IntPtr.Zero, copy=IntPtr.Zero, originMemory=IntPtr.Zero, token=IntPtr.Zero, profile=IntPtr.Zero, protectedString=IntPtr.Zero;
        uint blobSize=0, validatedBlobSize=0, copySize=0, protectedSize=0;
        try {
            if(!Equals(report["launch_sid_hash"],ExpectedSidHash)) {
                report["verdict"]="LAUNCH_PRINCIPAL_DRIFT_DENIED_BEFORE_PROMPT"; return 6;
            }
            int status=LsaConnectUntrusted(out lsa); report["lsa_connect_status"]=status;
            if(status!=0) throw new InvalidOperationException("LSA_CONNECT_FAILED");
            Str packageName=Ansi("Negotiate",out name);
            status=LsaLookupAuthenticationPackage(lsa,ref packageName,out uint package);
            report["package_lookup_status"]=status; report["requested_package"]=package;
            if(status!=0) throw new InvalidOperationException("PACKAGE_LOOKUP_FAILED");
            if(args.Length!=1 || args[0]!="--prompt") { report["verdict"]="PREFLIGHT_ONLY"; return 0; }
            uint expectedPackage=package;
            var ui=new UI {Size=(uint)Marshal.SizeOf<UI>(),Message=display,Caption="BAGO - verificacion experimental sin mutaciones"};
            uint result=CredUIPromptForWindowsCredentialsW(ref ui,0,ref package,IntPtr.Zero,0,out blob,out blobSize,IntPtr.Zero,0x1010);
            report["prompt_return"]=result; report["returned_package"]=package;
            if(result!=0) {report["verdict"]=result==1223?"CANCELLED":"PROMPT_FAILED"; return 2;}
            if(package!=expectedPackage) throw new InvalidOperationException("AUTH_PACKAGE_DRIFT_DENIED");
            if(blob==IntPtr.Zero || blobSize<Marshal.SizeOf<Interactive>() || blobSize>1024*1024) throw new InvalidOperationException("UNSUPPORTED_SERIALIZATION_SIZE_OR_POINTER");
            validatedBlobSize=blobSize;
            copySize=blobSize; copy=Marshal.AllocHGlobal((int)copySize);
            unsafe {new ReadOnlySpan<byte>((void*)blob,(int)blobSize).CopyTo(new Span<byte>((void*)copy,(int)copySize));}
            var logon=Marshal.PtrToStructure<Interactive>(copy);
            report["serialization_type"]=logon.Type;
            if(logon.Type!=2 && logon.Type!=7) throw new InvalidOperationException("UNSUPPORTED_SERIALIZATION_TYPE");
            logon.Domain=Rebase(logon.Domain,copy,copySize); logon.User=Rebase(logon.User,copy,copySize); logon.Password=Rebase(logon.Password,copy,copySize);
            string domain=Marshal.PtrToStringUni(logon.Domain.Buffer,logon.Domain.Length/2)!;
            // Local account only: do not ask LSA to contact a remote domain.
            if(!domain.Equals(Environment.MachineName,StringComparison.OrdinalIgnoreCase) && domain!=".") throw new InvalidOperationException("NON_LOCAL_DOMAIN_DENIED");
            // UNICODE_STRING need not include a terminator. Copy protected bytes
            // into an explicitly terminated unmanaged buffer for CredIsProtected.
            protectedSize=(uint)logon.Password.Length+2;
            protectedString=Marshal.AllocHGlobal((int)protectedSize); Wipe(protectedString,protectedSize);
            unsafe { new ReadOnlySpan<byte>((void*)logon.Password.Buffer,logon.Password.Length).CopyTo(new Span<byte>((void*)protectedString,(int)protectedSize)); }
            bool isProtected=CredIsProtectedW(protectedString,out uint protection);
            report["protection_query_ok"]=isProtected; report["protection_type"]=protection;
            if(!isProtected || protection==0) throw new InvalidOperationException("UNPROTECTED_CREDENTIAL_DENIED");
            logon.Type=2; Marshal.StructureToPtr(logon,copy,false);
            Str origin=Ansi("BAGOIEB",out originMemory);
            var source=new Source {Name=Encoding.ASCII.GetBytes("BAGOIEB\0")};
            if(!AllocateLocallyUniqueId(out source.Id)) throw new InvalidOperationException("LUID_FAILED");
            status=LsaLogonUser(lsa,ref origin,2,package,copy,copySize,IntPtr.Zero,ref source,out profile,out _,out _,out token,out _,out int sub);
            report["logon_status"]=status; report["logon_substatus"]=sub; report["logon_winerror"]=LsaNtStatusToWinError(status);
            if(status!=0 || token==IntPtr.Zero) {report["verdict"]="VERIFIER_REJECTED"; return 3;}
            using var identity=new WindowsIdentity(token);
            bool same=Hash(Encoding.UTF8.GetBytes(identity.User!.Value))==ExpectedSidHash;
            report["verified_sid_hash"]=Hash(Encoding.UTF8.GetBytes(identity.User!.Value)); report["same_sid"]=same;
            report["verifier_authenticated"]=same;
            report["verdict"]=same?"VERIFIER_PASS_PROVIDER_AND_RENDERING_OPEN":"WRONG_IDENTITY_DENIED";
            return same?0:4;
        }
        catch(Exception e) { report["failure_type"]=e.GetType().Name;
            if(e is InvalidOperationException) report["failure_gate"]=e.Message;
            report["verdict"]="UNSUPPORTED_OR_FAILED"; return 5; }
        finally {
            if(profile!=IntPtr.Zero) LsaFreeReturnBuffer(profile);
            if(token!=IntPtr.Zero) CloseHandle(token);
            Wipe(protectedString,protectedSize); if(protectedString!=IntPtr.Zero) Marshal.FreeHGlobal(protectedString);
            Wipe(copy,copySize); if(copy!=IntPtr.Zero) Marshal.FreeHGlobal(copy);
            Wipe(blob,validatedBlobSize); if(blob!=IntPtr.Zero) Marshal.FreeCoTaskMem(blob);
            if(originMemory!=IntPtr.Zero) Marshal.FreeHGlobal(originMemory);
            if(name!=IntPtr.Zero) Marshal.FreeHGlobal(name);
            if(lsa!=IntPtr.Zero) LsaDeregisterLogonProcess(lsa);
            report["finished_utc"]=DateTime.UtcNow.ToString("O");
            File.WriteAllText(Path.Combine(run,"observations.json"),JsonSerializer.Serialize(report,new JsonSerializerOptions{WriteIndented=true})+"\n");
            Console.WriteLine(run);
        }
    }
}
