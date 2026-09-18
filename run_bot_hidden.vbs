Set fso = CreateObject("Scripting.FileSystemObject")
Dim scriptDir
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WShell = CreateObject("WScript.Shell")
WShell.Run """" & scriptDir & "\run_bot.bat""", 0, False
