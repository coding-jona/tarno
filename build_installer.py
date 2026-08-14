import os
import sys
import shutil
import logging
import subprocess
import platform
from pathlib import Path

# --- Konfiguration & Pfade ---
APP_NAME = "Tarno Mesh"
APP_VERSION = "1.2.0"
BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"
LOG_FILE = BASE_DIR / "build.log"

ISCC_PATHS = [
    Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Inno Setup 6" / "ISCC.exe",
]

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("TarnoBuilder")

def get_venv_python():
    """Ermittelt automatisch das Python-Executable aus der .venv oder nutzt das System-Python."""
    if platform.system() == "Windows":
        venv_python = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = BASE_DIR / ".venv" / "bin" / "python"

    return venv_python if venv_python.exists() else Path(sys.executable)

def run_step(cmd, description):
    """Führt einen Build-Schritt aus und loggt die Ausgabe live."""
    logger.info(f"=== Starte: {description} ===")
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=BASE_DIR
        )

        for line in process.stdout:
            logger.info(f"  [BUILD] {line.strip()}")

        process.wait()

        if process.returncode != 0:
            logger.error(f"X Fehlschlag bei: {description} (Code {process.returncode})")
            return False

        logger.info(f"V Erfolgreich: {description}\n")
        return True
    except Exception as e:
        logger.exception(f"X Fehler beim Ausführen von '{description}': {e}")
        return False

def cleanup_obsolete_packages(venv_python):
    """Entfernt veraltete Pakete wie enum34, die PyInstaller blockieren."""
    result = subprocess.run([str(venv_python), "-m", "pip", "show", "enum34"], capture_output=True)
    if result.returncode == 0:
        logger.info("Veraltetes Paket 'enum34' gefunden. Entferne es automatisch...")
        run_step([str(venv_python), "-m", "pip", "uninstall", "enum34", "-y"], "Entfernen von enum34")

def ensure_pyinstaller(venv_python):
    """Prüft und installiert PyInstaller bei Bedarf."""
    result = subprocess.run([str(venv_python), "-c", "import PyInstaller"], capture_output=True)
    if result.returncode != 0:
        logger.info("PyInstaller nicht in .venv gefunden. Installiere automatisch...")
        if not run_step([str(venv_python), "-m", "pip", "install", "pyinstaller"], "PyInstaller Installation"):
            return False
    return True

def find_entry_point():
    """Sucht automatisch nach der Hauptdatei im Projekt."""
    candidates = [
        BASE_DIR / "src" / "tarno_backend" / "__main__.py",
        BASE_DIR / "src" / "tarno_backend" / "app.py",
        BASE_DIR / "main.py"
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def package_for_freebsd(source_dir: Path, out_dir: Path):
    """Erstellt ein tar.gz Archiv für FreeBSD mit einem einfachen Install-README."""
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_name = out_dir / f"{APP_NAME.replace(' ', '_')}-{APP_VERSION}-freebsd"
    logger.info(f"Erstelle tar.gz Paket fuer FreeBSD: {archive_name}.tar.gz")

    readme = source_dir / "INSTALL_FREEBSD.txt"
    readme.write_text(
        """Tarno FreeBSD packaging

Installation:
  1) Entpacken: tar xzf <archive>.tar.gz -C /opt
  2) Ins Verzeichnis wechseln: /opt/<package>
  3) Anwendung starten: ./tarno (oder ./Tarno Mesh je nach Build)

Hinweis: Dieses Paket enthält nur das Python-Backend; die WinUI-Frontend-UI wird auf FreeBSD nicht unterstützt.
"""
    )

    shutil.copytree(source_dir, out_dir / archive_name.name, dirs_exist_ok=True)
    # make_archive expects the base_name without suffix
    base = str(out_dir / archive_name.name)
    shutil.make_archive(base, 'gztar', root_dir=out_dir, base_dir=archive_name.name)
    # cleanup temporary copied folder
    shutil.rmtree(out_dir / archive_name.name, ignore_errors=True)
    logger.info(f"FreeBSD Paket erstellt: {base}.tar.gz")
    return Path(f"{base}.tar.gz")


def main():
    logger.info("==================================================")
    logger.info(f"   Building {APP_NAME} v{APP_VERSION} Installer (platform={platform.system()})")
    logger.info("==================================================")

    python_exe = get_venv_python()
    logger.info(f"Verwende Python-Interpreter: {python_exe}")

    # Automatische Vorbereitungen
    cleanup_obsolete_packages(python_exe)
    if not ensure_pyinstaller(python_exe):
        sys.exit(1)

    entry_point = find_entry_point()
    if not entry_point:
        logger.error("X Kein gültiger Einstiegspunkt (__main__.py oder app.py) gefunden!")
        sys.exit(1)
    logger.info(f"Einstiegspunkt automatisch erkannt: {entry_point}")

    # Alte Build-Ordner aufräumen
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    # PyInstaller Befehl zusammenbauen
    pyinstaller_cmd = [
        str(python_exe), "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        # avoid --windowed on non-Windows platforms
        "--name", APP_NAME,
        "--paths", str(BASE_DIR / "src"),  # Löst Import-Probleme im src-Layout
        str(entry_point)
    ]

    # On Windows we prefer a windowed app if building a GUI; for FreeBSD keep console
    if platform.system() == 'Windows':
        pyinstaller_cmd.insert(3, "--windowed")

    # Optionaler Models-Ordner
    models_dir = BASE_DIR / "models"
    if models_dir.exists():
        pyinstaller_cmd.extend(["--add-data", f"{models_dir}{os.pathsep}models"])
        logger.info("Ordner 'models' wird ins Paket eingebunden.")
    else:
        logger.info("Hinweis: Kein 'models'-Ordner im Root gefunden (wird übersprungen).")

    if not run_step(pyinstaller_cmd, "PyInstaller Bundling"):
        logger.error("X PyInstaller-Build fehlgeschlagen. Details siehe build.log.")
        sys.exit(1)

    # Pruefung: Stelle sicher, dass PyInstaller Output vorhanden ist
    if not DIST_DIR.exists():
        logger.error("X Dist-Ordner wurde nicht erstellt. PyInstaller hat scheinbar nichts publiziert.")
        sys.exit(1)

    # Suche nach dem erzeugten Backend-Ordner oder EXE
    possible_backend_dir = DIST_DIR / APP_NAME
    possible_backend_exe = DIST_DIR / (APP_NAME + ('.exe' if platform.system() == 'Windows' else ''))
    if not possible_backend_dir.exists() and not possible_backend_exe.exists():
        # versuche generischen Inhalt
        items = list(DIST_DIR.iterdir())
        if len(items) == 0:
            logger.error("X PyInstaller hat keine Artefakte in 'dist' erzeugt.")
            sys.exit(1)
        else:
            logger.info(f"Info: Gefundene Dist-Inhalte: {[p.name for p in items]}")

    # Platform-specific packaging
    if platform.system() == 'Windows':
        # Try to run Inno Setup if available
        iscc_exe = next((p for p in ISCC_PATHS if p.exists()), None)
        iss_file = BASE_DIR / "setup.iss"
        if iscc_exe and iss_file.exists():
            run_step([str(iscc_exe), str(iss_file)], "Inno Setup Compiler")
        else:
            logger.info("Inno Setup Schritt übersprungen (optional). Erzeuge stattdessen Zip-Staging in dist/TARNO_Package.")
            # assemble staging like the PowerShell script does
            staging = DIST_DIR / 'TARNO_Package'
            staging.mkdir(parents=True, exist_ok=True)
            # copy pyinstaller output
            src_py = possible_backend_dir if possible_backend_dir.exists() else (possible_backend_exe.parent if possible_backend_exe.exists() else DIST_DIR)
            shutil.copytree(src_py, staging / 'tarno', dirs_exist_ok=True)
            # Attempt to include UI publish if it exists
            ui_publish = BASE_DIR.parent / 'src' / 'TARNO.UI' / 'bin' / 'x64' / 'Release' / 'net8.0-windows10.0.19041.0' / 'win-x64' / 'publish'
            if ui_publish.exists():
                shutil.copytree(ui_publish, staging / 'UI', dirs_exist_ok=True)
            # create zip
            archive = shutil.make_archive(str(staging), 'zip', root_dir=staging)
            logger.info(f"Staging zip erstellt: {archive}")

    elif platform.system() == 'FreeBSD':
        # On FreeBSD we create a tar.gz package for the backend (WinUI frontend not supported)
        backend_src = possible_backend_dir if possible_backend_dir.exists() else (possible_backend_exe.parent if possible_backend_exe.exists() else DIST_DIR)
        out = DIST_DIR / 'packages'
        out.mkdir(parents=True, exist_ok=True)
        archive = package_for_freebsd(backend_src, out)
        logger.info(f"FreeBSD package erstellt: {archive}")
    else:
        logger.info(f"Unbekannte Plattform '{platform.system()}': Erzeuge generisches zip im dist-Ordner.")
        staging = DIST_DIR / 'TARNO_Package'
        staging.mkdir(parents=True, exist_ok=True)
        src_py = possible_backend_dir if possible_backend_dir.exists() else (possible_backend_exe.parent if possible_backend_exe.exists() else DIST_DIR)
        shutil.copytree(src_py, staging / 'tarno', dirs_exist_ok=True)
        archive = shutil.make_archive(str(staging), 'zip', root_dir=staging)
        logger.info(f"Staging zip erstellt: {archive}")

    logger.info("==================================================")
    logger.info(f"V BUILD ERFOLGREICH BEENDET! Output: {DIST_DIR}")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
