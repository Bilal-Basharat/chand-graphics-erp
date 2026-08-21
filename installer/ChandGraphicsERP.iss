; Chand Graphics ERP — production installer.
;
; Packages the verified PyInstaller onedir build in dist\ChandGraphicsERP
; and nothing else. Build it first, then:
;
;     pyinstaller --clean --noconfirm chand_graphics_erp.spec
;     ISCC.exe installer\ChandGraphicsERP.iss
;
; The one rule this script exists to keep: the application folder holds
; only what the vendor ships, and everything the customer owns —
; database, licence, configuration, logs — lives under
; %LOCALAPPDATA%\ChandGraphicsERP, is created by the application itself
; on first run, and is never touched here. Installing writes none of it;
; uninstalling removes none of it. A shop that uninstalls and reinstalls
; finds its trading exactly where it left it, still licensed.

#define AppName "Chand Graphics ERP"
; Keep in step with APP_VERSION in app\config\constants.py. They are two
; separate declarations of the same release; if they disagree, the
; version a customer sees in Add/Remove Programs is not the version the
; application reports about itself.
#define AppVersion "1.0.3"
#define AppPublisher "Alvi-Systems"
#define AppExeName "ChandGraphicsERP.exe"
#define AppSourceDir "..\dist\ChandGraphicsERP"

[Setup]
; Fixed for the lifetime of the product. This is what tells Windows that
; version 1.0.3 is an upgrade of 1.0.3 rather than a second application:
; change it and every customer ends up with two entries in Add/Remove
; Programs and two copies on disk. Never regenerate it.
AppId={{7C1F4A6E-2B93-4D58-9E0A-5F6C3D82B14E}

AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppContact={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
; One program group, so there is nothing worth asking the user about.
DisableProgramGroupPage=yes

UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}

OutputDir=..\release
OutputBaseFilename=ChandGraphicsERP-Setup-{#AppVersion}

; 64-bit only: the build embeds a 64-bit Python and 64-bit Qt, so there
; is nothing for a 32-bit Windows to run. Installing in 64-bit mode is
; what puts it in Program Files rather than Program Files (x86).
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

; Program Files is not writable by a standard user, which is exactly why
; the application keeps the customer's data elsewhere.
PrivilegesRequired=admin

; Solid compression pays off here: ~150 MB of Qt DLLs and Python modules
; that compress far better as one stream than as 219 separate ones.
Compression=lzma2/max
SolidCompression=yes

WizardStyle=modern
; Shut the application down cleanly before overwriting it, rather than
; asking for a reboot afterwards.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole build folder, and only the build folder. The Excludes are a
; backstop rather than a plan — a correct build contains none of these —
; so that a developer's stray .env or a test database sitting in dist\
; can never reach a customer's machine.
Source: "{#AppSourceDir}\*"; DestDir: "{app}"; \
    Excludes: ".env,*.env,*.db,*.sqlite3,*.backup,*.log,*.pem,*.key,*.lic,license.json,installation.json,session.json,sign_in.json,settings.json"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only the folder this installer created, and only if the application
; left nothing behind in it. There is deliberately no entry for
; {localappdata}\ChandGraphicsERP: the database, the activated licence,
; the configuration and the logs are the customer's, and an uninstall —
; including the one an upgrade performs — must not take them.
Type: dirifempty; Name: "{app}"
