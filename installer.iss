; Windows installer for Chand Graphics ERP.
;
; Wraps the PyInstaller onedir build in dist\ChandGraphicsERP\ as a single
; setup.exe that installs to Program Files, adds Start Menu and desktop
; shortcuts, and registers an uninstaller.
;
; Run PyInstaller first, then compile this. The .env is bundled into the
; build by PyInstaller's --add-data, so nothing needs copying alongside
; and no plaintext configuration is left sitting in Program Files.

#define AppName        "Chand Graphics ERP"
#define AppVersion     "1.0.1"
#define AppPublisher   "Alvi-Systems"
#define AppExeName     "ChandGraphicsERP.exe"
#define SourceDir      "dist\ChandGraphicsERP"

[Setup]
; Never change AppId. It is how Windows recognises a later release as an
; upgrade of this program rather than a second copy of it.
AppId={{B3F1C2A4-7E58-4D9A-9C31-2A6E5D8F1B04}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; Program Files is not writable by a standard user, so installing needs
; elevation. The database deliberately lives in %LOCALAPPDATA% instead,
; which is why the app itself never needs it.
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
MinVersion=10.0

OutputDir=installer
OutputBaseFilename=ChandGraphicsERP-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; WorkingDir is good practice rather than load-bearing: the app resolves
; its own .env from inside the bundle (settings._resolve_env_file), so it
; no longer depends on where it was started from.
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Description: "Start {#AppName}"; \
    Flags: nowait postinstall skipifsilent

; No [UninstallDelete] section on purpose. Inno already removes everything
; it installed, and the customer's database lives in
; %LOCALAPPDATA%\ChandGraphicsERP, which must survive an uninstall — their
; trading records are not ours to delete.
