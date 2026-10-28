# AI Video Studio — Trend Editor Starter

A responsive Flask starter for an AI-assisted video-editing workflow. It includes user accounts, project saving, eight editing-style presets, a brief-to-editing-blueprint generator, video upload, and an optional FFmpeg transcode export.

## Important reality check
This starter does **not** yet generate full AI-edited videos by itself. The preset engine creates an editing blueprint. The export button currently transcodes the uploaded source video to a compatible MP4; it does not automatically apply all style effects. Real automatic captions, speech transcription, beat detection, generative video, and timeline effect rendering require additional AI/media services and implementation.

## Run on Windows
Open PowerShell in this folder:

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000`. Create an account, log in, open Studio, choose a preset, and save a project.

If `Copy-Item` says `.env` already exists, that is fine; do not overwrite a secret you have already set.

## FFmpeg (optional)
To enable MP4 export, install FFmpeg from https://ffmpeg.org/download.html and make sure `ffmpeg -version` works in a new terminal. Export in this starter makes a compatible H.264/AAC MP4; it does not yet apply preset-specific effects.

## Where data is stored locally
- Accounts and project metadata: `instance/studio.db`
- Uploaded source videos: `instance/uploads/`
- Exports: `instance/exports/`

Back up the `instance` folder. Deleting it deletes local accounts, projects, uploads, and exports.

## Android and laptop access
The interface is responsive. To test on your Android phone while it shares the same Wi-Fi, run `ipconfig`, find your laptop's IPv4 address, then open `http://YOUR-LAPTOP-IP:5000` on the phone. Allow Python through Windows Firewall if prompted. This is local testing, not public hosting.

## Deploying online
Use a managed database and persistent object storage before production. The local SQLite database and `instance/` folders are not reliable permanent storage on many cloud hosts. Set a strong `SECRET_KEY`, disable debug mode, and configure backups before sharing with other users. A production release should also add CSRF protection, rate limiting, file scanning, and a background job queue for long renders.


## Local automatic editing features (V2)

This version adds an FFmpeg-based export form with trim-in/trim-out, 480p/720p/1080p/4K scaling, file-size presets, simple color looks, a fade-in option, background-noise reduction, optional GIF/image upload, and local automatic speech transcription using faster-whisper. Caption generation downloads a Whisper model on first use and can take time; generated captions are included as an MP4 subtitle track and an SRT download.

### Required system dependency

Install FFmpeg and add its `bin` folder to Windows PATH. Open a new PowerShell window and verify with `ffmpeg -version`. Install Python packages with `py -m pip install -r requirements.txt`. The first caption run downloads the configured Whisper model (default `base`); set `WHISPER_MODEL=tiny` for a faster, less accurate model.

### Important limitations

This is an early local editing pipeline, not a full human-equivalent editor. Speech recognition may be inaccurate and should be reviewed. Sticker overlays and certain filters depend on the installed FFmpeg build. It does not yet infer and clone an arbitrary reference video's exact cuts, motion graphics, or effects; it also does not yet do beat detection, silence-aware automatic cutting, generative video, or true animated transitions between separate scenes. Preview and verify exports before publishing. For public hosting, use persistent storage and add upload quotas and resource limits.
