; Aeon Application — Windows installer (Inno Setup)
;
; Produces AeonApplicationSetup-<version>.exe from the PyInstaller
; bundle at dist/aeon-launcher/. Run from the repo root:
;     iscc packaging/windows/aeon-installer.iss
;
; This installer is UNSIGNED by default. When a signing environment
; is available, sign the produced setup .exe out-of-band using
; SignTool or a comparable tool; see L16-WINDOWS-PACKAGING-REPORT.md.

#define AppName "Aeon Application"
#define AppVersion "0.1.0"
#define AppPublisher "Aeon"
#define AppExeName "aeon-launcher.exe"
; PyInstaller runs from aeon-application/ (see aeon-launcher.spec
; header + aeon-windows workflow). AppSourceDir is resolved relative
; to this .iss file at aeon-application/packaging/windows/.
#define AppSourceDir "..\..\dist\aeon-launcher"

[Setup]
AppId={{4A0E4B2B-4A69-4A18-9C9C-AEON-0-1-0}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Aeon
DefaultGroupName=Aeon
OutputBaseFilename=AeonApplicationSetup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#AppExeName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
CloseApplicationsFilter=*.exe,*.dll

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#AppSourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Verify installation (certified smoke)"; Parameters: "--smoke"; Flags: postinstall skipifsilent runhidden

; User data policy: the installer does NOT touch %LOCALAPPDATA%\Aeon.
; Uninstall does NOT remove user data by default. See L16 report.
