#!/bin/bash

# --- CONFIGURATION ---
# List of services to stop/start
SERVICES="jellyfin qbittorrent-nox@spidey telegram-bot"

# Your Hotspot Command (Added --daemon so it runs in background)
# Ensure 'usb0' matches your phone's interface name!
HOTSPOT_CMD="create_ap --daemon --no-virt wlan0 usb0 MyMediaServer MyPassword --freq-band 2.4"
# ---------------------

echo "🌙 Goodnight! Stopping services..."

# 1. Kill the Hotspot (Clean up old processes)
sudo create_ap --stop wlan0
sudo killall create_ap

# 2. Stop Applications
sudo systemctl stop $SERVICES

echo "⏰ Setting alarm for 7:00 AM..."

# 3. Set the Wake-Up Alarm & Sleep
# This command suspends the laptop to RAM (-m mem) and wakes it at 07:00 tomorrow
sudo rtcwake -m mem --date "tomorrow 07:00"

# --- THE SYSTEM SLEEPS HERE --- 
# (The script pauses exactly here until the laptop wakes up)

echo "☀️ Good morning! Waking up..."

# 4. Wait for hardware to initialize (USB, Wi-Fi, etc)
sleep 15

# 5. Restart Applications
sudo systemctl start $SERVICES

# 6. Restart Hotspot
# We restart NetworkManager first to ensure USB Tethering is grabbed
sudo systemctl restart NetworkManager
sleep 5
sudo $HOTSPOT_CMD

echo "✅ All systems online."