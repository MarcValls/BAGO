# BAGO third-party notices for the MSIX bootstrap

This file is shipped with the BAGO bootstrap candidate. It identifies the
third-party components present in the package and points to the license text
that must remain with the distribution.

## CPython 3.14.7 embedded runtime

- Component: CPython 3.14.7, Windows x64 embeddable distribution.
- Source archive SHA-256: `d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15`.
- License text: `third_party_notices/python-3.14.7-LICENSE.txt`.
- Upstream: <https://www.python.org/psf/license/>.

## Python.NET 3.1.0

- Component: `Python.Runtime.dll` from NuGet `pythonnet` 3.1.0.
- License text: `third_party_notices/pythonnet-3.1.0-LICENSE.txt`.
- License: MIT.
- NuGet: <https://www.nuget.org/packages/pythonnet/3.1.0>.

## Microsoft Windows SDK for .NET

- Components: `Microsoft.Windows.SDK.NET.dll` and the Windows SDK reference
  assemblies used by the bootstrap host.
- Package: `Microsoft.Windows.SDK.NET.Ref` 10.0.19041.57.
- License and terms: <https://aka.ms/WinSDKLicenseURL>.
- The Microsoft copyright and license terms supplied by the SDK remain
  applicable to the redistributable binaries.

## C#/WinRT runtime

- Component: `WinRT.Runtime.dll`, C#/WinRT 2.2.0.48161.
- Publisher: Microsoft Corporation.
- Project and license information: <https://github.com/microsoft/CSharpWinRT>.
- The upstream copyright and license notices remain applicable.

## BAGO dependency inventory

The complete direct dependency and license review is recorded in
`docs/licensing/signpath-license-inventory-2026-10-03.md`. The MSIX payload
must retain this file and the license texts in `third_party_notices/`.
