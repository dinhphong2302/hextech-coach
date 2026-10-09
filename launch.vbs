' Khởi động JC Coaching không kèm cửa sổ console.
' Dùng wscript.exe vì shortcut không gọi trực tiếp được python.exe của Microsoft Store.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = appDir

' Tìm pythonw: bản Microsoft Store, bản cài thường, rồi mới tới PATH
candidates = Array( _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe"), _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\python.exe"), _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python312\python.exe"))

pyw = ""
For Each c In candidates
  If pyw = "" And fso.FileExists(c) Then pyw = c
Next
If pyw = "" Then pyw = "python.exe"

sh.Run """" & pyw & """ main.py watch", 0, False
