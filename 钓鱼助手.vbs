Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.Run ".venv\Scripts\pythonw.exe fishing.pyw", 0, False

