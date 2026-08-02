# 🎬 AI-Powered Automated Home Media Server Stack

[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Jellyfin](https://img.shields.io/badge/Jellyfin-00A4DC?style=for-the-badge&logo=jellyfin&logoColor=white)](https://jellyfin.org/)
[![qBittorrent](https://img.shields.io/badge/qBittorrent-2F67AD?style=for-the-badge&logo=qbittorrent&logoColor=white)](https://qbittorrent.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=google-gemini&logoColor=white)](https://ai.google.dev/)

An all-in-one, self-hosted containerized home media ecosystem. It seamlessly pairs **qBittorrent** for automated downloads, **Jellyfin** for hardware-accelerated media streaming, and an intelligent **AI Media Sorter Watchdog** powered by **Google Gemini 1.5 Flash** to automatically organize incoming movies and TV series into clean, structured library directories.

---

## 🌟 Key Features

- 🍿 **Hardware-Accelerated Streaming**: Built-in Intel QuickSync Video (`/dev/dri`) device passthrough for efficient 4K/HD Jellyfin transcoding.
- 📥 **Headless Download Manager**: qBittorrent integration with a web-accessible UI (`WEBUI_PORT=8080`).
- 🤖 **Smart AI Media Sorter**:
  - **Fast Regex Engine**: Automatically extracts show titles, season numbers, and movie metadata from standardized release names.
  - **Gemini AI Fallback**: Utilizes `gemini-1.5-flash` to intelligently classify complex, obscure, or non-standard file names into Movies vs. TV Series and extract Season/Show info.
  - **Atomic File Operations**: Monitors active downloads to ensure files are fully written before moving them.
  - **Automated Permission Management**: Automatically fixes permissions (`chmod 777`) on moved media so Jellyfin indexes them instantly.
- 🐳 **100% Dockerized Architecture**: Managed effortlessly via Docker Compose with host network mode for high performance.

---

## 🏗️ Architecture & Data Flow

```mermaid
flowchart LR
    A[qBittorrent] -->|Downloads file| B[/srv/media/downloads]
    B -->|Monitors folder| C[Media Sorter Watchdog]
    C -->|1. Fast Regex Match| D{Is Match?}
    D -- Yes --> F[Extract Show & Season]
    D -- No --> E[Query Google Gemini 1.5 Flash API]
    E --> F
    F -->|Organize & Move| G[/srv/media/movies OR /srv/media/series]
    G -->|Fix Permissions & Index| H[Jellyfin Media Server]
```

### Directory Structure

```text
docker-server/
├── docker-compose.yml       # Central orchestration file for Jellyfin, qBittorrent & Sorter
├── config/                  # Persistent runtime configs
│   ├── jellyfin/            # Jellyfin server metadata, plugins, and cache
│   └── qbittorrent/         # qBittorrent application state and settings
└── sorter/                  # Sorter service source code
    ├── Dockerfile           # Python 3.10 runtime build definition
    └── media_sorter.py      # Watchdog script with Regex + Gemini AI integration
```

---

## 🚀 Getting Started

### Prerequisites

- **Host OS**: Linux distribution (e.g., Ubuntu/Debian/Arch) with Docker and Docker Compose installed.
- **Hardware**: Intel CPU with Integrated Graphics (`/dev/dri`) for hardware transcoding *(Optional, can be commented out if using software encoding)*.
- **API Key**: A free [Google Gemini API Key](https://aistudio.google.com/).

### Host Directory Preparation

Before launching the container stack, ensure the shared media directories exist on your host system:

```bash
sudo mkdir -p /srv/media/downloads
sudo mkdir -p /srv/media/movies
sudo mkdir -p /srv/media/series
sudo chmod -R 777 /srv/media
```

---

## ⚙️ Configuration & Installation

### 1. Set Up Google Gemini API Key

Edit `sorter/media_sorter.py` and replace `YOUR_GEMINI_KEY_HERE` with your actual Google Gemini API key:

```python
# sorter/media_sorter.py
GEMINI_API_KEY = 'your-actual-gemini-api-key-here'
```

> 💡 *Tip: For production setups, consider passing `GEMINI_API_KEY` as an environment variable via `docker-compose.yml`.*

### 2. Launch the Stack

Run Docker Compose to build the custom sorter container and start all services in detached mode:

```bash
docker compose up -d --build
```

### 3. Verify Container Status

Check that all three containers are healthy and running:

```bash
docker compose ps
```

---

## 🖥️ Service Access & Setup

| Service | Protocol / Port | Purpose | Default URL |
| :--- | :--- | :--- | :--- |
| **Jellyfin** | Host Network (8096) | Media Streaming & Library Management | `http://<your-server-ip>:8096` |
| **qBittorrent** | Host Network (8080) | Torrent Downloads | `http://<your-server-ip>:8080` |
| **Media Sorter** | Background Service | Automated File Sorting & Organizing | Container logs (`docker logs -f media_sorter`) |

### Service Configurations

#### 1. qBittorrent Setup
- Navigate to `http://<your-server-ip>:8080`.
- Set default download directory to `/downloads` in qBittorrent preferences. Downloads will land in `/srv/media/downloads` on the host.

#### 2. Jellyfin Setup
- Navigate to `http://<your-server-ip>:8096` to complete the initial setup wizard.
- Add **Movies** library pointed to `/media/movies`.
- Add **TV Shows** library pointed to `/media/series`.
- Enable **Intel QuickSync (QSV)** in `Admin Dashboard -> Playback -> Transcoding` for hardware acceleration.

#### 3. Media Sorter Watchdog
- Monitors `/downloads` inside the container every 60 seconds.
- Automatically skips active (growing) file downloads.
- Formats TV shows into `/media/series/<Show Name>/Season <N>/`.
- Places movies directly into `/media/movies/`.

---

## 🛠️ Logs & Troubleshooting

### Viewing Sorter Logs
To inspect real-time file processing and AI decision logs:

```bash
docker logs -f media_sorter
```

### Intel QuickSync GPU Access
If Jellyfin fails to transcode, check host permissions for `/dev/dri`:

```bash
ls -la /dev/dri
# Ensure host user is in the render/video group
sudo usermod -aG render,video $USER
```

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
