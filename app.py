from flask import Flask, request, render_template_string, send_file
import yt_dlp
import os
import glob
import shutil
import imageio_ffmpeg

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

    if "youtube.com/watch?v=" in text:
        return text.split("v=")[1].split("&")[0]

    if "youtu.be/" in text:
        return text.split("youtu.be/")[1].split("?")[0]

    if "youtube.com/shorts/" in text:
        return text.split("shorts/")[1].split("?")[0]

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
        <p>youtube.com / google.com / ログイン系cookie が True ならかなりOKです。</p>
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

    output_template = "/tmp/%(id)s.%(ext)s"

    ydl_opts = {
        # まずmp4動画+m4a音声を優先。
        # なければ取れる形式を落として、ffmpegでmp4へ変換する。
        "format": (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo+bestaudio/"
            "18/"
            "best"
        ),

        "outtmpl": output_template,

        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,

        "cookiefile": cookie_path,

        "ffmpeg_location": ffmpeg_path,

        # 結合時の出力コンテナをmp4へ
        "merge_output_format": "mp4",

        # 最終ファイルをmp4へ変換
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4"
            }
        ],

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        },

        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 1,
    }

    try:
        before_files = set(glob.glob("/tmp/*"))

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                url,
                download=True
            )

        video_id = info.get("id")

        # mp4優先で探す
        mp4_files = glob.glob(f"/tmp/{video_id}.mp4")

        if mp4_files:
            file_path = max(
                mp4_files,
                key=os.path.getctime
            )
        else:
            after_files = set(glob.glob("/tmp/*"))
            new_files = list(after_files - before_files)

            if not new_files:
                possible_files = glob.glob(f"/tmp/{video_id}.*")

                if possible_files:
                    file_path = max(
                        possible_files,
                        key=os.path.getctime
                    )
                else:
                    return "DL失敗：ファイルが生成されませんでした"
            else:
                file_path = max(
                    new_files,
                    key=os.path.getctime
                )

        if not os.path.exists(file_path):
            return "DL失敗：ファイル未発見"

        # 念のため、mp4以外ならエラー表示
        if not file_path.endswith(".mp4"):
            return f"MP4変換失敗：生成ファイルは {os.path.basename(file_path)} でした"

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
