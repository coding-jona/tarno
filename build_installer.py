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

def main():
    logger.info("==================================================")
    logger.info(f"   Building {APP_NAME} v{APP_VERSION} Windows Installer")
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
        "--windowed",
        "--name", APP_NAME,
        "--paths", str(BASE_DIR / "src"),  # Löst Import-Probleme im src-Layout
        str(entry_point)
    ]

    # Optionaler Models-Ordner
    models_dir = BASE_DIR / "models"
    if models_dir.exists():
        pyinstaller_cmd.extend(["--add-data", f"models{os.pathsep}models"])
        logger.info("Ordner 'models' wird ins Paket eingebunden.")
    else:
        logger.info("Hinweis: Kein 'models'-Ordner im Root gefunden (wird übersprungen).")

    if not run_step(pyinstaller_cmd, "PyInstaller Bundling"):
        logger.error("X PyInstaller-Build fehlgeschlagen. Details siehe build.log.")
        sys.exit(1)

    # Inno Setup (optional)
    iscc_exe = next((p for p in ISCC_PATHS if p.exists()), None)
    iss_file = BASE_DIR / "setup.iss"

    if iscc_exe and iss_file.exists():
        run_step([str(iscc_exe), str(iss_file)], "Inno Setup Compiler")
    else:
        logger.info("Inno Setup Schritt übersprungen (optional).")

    logger.info("==================================================")
    logger.info(f"V BUILD ERFOLGREICH BEENDET! Output: {DIST_DIR}")
    logger.info("==================================================")

if __name__ == "__main__":
    main()