; Inno Setup Script for RetroSprite
; Compile with Inno Setup 6+ (https://jrsoftware.org/isinfo.php)

#define MyAppName "RetroSprite"
#define MyAppFriendlyName "RetroSprite - Pixel Art Creator"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "RetroSprite"
#define MyAppExeName "RetroSprite.exe"
#define MyAppURL "https://github.com/Theodor908/RetroSprite"

[Setup]
AppId={{E8A3F2B1-9C47-4D6E-A1B0-3F8E7C2D5A94}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=RetroSprite_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
AllowNoIcons=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Main executable
Source: "dist\RetroSprite\RetroSprite.exe"; DestDir: "{app}"; Flags: ignoreversion
; Internal dependencies
Source: "dist\RetroSprite\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Desktop shortcut with friendly name
Name: "{autodesktop}\{#MyAppFriendlyName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Start Menu entry
Name: "{group}\{#MyAppFriendlyName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch RetroSprite"; Flags: nowait postinstall skipifsilent
