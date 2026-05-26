from flask import Flask, request, render_template_string, send_file
import yt_dlp
import os
import glob
import shutil

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
    </style>
</head>
<body>

<h1>YouTube MP4 Downloader</h1>

<form method="POST">
    <input type="text" name="input" placeholder="YouTube URLを貼ってください">
    <br>
    <button type="submit">表示</button>
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
        <button>MP4ダウンロード</button>
    </a>
</div>
{% endif %}

</body>
</html>
"""


def get_video_id(text):
    if not text:
        return None

    if "youtube.com/watch?v=" in text:
        return text.split("v=")[1].split("&")[0]

    if "youtu.be/" in text:
        return text.split("youtu.be/")[1].split("?")[0]

    if "youtube.com/shorts/" in text:
        return text.split("shorts/")[1].split("?")[0]

    return None


@app.route("/", methods=["GET", "POST"])
def home():
    video_id = None
    error = None

    if request.method == "POST":
        text = request.form.get("input", "").strip()

        video_id = get_video_id(text)

        if not video_id:
            error = "YouTubeのURLを入力してください"

    return render_template_string(
        HTML,
        video_id=video_id,
        error=error
    )


@app.route("/download")
def download():
    url = request.args.get("url")

    if not url:
        return "URLがありません"

    # Render Secret File
    secret_cookie = "/etc/secrets/cookies.txt"

    # 書き込み可能領域へコピー
    cookie_path = "/tmp/cookies.txt"

    if not os.path.exists(secret_cookie):
        return "cookies.txtがRenderに設定されていません"

    try:
        shutil.copy(secret_cookie, cookie_path)
    except Exception as e:
        return f"cookieコピー失敗: {str(e)}"

    ydl_opts = {
        "format": (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "best[ext=mp4]/best"
        ),

        "merge_output_format": "mp4",

        "outtmpl": "/tmp/%(id)s.%(ext)s",

        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,

        "cookiefile": cookie_path,

        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),

            "Accept-Language":
                "ja,en-US;q=0.9,en;q=0.8",
        },

        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 1,
    }

    try:
        before_files = set(glob.glob("/tmp/*"))

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        video_id = info.get("id")

        files = glob.glob(f"/tmp/{video_id}.*")

        mp4_files = [
            f for f in files if f.endswith(".mp4")
        ]

        if mp4_files:
            file_path = mp4_files[0]

        else:
            after_files = set(glob.glob("/tmp/*"))

            new_files = list(after_files - before_files)

            if not new_files:
                return "DL失敗：ファイル生成なし"

            file_path = new_files[0]

        if not os.path.exists(file_path):
            return "DL失敗：ファイル未発見"

        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"{video_id}.mp4"
        )

    except Exception as e:
        return f"DLエラー: {str(e)}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )
