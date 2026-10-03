using Bago.Bootstrap.Host;

if (args.Length != 1) return 2;
Console.WriteLine(BootstrapPolicy.HashPackageTree(args[0]));
return 0;
