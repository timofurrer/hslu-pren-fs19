#!/bin/bash

set -e

ENSURE_SSH=true
CONFIGURE_WIFI=true
ADD_UART_OVERLAY=true

if [ -z "$1" ]; then
    echo "Please specify an image as the first argument" >&2
    exit 1
fi
IMAGE="$1"

if [ -z "$2" ]; then
    echo "Please specify the target disk as the second argument" >&2
    exit 1
fi
DISK="$2"

if $CONFIGURE_WIFI && [ -z "$3" ]; then
    echo "Please specify the wpa_supplicant file to use as the third argument" >&2
    exit 1
fi
WIFI_CONF_FILE="$3"

echo "[*] Mounting image ..."

kpartx_mount=$(kpartx -va "$IMAGE")
loop_device=$(echo "$kpartx_mount" | head -n1 | cut -d' ' -f3)
echo "[*] Mounted boot partition at $loop_device"

mkdir /tmp/raspi-disk
sleep 1
mount "/dev/mapper/$loop_device" /tmp/raspi-disk

if $ENSURE_SSH; then
    touch /tmp/raspi-disk/ssh
    echo "[*] ssh file written"
fi

if $CONFIGURE_WIFI; then
    cp "$WIFI_CONF_FILE" /tmp/raspi-disk/wpa_supplicant.conf
    echo "[*] wpa supplicant file written"
fi

if $ADD_UART_OVERLAY; then
    echo "dtoverlay=pi3-miniuart-bt" >> /tmp/raspi-disk/config.txt
    echo "[*] added UART overlay to kernel options"
fi

sleep 1
echo "[*] Unmounting image ..."
umount /tmp/raspi-disk
rm -rf /tmp/raspi-disk
kpartx -d "$IMAGE"

echo "[*] Writing image to SD card ..."
dd if="$IMAGE" of="$DISK" bs=4M conv=fsync status=progress
echo "[*] Done!"
