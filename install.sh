#!/bin/bash
set -e

# Detect current (target) user even under sudo
TARGET_USER="${SUDO_USER:-$USER}"
HOME_DIR="$(eval echo "~$TARGET_USER")"
DESKTOP="$HOME_DIR/Desktop"

REPO_URL="https://github.com/mccutcheonlab/FED_RT.git"
BRANCH="RTFEDPi"
INSTALL_ROOT="/opt/FED_RT"

echo "🔧 Updating apt and installing system packages..."
sudo apt update -y
sudo apt install -y \
  python3 python3-pip python3-venv python3-tk \
  git ffmpeg v4l-utils libatlas-base-dev libopenblas-dev \
  libjpeg-dev zlib1g-dev rsync

echo "📦 Preparing $INSTALL_ROOT..."
sudo mkdir -p "$INSTALL_ROOT"

# If we are inside a git working copy, install from here; else clone from GitHub
if [ -d .git ]; then
  echo "➡️ Installing from local working copy: $(pwd)"
  sudo rsync -a --delete ./ "$INSTALL_ROOT"/
else
  echo "➡️ Cloning from GitHub ($BRANCH)..."
  sudo rm -rf "$INSTALL_ROOT"/*
  sudo git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_ROOT"
fi

sudo chown -R "$TARGET_USER:$TARGET_USER" "$INSTALL_ROOT"

echo "🐍 Creating HOMEPHOTOFED environment..."
python3 -m venv "$INSTALL_ROOT/HOMEPHOTOFED"
source "$INSTALL_ROOT/HOMEPHOTOFED/bin/activate"

echo "📚 Installing Python packages..."
REQ_FILE="$INSTALL_ROOT/requirements.txt"
pip install --upgrade pip
if [ -f "$REQ_FILE" ]; then
  pip install -r "$REQ_FILE"
else
  echo "⚠️ requirements.txt not found — installing a minimal set."
  pip install gspread google-auth pyserial opencv-python pandas numpy pillow
fi
deactivate

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

echo "🖥 Creating Desktop icons..."
sudo -u "$TARGET_USER" mkdir -p "$DESKTOP"

sudo -u "$TARGET_USER" tee "$DESKTOP/RTFED_Basic.desktop" >/dev/null <<'EOF'
[Desktop Entry]
Type=Application
Name=RTFED Basic
Exec=/opt/FED_RT/launchers/rtfed_basic.sh
Icon=utilities-terminal
Comment=Run the RTFED Basic GUI
Categories=Education;Science;
Terminal=false
EOF

sudo -u "$TARGET_USER" tee "$DESKTOP/RTFED_PiCAM.desktop" >/dev/null <<'EOF'
[Desktop Entry]
Type=Application
Name=RTFED PiCAM
Exec=/opt/FED_RT/launchers/rtfed_picam.sh
Icon=video-display
Comment=Run the RTFED PiCAM GUI
Categories=Education;Science;
Terminal=false
EOF

sudo -u "$TARGET_USER" tee "$DESKTOP/RTFED_PiTTL.desktop" >/dev/null <<'EOF'
[Desktop Entry]
Type=Application
Name=RTFED PiTTL
Exec=/opt/FED_RT/launchers/rtfed_pittl.sh
Icon=utilities-terminal
Comment=Run the RTFED PiTTL GUI
Categories=Education;Science;
Terminal=false
EOF

sudo chmod +x "$DESKTOP"/RTFED_*.desktop

echo "✅ Done!"
echo "• Non-coders: double-click the three Desktop icons."
echo "• Experts: source $INSTALL_ROOT/HOMEPHOTOFED/bin/activate, then run/edit code under $INSTALL_ROOT/scripts/ ..."
