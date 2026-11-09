#ifndef BuildDir
  #define BuildDir "..\dist\PyPilot"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist\installer"
#endif
[Setup]
AppId={{7C5D7AF6-1DB7-4B1C-BB98-69B1DD21A7F2}
AppName=PyPilot
AppVersion=0.1.0
AppPublisher=PyPilot contributors
DefaultDirName={localappdata}\Programs\PyPilot
DefaultGroupName=PyPilot
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutputDir}
OutputBaseFilename=PyPilot-Setup-0.1.0
SetupIconFile=..\assets\pypilot.ico
UninstallDisplayIcon={app}\PyPilot.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\PyPilot"; Filename: "{app}\PyPilot.exe"
Name: "{autodesktop}\PyPilot"; Filename: "{app}\PyPilot.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\PyPilot.exe"; Description: "Launch PyPilot"; Flags: nowait postinstall skipifsilent
