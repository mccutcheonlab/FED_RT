#!/bin/bash
set -e

# ---------- CONFIG ----------
TARGET_USER="hpfed"
HOME_DIR="/home/$TARGET_USER"
DESKTOP="$HOME_DIR/Desktop"
LOCAL_REPO="$HOME_DIR/HOMEPHOTOFED/GitHub/FED_RT"
BRANCH="RTFEDPi"
INSTALL_ROOT="/opt/FED_RT"

# ---------- 1) System deps ----------
echo "🔧 Updating apt and installing system packages..."
sudo apt update -y
sudo apt install -y \
  python3 python3-pip python3-venv python3-tk \
  git ffmpeg v4l-utils libatlas-base-dev libopenblas-dev \
  libjpeg-dev zlib1g-dev rsync

# ---------- 2) Copy project to /opt/FED_RT ----------
echo "📦 Copying from local repository ($LOCAL_REPO)..."
if [ ! -d "$LOCAL_REPO/.git" ]; then
  echo "❌ Local repo not found at $LOCAL_REPO"
  exit 1
fi

sudo mkdir -p "$INSTALL_ROOT"
sudo rsync -a --delete "$LOCAL_REPO"/ "$INSTALL_ROOT"/
sudo chown -R "$TARGET_USER:$TARGET_USER" "$INSTALL_ROOT"

# ---------- 3) Create HOMEPHOTOFED venv ----------
echo "🐍 Creating HOMEPHOTOFED environment in $INSTALL_ROOT..."
python3 -m venv "$INSTALL_ROOT/HOMEPHOTOFED"
source "$INSTALL_ROOT/HOMEPHOTOFED/bin/activate"

# ---------- 4) Install Python deps ----------
REQ_FILE="$INSTALL_ROOT/requirements.txt"
echo "📚 Installing Python packages..."
pip install --upgrade pip
if [ -f "$REQ_FILE" ]; then
  pip install -r "$REQ_FILE"
else
  echo "⚠️ requirements.txt not found — installing a minimal set."
  pip install gspread google-auth pyserial opencv-python pandas numpy pillow
fi
deactivate

# ---------- 5) Create launcher scripts ----------
echo "🚀 Creating launcher scripts..."
sudo -u "$TARGET_USER" mkdir -p "$INSTALL_ROOT/launchers"

sudo tee "$INSTALL_ROOT/launchers/rtfed_basic.sh" >/dev/null <<'EOF'
#!/bin/bash
BIN="/opt/FED_RT/bin/RTFED_Basic"
PY="/opt/FED_RT/scripts/RTFED_PiBasic/RTFEDPi(Basic).py"
ENV="/opt/FED_RT/HOMEPHOTOFED/bin/activate"
if [ -f "$BIN" ]; then exec "$BIN"; else source "$ENV"; python "$PY"; fi
EOF

sudo tee "$INSTALL_ROOT/launchers/rtfed_picam.sh" >/dev/null <<'EOF'
#!/bin/bash
BIN="/opt/FED_RT/bin/RTFED_PiCAM"
PY="/opt/FED_RT/scripts/RTFED_PiCAM/RTFED(PiCAM).py"
ENV="/opt/FED_RT/HOMEPHOTOFED/bin/activate"
if [ -f "$BIN" ]; then exec "$BIN"; else source "$ENV"; python "$PY"; fi
EOF

sudo tee "$INSTALL_ROOT/launchers/rtfed_pittl.sh" >/dev/null <<'EOF'
#!/bin/bash
BIN="/opt/FED_RT/bin/RTFED_PiTTL"
PY="/opt/FED_RT/scripts/RTFED_TTL/RTFED(PiTTL).py"
ENV="/opt/FED_RT/HOMEPHOTOFED/bin/activate"
if [ -f "$BIN" ]; then exec "$BIN"; else source "$ENV"; python "$PY"; fi
EOF

sudo chmod +x "$INSTALL_ROOT/launchers/"*.sh
sudo chown -R "$TARGET_USER:$TARGET_USER" "$INSTALL_ROOT/launchers"

# ---------- 6) Create Desktop icons ----------
echo "🖥 Creating Desktop icons..."
mkdir -p "$DESKTOP"

cat >"$DESKTOP/RTFED_Basic.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=RTFED Basic
Exec=/opt/FED_RT/launchers/rtfed_basic.sh
Icon=utilities-terminal
Comment=Run the RTFED Basic GUI
Categories=Education;Science;
Terminal=false
EOF

cat >"$DESKTOP/RTFED_PiCAM.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=RTFED PiCAM
Exec=/opt/FED_RT/launchers/rtfed_picam.sh
Icon=video-display
Comment=Run the RTFED PiCAM GUI
Categories=Education;Science;
Terminal=false
EOF

cat >"$DESKTOP/RTFED_PiTTL.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=RTFED PiTTL
Exec=/opt/FED_RT/launchers/rtfed_pittl.sh
Icon=utilities-terminal
Comment=Run the RTFED PiTTL GUI
Categories=Education;Science;
Terminal=false
EOF

chmod +x "$DESKTOP"/RTFED_*.desktop

echo "✅ Installation complete!"
echo "• Non-coders: double-click the three icons on your Desktop."
echo "• Experts: source /opt/FED_RT/HOMEPHOTOFED/bin/activate, then edit/run code in /opt/FED_RT/scripts/..."
