from flask import Flask, request, render_template_string, send_file
import os
import shutil
import tempfile
import subprocess
import sys
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

        .note {
            font-size: 14px;
            color: #cccccc;
        }

        pre {
            white-space: pre-wrap;
            word-break: break-word;
            text-align: left;
            background: #111;
            padding: 10px;
            border-radius: 10px;
            color: #ddd;
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

    <p class="note">
        動画によっては変換に少し時間がかかります。
    </p>

</div>
{% endif %}

</body>
</html>
"""


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


def find_mp4_file(folder):
    found = []

    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(".mp4"):
                found.append(os.path.join(root, file))

    if not found:
        return None

    return max(found, key=os.path.getctime)


def run_command(cmd, timeout=300):
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout
    )

    return result.returncode, result.stdout, result.stderr


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


@app.route("/cookie-check")
def cookie_check():
    secret_cookie = "/etc/secrets/cookies.txt"

    if not os.path.exists(secret_cookie):
        return "NG: /etc/secrets/cookies.txt が存在しません"

    try:
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
        <hr>
        <p>youtube.com / google.com / ログイン系cookie が True ならOK寄りです。</p>
        """

    except Exception as e:
        return f"NG: cookie確認中にエラー: {str(e)}"


@app.route("/ffmpeg-check")
def ffmpeg_check():
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

        if os.path.exists(ffmpeg_path):
            return f"ffmpeg OK: {ffmpeg_path}"

        return "ffmpeg NG: パスは取得できましたが、ファイルが存在しません"

    except Exception as e:
        return f"ffmpeg NG: {str(e)}"


@app.route("/formats-check")
def formats_check():
    url = request.args.get("url")

    if not url:
        return "URLがありません"

    cookie_path, cookie_error = prepare_cookie()

    if cookie_error:
        return cookie_error

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--cookies",
        cookie_path,
        "--no-playlist",
        "--no-warnings",
        "-F",
        url
    ]

    try:
        code, stdout, stderr = run_command(cmd, timeout=120)

        output = stdout + "\n" + stderr

        if not output.strip():
            output = "出力が空です"

        return f"""
        <h2>Formats Check</h2>
        <p>return code: {code}</p>
        <pre>{output}</pre>
        """

    except Exception as e:
        return f"formats確認エラー: {str(e)}"


@app.route("/download")
def download():
    url = request.args.get("url")

    if not url:
        return "URLがありません"

    cookie_path, cookie_error = prepare_cookie()

    if cookie_error:
        return cookie_error

    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        return f"ffmpeg取得エラー: {str(e)}"

    temp_dir = tempfile.mkdtemp(prefix="yt_")
    output_path = os.path.join(temp_dir, "%(id)s.%(ext)s")

    # 成功率優先で複数パターン試す
    format_patterns = [
        "best*",
        "best",
        "bv*+ba/best",
        "18/best"
    ]

    errors = []

    for fmt in format_patterns:
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",

            "--cookies",
            cookie_path,

            "--no-playlist",
            "--no-warnings",

            "--ffmpeg-location",
            ffmpeg_path,

            "-f",
            fmt,

            "--merge-output-format",
            "mp4",

            "--recode-video",
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

                errors.append(
                    f"format={fmt}: コマンド成功したがmp4ファイルなし\n{stdout}\n{stderr}"
                )

            else:
                errors.append(
                    f"format={fmt}: 失敗\n{stdout}\n{stderr}"
                )

        except subprocess.TimeoutExpired:
            errors.append(f"format={fmt}: タイムアウト")
        except Exception as e:
            errors.append(f"format={fmt}: 例外 {str(e)}")

    return f"""
    <h2>DL失敗</h2>
    <p>すべてのformatパターンで失敗しました。</p>
    <p>この動画はRender環境から形式一覧を取得できていない可能性が高いです。</p>
    <hr>
    <pre>{chr(10).join(errors)}</pre>
    """


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )
