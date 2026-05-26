from flask import Flask, request, render_template_string, send_file
import os
import shutil
import tempfile
import subprocess
import sys
import traceback
import html
import imageio_ffmpeg
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube MP4 Downloader</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        body {
            font-family: Arial;
            background: #0f0f0f;
            color: white;
            text-align: center;
            margin: 0;
            padding: 20px;
        }

        input {
            width: 85%;
            padding: 12px;
            border-radius: 10px;
            border: none;
            margin-top: 20px;
        }

        button {
            padding: 12px 18px;
            border-radius: 10px;
            border: none;
            background: red;
            color: white;
            margin-top: 15px;
            cursor: pointer;
        }

        .box {
            background: #1f1f1f;
            padding: 15px;
            margin-top: 20px;
            border-radius: 12px;
        }

        iframe {
            width: 100%;
            max-width: 600px;
            height: 320px;
            border: none;
        }

        pre {
            white-space: pre-wrap;
            word-break: break-word;
            text-align: left;
            background: #111;
            padding: 10px;
            border-radius: 10px;
            color: #ddd;
            max-height: 650px;
            overflow-y: auto;
        }

        a {
            color: white;
            text-decoration: none;
        }

        .note {
            font-size: 14px;
            color: #cccccc;
        }
    </style>
</head>

<body>

<h1>YouTube MP4 Downloader</h1>

<form method="POST">
    <input
        type="text"
        name="input"
        placeholder="YouTube URLを貼ってください">

    <br>

    <button type="submit">
        表示
    </button>
</form>

{% if error %}
<div class="box">
    <p>{{ error }}</p>
</div>
{% endif %}

{% if video_id %}
<div class="box">

    <h2>動画</h2>

    <iframe
        src="https://www.youtube.com/embed/{{ video_id }}"
        allowfullscreen>
    </iframe>

    <br>

    <a href="/download?url=https://www.youtube.com/watch?v={{ video_id }}">
        <button>
            MP4ダウンロード
        </button>
    </a>

    <br>

    <a href="/formats-check?url=https://www.youtube.com/watch?v={{ video_id }}">
        <button>
            形式チェック
        </button>
    </a>

    <br>

    <a href="/runtime-check">
        <button>
            Runtime確認
        </button>
    </a>

    <p class="note">
        まず Runtime確認 → 形式チェック → MP4ダウンロード の順で試してください。
    </p>

</div>
{% endif %}

</body>
</html>
"""


@app.errorhandler(Exception)
def handle_exception(e):
    error_text = traceback.format_exc()
    return f"""
    <h2>アプリ内部エラー</h2>
    <pre>{html.escape(error_text)}</pre>
    """, 500


def get_video_id(text):
    if not text:
        return None

    text = text.strip()

    try:
        parsed = urlparse(text)

        if "youtube.com" in parsed.netloc:
            if parsed.path == "/watch":
                query = parse_qs(parsed.query)
                return query.get("v", [None])[0]

            if parsed.path.startswith("/shorts/"):
                return parsed.path.split("/shorts/")[1].split("/")[0]

        if "youtu.be" in parsed.netloc:
            return parsed.path.strip("/").split("/")[0]

    except Exception:
        return None

    return None


def prepare_cookie():
    secret_cookie = "/etc/secrets/cookies.txt"
    cookie_path = "/tmp/cookies.txt"

    if not os.path.exists(secret_cookie):
        return None, "cookies.txt がRenderにありません"

    try:
        shutil.copy(secret_cookie, cookie_path)
    except Exception as e:
        return None, f"cookieコピー失敗: {str(e)}"

    return cookie_path, None


def get_ffmpeg_path():
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def get_deno_path():
    candidates = [
        os.path.expanduser("~/.deno/bin/deno"),
        "/opt/render/.deno/bin/deno",
        "/opt/render/project/.deno/bin/deno",
        "/opt/render/project/src/.deno/bin/deno",
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    return "deno"


def run_command(cmd, timeout=180):
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout
    )

    return result.returncode, result.stdout, result.stderr


def base_ytdlp_cmd(cookie_path):
    deno_path = get_deno_path()

    return [
        sys.executable,
        "-m",
        "yt_dlp",

        "--cookies",
        cookie_path,

        "--no-playlist",

        "--force-ipv4",

        "--js-runtimes",
        f"deno:{deno_path}",

        "--remote-components",
        "ejs:npm",

        "--user-agent",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),

        "--referer",
        "https://www.youtube.com/",
    ]


def add_client_args(cmd, client_name):
    if client_name == "default":
        return cmd

    return cmd + [
        "--extractor-args",
        f"youtube:player_client={client_name}"
    ]


def find_mp4_file(folder):
    found = []

    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(".mp4"):
                found.append(os.path.join(root, file))

    if not found:
        return None

    return max(found, key=os.path.getctime)


def find_any_file(folder):
    found = []

    for root, dirs, files in os.walk(folder):
        for file in files:
            found.append(os.path.join(root, file))

    if not found:
        return None

    return max(found, key=os.path.getctime)


@app.route("/", methods=["GET", "POST"])
def home():
    video_id = None
    error = None

    if request.method == "POST":
        text = request.form.get("input", "").strip()
        video_id = get_video_id(text)

        if not video_id:
            error = "YouTube URLを入力してください"

    return render_template_string(
        HTML,
        video_id=video_id,
        error=error
    )


@app.route("/health")
def health():
    return "OK"


@app.route("/runtime-check")
def runtime_check():
    outputs = []

    commands = [
        ["python version", [sys.executable, "--version"]],
        ["yt-dlp version", [sys.executable, "-m", "yt_dlp", "--version"]],
        ["deno version", [get_deno_path(), "--version"]],
    ]

    for title, cmd in commands:
        try:
            code, stdout, stderr = run_command(cmd, timeout=60)

            outputs.append(
                f"""
==============================
{title}
return code: {code}
==============================
STDOUT:
{stdout}

STDERR:
{stderr}
"""
            )

        except Exception as e:
            outputs.append(
                f"""
==============================
{title}
ERROR
==============================
{str(e)}
"""
            )

    ffmpeg_path = get_ffmpeg_path()

    outputs.append(
        f"""
==============================
ffmpeg
==============================
{ffmpeg_path}
exists: {os.path.exists(ffmpeg_path) if ffmpeg_path else False}

==============================
deno path used
==============================
{get_deno_path()}
"""
    )

    return f"""
    <h2>Runtime Check</h2>
    <pre>{html.escape(''.join(outputs))}</pre>
    """


@app.route("/cookie-check")
def cookie_check():
    secret_cookie = "/etc/secrets/cookies.txt"

    if not os.path.exists(secret_cookie):
        return "NG: /etc/secrets/cookies.txt が存在しません"

    size = os.path.getsize(secret_cookie)

    with open(secret_cookie, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    has_youtube = "youtube.com" in text
    has_google = "google.com" in text
    has_sid = "SID" in text or "__Secure" in text
    starts_ok = "# Netscape HTTP Cookie File" in text[:200]

    return f"""
    <h2>Cookie Check</h2>
    <p>file: OK</p>
    <p>size: {size} bytes</p>
    <p>Netscape形式: {starts_ok}</p>
    <p>youtube.com cookieあり: {has_youtube}</p>
    <p>google.com cookieあり: {has_google}</p>
    <p>ログイン系cookieらしきものあり: {has_sid}</p>
    """


@app.route("/ffmpeg-check")
def ffmpeg_check():
    ffmpeg_path = get_ffmpeg_path()

    if not ffmpeg_path:
        return "ffmpeg NG"

    if os.path.exists(ffmpeg_path):
        return f"ffmpeg OK: {ffmpeg_path}"

    return "ffmpeg NG: ファイルが存在しません"


@app.route("/formats-check")
def formats_check():
    url = request.args.get("url")

    if not url:
        return "URLがありません"

    cookie_path, cookie_error = prepare_cookie()

    if cookie_error:
        return cookie_error

    clients = [
        "android_vr",
        "web",
        "ios",
        "android",
        "default"
    ]

    outputs = []

    for client in clients:
        cmd = base_ytdlp_cmd(cookie_path)
        cmd = add_client_args(cmd, client)

        cmd = cmd + [
            "-F",
            url
        ]

        try:
            code, stdout, stderr = run_command(cmd, timeout=180)

            output = stdout + "\n" + stderr

            outputs.append(
                f"""
==============================
CLIENT: {client}
RETURN CODE: {code}
==============================
COMMAND:
{' '.join(cmd)}

OUTPUT:
{output}
"""
            )

            if (
                " mp4 " in output
                or " m4a " in output
                or " webm " in output
                or "audio only" in output
                or "video only" in output
            ):
                break

        except subprocess.TimeoutExpired:
            outputs.append(
                f"""
==============================
CLIENT: {client}
TIMEOUT
==============================
"""
            )

        except Exception as e:
            outputs.append(
                f"""
==============================
CLIENT: {client}
ERROR
==============================
{str(e)}
"""
            )

    final_output = "".join(outputs)

    if len(final_output) > 60000:
        final_output = final_output[:60000] + "\n\n--- 出力が長すぎるため省略 ---"

    return f"""
    <h2>Formats Check</h2>
    <pre>{html.escape(final_output)}</pre>
    """


@app.route("/download")
def download():
    url = request.args.get("url")

    if not url:
        return "URLがありません"

    cookie_path, cookie_error = prepare_cookie()

    if cookie_error:
        return cookie_error

    ffmpeg_path = get_ffmpeg_path()

    if not ffmpeg_path:
        return "ffmpegが取得できません"

    temp_dir = tempfile.mkdtemp(prefix="yt_")
    output_path = os.path.join(temp_dir, "%(id)s.%(ext)s")

    clients = [
        "android_vr",
        "web",
        "ios",
        "android",
        "default"
    ]

    format_patterns = [
        "137+140/136+140/135+140/134+140/18",
        "136+140/135+140/134+140/18",
        "134+140/18",
        "18",
        "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best"
    ]

    errors = []

    for client in clients:
        for fmt in format_patterns:
            cmd = base_ytdlp_cmd(cookie_path)
            cmd = add_client_args(cmd, client)

            cmd = cmd + [
                "--ffmpeg-location",
                ffmpeg_path,

                "-f",
                fmt,

                "--merge-output-format",
                "mp4",

                "-o",
                output_path,

                url
            ]

            try:
                code, stdout, stderr = run_command(cmd, timeout=300)

                if code == 0:
                    mp4_file = find_mp4_file(temp_dir)

                    if mp4_file and os.path.exists(mp4_file):
                        video_id = get_video_id(url) or "video"

                        return send_file(
                            mp4_file,
                            as_attachment=True,
                            download_name=f"{video_id}.mp4"
                        )

                    any_file = find_any_file(temp_dir)

                    if any_file:
                        errors.append(
                            f"client={client}, format={fmt}: mp4なし。生成ファイル: {os.path.basename(any_file)}"
                        )
                    else:
                        errors.append(
                            f"client={client}, format={fmt}: 成功扱いだがファイルなし"
                        )

                else:
                    errors.append(
                        f"""
client={client}
format={fmt}
return code={code}
STDOUT:
{stdout}
STDERR:
{stderr}
"""
                    )

            except subprocess.TimeoutExpired:
                errors.append(
                    f"client={client}, format={fmt}: タイムアウト"
                )

            except Exception as e:
                errors.append(
                    f"client={client}, format={fmt}: 例外 {str(e)}"
                )

    error_output = "\n".join(errors)

    if len(error_output) > 60000:
        error_output = error_output[:60000] + "\n\n--- エラー出力が長すぎるため省略 ---"

    return f"""
    <h2>DL失敗</h2>
    <p>すべてのclient / formatで失敗しました。</p>
    <p>Runtime確認と形式チェックの結果を確認してください。</p>
    <pre>{html.escape(error_output)}</pre>
    """


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )
