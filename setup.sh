#!/usr/bin/env bash
#toolchain into tools/, cocotb into its python

set -euo pipefail
cd "$(dirname "$0")"

TAG="2026-07-19"  #oss-cad-suite-build release
TARBALL="oss-cad-suite-linux-x64-${TAG//-/}.tgz"

if [ ! -x tools/oss-cad-suite/bin/yosys ]; then
    echo ">> downloading oss-cad-suite ${TAG} (~1GB)"
    mkdir -p tools
    curl -L --fail -o "tools/${TARBALL}" \
        "https://github.com/YosysHQ/oss-cad-suite-build/releases/download/${TAG}/${TARBALL}"
    echo ">> extracting"
    tar -xzf "tools/${TARBALL}" -C tools
    rm "tools/${TARBALL}"
fi

#the suite's own python
if [ ! -x tools/oss-cad-suite/py3bin/cocotb-config ]; then
    echo ">> installing python deps"
    tools/oss-cad-suite/py3bin/pip3 install -q -r requirements.txt
fi

echo
echo "done. activate with:  source tools/oss-cad-suite/environment"
echo
echo "to flash over usb without sudo (one time):"
echo "  curl -sL https://raw.githubusercontent.com/trabucayre/openFPGALoader/master/99-openfpgaloader.rules | sudo tee /etc/udev/rules.d/99-openfpgaloader.rules >/dev/null"
echo "  sudo udevadm control --reload-rules && sudo udevadm trigger"
