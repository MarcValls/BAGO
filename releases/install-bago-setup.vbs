' BAGO 4.8.2 Installer Launcher VBScript
' This launches the batch wrapper as a proper installer GUI application
' No console window flashing - clean user experience

Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")

' Get the directory where this script is located
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Path to the batch wrapper
batchFile = objFSO.BuildPath(scriptDir, "install-bago-setup.cmd")

' Verify batch file exists
If Not objFSO.FileExists(batchFile) Then
    objShell.Popup "ERROR: install-bago-setup.cmd not found!" & vbCrLf & vbCrLf & _
                   "Expected location: " & batchFile, 0, "BAGO Installer - Error", 48
    WScript.Quit 1
End If

' Launch the batch file with admin rights (UAC prompt)
On Error Resume Next
objShell.Run """" & batchFile & """", 1, True
errorCode = Err.Number

If errorCode <> 0 Then
    objShell.Popup "Installation failed or was cancelled." & vbCrLf & vbCrLf & _
                   "Error Code: " & errorCode, 0, "BAGO Installer - Result", 64
    WScript.Quit 1
Else
    objShell.Popup "Installation completed successfully!" & vbCrLf & vbCrLf & _
                   "BAGO 4.8.2 is ready to use." & vbCrLf & _
                   "You can launch it from the Start Menu.", 0, "BAGO Installer - Success", 64
    WScript.Quit 0
End If
