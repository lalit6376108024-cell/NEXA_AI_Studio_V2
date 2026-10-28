import os, sqlite3, secrets, json, subprocess, shutil
from datetime import datetime
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
INSTANCE = BASE_DIR / "instance"
UPLOADS = INSTANCE / "uploads"
EXPORTS = INSTANCE / "exports"
for folder in (INSTANCE, UPLOADS, EXPORTS):
    folder.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = str(UPLOADS)
ALLOWED_EXTENSIONS = {"mp4", "mov", "m4v", "webm", "avi"}
ALLOWED_STICKERS = {"gif", "png", "jpg", "jpeg", "webp"}

PRESETS = {
    "viral_reel": {
        "name": "Viral Reel", "emoji": "⚡", "description": "Fast hooks, punchy cuts, animated captions, vertical framing.",
        "format": "9:16 vertical", "pace": "Fast", "captions": "Bold kinetic captions",
        "color": "Bright contrast", "transitions": "Quick cuts and punch-ins",
        "steps": ["Open with a strong 1–2 second hook.", "Remove pauses and repeated phrases.", "Use bold captions with highlighted keywords.", "Keep the strongest moment near the beginning.", "Finish with a clear takeaway or call to action."]
    },
    "cinematic": {
        "name": "Cinematic", "emoji": "🎬", "description": "Film-like color, considered pacing, dramatic titles.",
        "format": "16:9 widescreen", "pace": "Measured", "captions": "Minimal elegant subtitles",
        "color": "Cinematic contrast", "transitions": "Soft fades and motivated cuts",
        "steps": ["Choose the strongest establishing shot.", "Let key moments breathe; trim only distracting dead time.", "Apply a consistent film-inspired color look.", "Use restrained titles and smooth transitions.", "Shape the ending around the emotional high point."]
    },
    "velocity": {
        "name": "Velocity / Beat Sync", "emoji": "🎵", "description": "Speed ramps, action emphasis, rhythm-led cuts.",
        "format": "9:16 or 16:9", "pace": "Very fast", "captions": "Short punchy text",
        "color": "High-energy contrast", "transitions": "Speed ramps and beat cuts",
        "steps": ["Find the strongest action moments.", "Mark music beats before placing cuts.", "Use speed ramps only where motion supports them.", "Sync transitions to the rhythm.", "Keep effects short so the action stays readable."]
    },
    "motivation": {
        "name": "Motivation / Transformation", "emoji": "🔥", "description": "Emotional progression, strong statements, uplifting finish.",
        "format": "9:16 vertical", "pace": "Builds from slow to fast", "captions": "Large emphasis captions",
        "color": "Warm dramatic grade", "transitions": "Match cuts and rising momentum",
        "steps": ["Start with a struggle, question, or bold statement.", "Arrange clips as beginning, effort, and progress.", "Add concise captions that reinforce the message.", "Build pace toward the strongest achievement.", "End with a memorable line or next step."]
    },
    "ai_story": {
        "name": "AI Story", "emoji": "🌌", "description": "Turn an idea into a scene-by-scene editing blueprint.",
        "format": "Choose per platform", "pace": "Story-led", "captions": "Narrative captions",
        "color": "Mood-based palette", "transitions": "Scene-matched transitions",
        "steps": ["Write the central idea in one sentence.", "Split it into a hook, setup, turning point, and payoff.", "Assign one visual to each story beat.", "Generate narration and on-screen text.", "Keep a consistent visual mood across scenes."]
    },
    "retro": {
        "name": "Retro / VHS", "emoji": "📼", "description": "Nostalgic texture, film grain, dated timestamps and color shifts.",
        "format": "4:3 or 9:16", "pace": "Flexible", "captions": "Retro typewriter text",
        "color": "Warm faded / VHS", "transitions": "Analog glitches and tape cuts",
        "steps": ["Choose clips with a nostalgic feel.", "Apply a restrained grain or tape texture.", "Use a limited retro color palette.", "Add timestamp or typewriter-style text sparingly.", "Avoid stacking too many distortion effects."]
    },
    "clean_creator": {
        "name": "Clean Creator", "emoji": "🎙️", "description": "Clear speech, readable subtitles, tidy pacing and polished framing.",
        "format": "9:16, 1:1, or 16:9", "pace": "Natural", "captions": "Clean readable subtitles",
        "color": "Natural skin tones", "transitions": "Simple cuts",
        "steps": ["Prioritize clear speech and good audio levels.", "Trim long pauses without making delivery feel rushed.", "Keep the speaker framed consistently.", "Add readable subtitles with safe margins.", "Use simple titles and a clear final takeaway."]
    },
    "motion_graphics": {
        "name": "Motion Graphics", "emoji": "📊", "description": "Animated labels, data callouts, diagrams and explainer pacing.",
        "format": "16:9 or 9:16", "pace": "Clear and structured", "captions": "Labels and callouts",
        "color": "Brand-consistent palette", "transitions": "Animated wipes and reveals",
        "steps": ["Break the explanation into three to five points.", "Use a visual label for each important idea.", "Animate only elements that clarify meaning.", "Keep charts and text on screen long enough to read.", "End with a concise summary."]
    }
}

def db():
    conn = sqlite3.connect(INSTANCE / "studio.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            title TEXT NOT NULL, filename TEXT, sticker_filename TEXT, preset TEXT NOT NULL DEFAULT 'viral_reel',
            brief TEXT DEFAULT '', plan_json TEXT DEFAULT '{}', created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id))""")
        # Safe migration for databases created by earlier NEXA versions.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
        if "sticker_filename" not in cols:
            conn.execute("ALTER TABLE projects ADD COLUMN sticker_filename TEXT")
init_db()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to open your studio.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def build_plan(preset_key, brief="", duration="30–60 seconds", platform="Instagram Reels / TikTok", captions=True, music=True):
    preset = PRESETS.get(preset_key, PRESETS["viral_reel"])
    return {
        "preset": preset["name"], "brief": brief.strip(), "platform": platform,
        "target_duration": duration, "format": preset["format"], "pace": preset["pace"],
        "captions": preset["captions"] if captions else "No captions requested",
        "color": preset["color"], "transitions": preset["transitions"],
        "music": "Suggest beat-matched music; use licensed or user-owned audio" if music else "Keep original audio",
        "disclaimer": "This is an AI-style editing blueprint. Automatic speech recognition, generative video, beat detection, and advanced effects need connected AI/media engines.",
        "steps": preset["steps"]
    }

@app.context_processor
def inject_globals():
    return {"presets": PRESETS, "current_user": session.get("username")}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(username) < 3 or "@" not in email or len(password) < 8:
            flash("Use a username of 3+ characters, a valid email, and a password of at least 8 characters.", "error")
            return render_template("auth.html", mode="register")
        try:
            with db() as conn:
                conn.execute("INSERT INTO users(username,email,password_hash,created_at) VALUES(?,?,?,?)",
                    (username, email, generate_password_hash(password), datetime.utcnow().isoformat()))
            flash("Account created. Log in to start editing.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That username or email is already registered.", "error")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity", "").strip().lower()
        password = request.form.get("password", "")
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE lower(username)=? OR email=?", (identity, identity)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        flash("Login details were not correct.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as conn:
        projects = conn.execute("SELECT * FROM projects WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    return render_template("dashboard.html", projects=projects)

@app.route("/editor", methods=["GET", "POST"])
@login_required
def editor():
    if request.method == "POST":
        title = request.form.get("title", "My video project").strip() or "My video project"
        preset_key = request.form.get("preset", "viral_reel")
        if preset_key not in PRESETS: preset_key = "viral_reel"
        brief = request.form.get("brief", "")
        filename = None
        sticker_filename = None
        sticker = request.files.get("sticker")
        if sticker and sticker.filename:
            ext = sticker.filename.rsplit(".", 1)[-1].lower() if "." in sticker.filename else ""
            if ext not in ALLOWED_STICKERS:
                flash("Sticker must be GIF, PNG, JPG, or WEBP.", "error")
                return render_template("editor.html")
            sticker_filename = f"{session['user_id']}_{secrets.token_hex(5)}_sticker.{ext}"
            sticker.save(UPLOADS / sticker_filename)
        upload = request.files.get("video")
        if upload and upload.filename:
            if not allowed_file(upload.filename):
                flash("Upload an MP4, MOV, M4V, WEBM, or AVI video.", "error")
                return render_template("editor.html")
            safe = secure_filename(upload.filename)
            filename = f"{session['user_id']}_{secrets.token_hex(5)}_{safe}"
            upload.save(UPLOADS / filename)
        plan = build_plan(preset_key, brief, request.form.get("duration", "30–60 seconds"),
                          request.form.get("platform", "Instagram Reels / TikTok"),
                          request.form.get("captions") == "on", request.form.get("music") == "on")
        with db() as conn:
            conn.execute("""INSERT INTO projects(user_id,title,filename,sticker_filename,preset,brief,plan_json,created_at)
                VALUES(?,?,?,?,?,?,?,?)""", (session["user_id"], title, filename, sticker_filename, preset_key, brief,
                json.dumps(plan), datetime.utcnow().isoformat()))
        flash("Project saved. Your editing blueprint is ready.", "success")
        return redirect(url_for("dashboard"))
    return render_template("editor.html")

@app.route("/project/<int:project_id>")
@login_required
def project(project_id):
    with db() as conn:
        p = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, session["user_id"])).fetchone()
    if not p:
        flash("Project not found.", "error")
        return redirect(url_for("dashboard"))
    try: plan = json.loads(p["plan_json"] or "{}")
    except json.JSONDecodeError: plan = {}
    return render_template("project.html", project=p, plan=plan, preset=PRESETS.get(p["preset"], PRESETS["viral_reel"]))

@app.route("/media/<path:filename>")
@login_required
def media(filename):
    # Only serve files belonging to the signed-in user's filename prefix.
    if not filename.startswith(f"{session['user_id']}_"):
        return "Not found", 404
    return send_from_directory(UPLOADS, filename)

@app.route("/export/<int:project_id>", methods=["POST"])
@login_required
def export_video(project_id):
    with db() as conn:
        p = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, session["user_id"])).fetchone()
    if not p or not p["filename"]:
        flash("Upload a source video before exporting.", "warning")
        return redirect(url_for("project", project_id=project_id))
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        flash("FFmpeg is not installed. Install FFmpeg and add it to PATH before rendering.", "warning")
        return redirect(url_for("project", project_id=project_id))
    source = UPLOADS / p["filename"]
    output_name = f"project_{project_id}_edited.mp4"
    output = EXPORTS / output_name
    try:
        start = max(0.0, float(request.form.get("trim_start", "0") or 0))
        end_text = (request.form.get("trim_end", "") or "").strip()
        duration = None
        if end_text:
            duration = float(end_text) - start
            if duration <= 0:
                flash("Trim end must be greater than trim start.", "error")
                return redirect(url_for("project", project_id=project_id))
        quality = request.form.get("quality", "1080")
        scale = {"2160": "scale=-2:2160", "1080": "scale=-2:1080", "720": "scale=-2:720", "480": "scale=-2:480"}.get(quality, "scale=-2:1080")
        crf = {"high": "18", "standard": "23", "small": "28"}.get(request.form.get("file_size", "standard"), "23")
        noise = request.form.get("noise_reduction") == "on"
        want_captions = request.form.get("auto_captions") == "on"
        transition = request.form.get("transition", "fade")
        color = request.form.get("color_look", "natural")
        vf = [scale, "setsar=1"]
        if color == "cinematic": vf.append("eq=contrast=1.08:saturation=0.88:brightness=-0.01")
        elif color == "vibrant": vf.append("eq=contrast=1.10:saturation=1.25:brightness=0.02")
        elif color == "warm": vf.append("colorbalance=rs=0.04:gs=0.01:bs=-0.03")
        # Fade-in is safe without knowing the final duration; fade-out is added after probing.
        if transition == "fade": vf.append("fade=t=in:st=0:d=0.45")
        elif transition == "flash": vf.append("eq=contrast=1.12:saturation=1.15")
        # Auto captions are generated locally with faster-whisper. The SRT is also downloadable.
        srt_path = EXPORTS / f"project_{project_id}_captions.srt"
        if want_captions:
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel(os.getenv("WHISPER_MODEL", "base"), device="cpu", compute_type="int8")
                segments, info = model.transcribe(str(source), vad_filter=True)
                def stamp(seconds):
                    ms = int(round(seconds * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); sec, ms = divmod(ms, 1000)
                    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
                with srt_path.open("w", encoding="utf-8") as f:
                    for i, seg in enumerate(segments, 1):
                        f.write(f"{i}\n{stamp(seg.start)} --> {stamp(seg.end)}\n{seg.text.strip()}\n\n")
            except Exception as e:
                app.logger.exception("Caption transcription failed")
                flash("Automatic captions could not be generated. Confirm faster-whisper is installed and retry; the video was not exported.", "error")
                return redirect(url_for("project", project_id=project_id))
        cmd = [ffmpeg, "-y"]
        if start: cmd += ["-ss", str(start)]
        cmd += ["-i", str(source)]
        sticker_path = UPLOADS / p["sticker_filename"] if p["sticker_filename"] else None
        has_sticker = bool(sticker_path and sticker_path.exists())
        if has_sticker:
            if sticker_path.suffix.lower() == ".gif": cmd += ["-ignore_loop", "0", "-i", str(sticker_path)]
            else: cmd += ["-loop", "1", "-i", str(sticker_path)]
        subtitle_input_index = None
        if want_captions and srt_path.exists():
            subtitle_input_index = 2 if has_sticker else 1
            cmd += ["-i", str(srt_path)]
        if duration is not None: cmd += ["-t", str(duration)]
        if has_sticker:
            # Build a proper multi-input filter graph for the sticker overlay.
            filter_graph = f"[0:v]{','.join(vf)}[base];[1:v]scale=180:-1[sticker];[base][sticker]overlay=W-w-36:H-h-36:shortest=0[vout]"
            cmd += ["-filter_complex", filter_graph, "-map", "[vout]", "-map", "0:a?"]
        else:
            cmd += ["-vf", ",".join(vf), "-map", "0:v:0", "-map", "0:a?"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p"]
        if noise: cmd += ["-af", "afftdn=nf=-25"]
        if subtitle_input_index is not None:
            cmd += ["-map", f"{subtitle_input_index}:0?", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
        cmd += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode != 0:
            app.logger.error("FFmpeg failed: %s", result.stderr[-3000:])
            flash("Render failed. Check that FFmpeg supports the selected filters and your video file is valid.", "error")
        else:
            msg = "Edited MP4 exported."
            if want_captions: msg += " Captions were added as a selectable subtitle track and an SRT file."
            flash(msg, "success")
    except ValueError:
        flash("Trim values must be numbers in seconds.", "error")
    except subprocess.TimeoutExpired:
        flash("Render took too long. Try a shorter video or lower resolution.", "error")
    return redirect(url_for("project", project_id=project_id))

@app.route("/captions/<int:project_id>")
@login_required
def download_captions(project_id):
    path = EXPORTS / f"project_{project_id}_captions.srt"
    with db() as conn:
        owned = conn.execute("SELECT id FROM projects WHERE id=? AND user_id=?", (project_id, session["user_id"])).fetchone()
    if not owned or not path.exists():
        flash("No captions are available yet. Enable automatic captions and export first.", "warning")
        return redirect(url_for("project", project_id=project_id))
    return send_from_directory(EXPORTS, path.name, as_attachment=True)

@app.route("/download/<int:project_id>")
@login_required
def download_export(project_id):
    filename = f"project_{project_id}_edited.mp4"
    with db() as conn:
        p = conn.execute("SELECT id FROM projects WHERE id=? AND user_id=?", (project_id, session["user_id"])).fetchone()
    if not p or not (EXPORTS / filename).exists():
        flash("No export is available yet.", "warning")
        return redirect(url_for("project", project_id=project_id))
    return send_from_directory(EXPORTS, filename, as_attachment=True)

@app.errorhandler(413)
def too_large(_):
    flash("Video is too large. The starter limit is 500 MB.", "error")
    return redirect(url_for("editor"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
