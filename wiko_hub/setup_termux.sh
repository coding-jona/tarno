#!/data/data/com.termux/files/usr/bin/bash
# TARNO Mesh - Wiko View 5 Plus Termux setup.
# Run this ONCE inside Termux on the Wiko phone - entweder direkt in der
# Termux-App eingetippt, oder remote per
# `adb shell run-as com.termux files/usr/bin/bash <pfad-zu-diesem-skript>`
# (setzt vorher HOME/PREFIX/PATH, siehe README - getestet und funktioniert).

set -e

echo "== TARNO Mesh Wiko-Hub Setup =="

echo "-> Termux-Pakete aktualisieren..."
# --force-confdef/--force-confold: bei Konfigurationsdatei-Konflikten (z.B.
# openssl.cnf beim Upgrade) automatisch die aktuell installierte Version
# behalten statt interaktiv nachzufragen - ohne das wuerde apt hier auf ein
# Terminal warten, das in einer nicht-interaktiven Shell (adb/Automatisierung)
# nie kommt, und mit "end of file on stdin at conffile prompt" abbrechen.
pkg update -y && pkg upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

echo "-> Python installieren..."
pkg install -y python

echo "-> Python-Abhängigkeiten installieren..."
# KEIN "pip install --upgrade pip" - Termux verwaltet pip selbst ueber das
# python-pip-Paket und verbietet Self-Upgrades explizit ("Installing pip is
# forbidden, this will break the python-pip package (termux)."), im
# Gegensatz zu normalen Linux-/Windows-Python-Installationen.
#
# python-psutil VOR amqtt installieren: amqtt haengt von psutil ab, dessen
# eigenes setup.py den Build auf "platform android" explizit verweigert
# ("platform android is not supported") - pip wuerde also versuchen, es aus
# der Quelle zu bauen und scheitern. Termux hat eine eigene, fertig
# gepatchte psutil-Version im apt-Repo; einmal per pkg installiert, findet
# pip install amqtt es bereits erfuellt und baut nichts mehr selbst.
pkg install -y python-psutil
pip install amqtt

echo "-> Termux:Boot-Verzeichnis vorbereiten..."
echo "   WICHTIG: installiere zusätzlich die App 'Termux:Boot' aus F-Droid"
echo "   (NICHT im Play Store verfügbar - nur F-Droid oder GitHub Releases)."
mkdir -p "$HOME/.termux/boot"

BOOT_SCRIPT="$HOME/.termux/boot/start-mesh-hub.sh"
cat > "$BOOT_SCRIPT" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd "$HOME/tarno_mesh_hub" || exit 1
python broker_and_analytics.py >> "$HOME/tarno_mesh/hub.log" 2>&1
EOF
chmod +x "$BOOT_SCRIPT"

echo "-> Zielordner für das Hub-Skript anlegen..."
mkdir -p "$HOME/tarno_mesh_hub"
echo "   Kopiere broker_and_analytics.py jetzt dorthin, z.B. via:"
echo "   termux-setup-storage && cp /sdcard/Download/broker_and_analytics.py ~/tarno_mesh_hub/"

echo ""
echo "== Fertig =="
echo "Nach einem Neustart des Handys startet der Hub automatisch (via Termux:Boot)."
echo "Manuell testen: cd ~/tarno_mesh_hub && python broker_and_analytics.py"
echo ""
echo "WICHTIG - Akku-Optimierung deaktivieren für zuverlässigen Dauerbetrieb:"
echo "  Android-Einstellungen -> Apps -> Termux -> Akku -> 'Nicht optimieren'"
echo "  (sonst killt Android den Hintergrundprozess nach einiger Zeit)"
