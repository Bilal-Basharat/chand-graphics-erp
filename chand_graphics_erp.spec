# -*- mode: python ; coding: utf-8 -*-
"""
Production build. One directory, no console, and nothing of the
customer's inside it.

    pyinstaller --clean --noconfirm chand_graphics_erp.spec

The result is `dist/ChandGraphicsERP/`, which is what an installer copies
into Program Files. Everything in that folder is code the vendor ships;
everything the customer owns — database, licence, configuration, logs —
is written at runtime under %LOCALAPPDATA%\\ChandGraphicsERP and never
here. Replacing this folder is exactly what an upgrade does.

`datas` is deliberately empty. This application has no packaged runtime
resources at all: the theme is built in Python (`presentation/theme/
stylesheet.py`), the two image assets are painted with QPainter on first
use into the data folder (`presentation/theme/assets.py`), the navigation
icons are drawn the same way, the base font is the operating system's,
and the schema is upgraded by numbered steps in Python
(`infrastructure/db/upgrade.py`) rather than by migration files on disk.
Keeping the list empty is therefore not an oversight to be corrected
later — it is what stops `.env` and `data/erp.db` reaching a build.
"""
from PyInstaller.utils.hooks import collect_submodules

APP_NAME = "ChandGraphicsERP"

hiddenimports = [
    # SQLAlchemy loads its dialect by name at connect time, so nothing
    # imports this module in a way static analysis can see.
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    # keyring finds its backends through entry points, which do not
    # survive freezing. Without these the credential vault reports itself
    # unavailable and both the remembered sign-in password and the mail
    # password quietly stop working.
    *collect_submodules("keyring.backends"),
]

excludes = [
    # Development only, and the reason it is named here rather than left
    # to chance: `load_development_env()` already refuses to read a .env
    # in a frozen build, and leaving the library out makes that a
    # property of the build instead of a branch that has to be right.
    "dotenv",
    # Declared in requirements.txt but imported nowhere in the
    # application. Migrations are the numbered steps in upgrade.py.
    "alembic",
    "pydantic",
    # Testing and formatting tooling.
    "pytest",
    "black",
    "isort",
    "tkinter",
    # Qt frameworks this application does not use. It draws widgets,
    # prints (QtPrintSupport) and charts one bar graph (QtCharts);
    # everything below would otherwise be carried as dead weight.
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    # The database is reached through SQLAlchemy and the standard
    # library's sqlite3, never through Qt's own SQL layer.
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]

analysis = Analysis(
    ["app/main.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Windowed: this is a desktop application, and a console window
    # behind it would be both ugly and something a user can close out
    # from under the app.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
