Dim folder
folder = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

Dim WShell
Set WShell = CreateObject("WScript.Shell")
WShell.Run """" & folder & "\.venv\Scripts\pythonw.exe"" """ & folder & "\launcher.py""", 0, False
