from flask import Flask, request, render_template_string, send_file
import yt_dlp
import os

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube軽量アプリ</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial;
            background: #0f0f0f;
            color: white;
            text-align: center;
            margin: 0;
        }

        h1 { padding: 10px; }

        input {
            width: 80%;
            padding: 10px;
            border-radius: 10px;
            border: none;
        }

        button {
            padding: 10px 15px;
            border-radius: 10px;
            border: none;
            background: red;
            color: white;
            margin-top: 10px;
        }

        .video {
            background: #1f1f1f;
            margin: 10px;
            padding: 10px;
            border-radius: 10px;
        }

        img {
            width: 100%;
            border-radius: 10px;
        }

        iframe {
            width: 100%;
            height: 240px;
        }
    </style>
</head>
<body>

<h1>YouTube軽量アプリ</h1>

<form method="POST">
    <input type="text" name="input" placeholder="URL or 検索ワード">
    <br>
    <button type="submit">検索</button>
</form>

{% if video_id %}
    <h2>再生中</h2>
    <iframe src="https://www.youtube.com/embed/{{ video_id }}" allowfullscreen></iframe>

    <br>
    <a href="/download?url=https://www.youtube.com/watch?v={{ video_id }}">
        <button>MP4ダウンロード</button>
    </a>
{% endif %}

{% if videos %}
    <h2>検索結果</h2>
    {% for v in videos %}
        <div class="video">
            <p>{{ v.title }}</p>
            <img src="{{ v.thumbnail }}">

            <br><br>

            <a href="/watch?v={{ v.id }}">
                <button>再生</button>
            </a>

            <a href="/download?url=https://www.youtube.com/watch?v={{ v.id }}">
                <button>DL</button>
            </a>
        </div>
    {% endfor %}
{% endif %}

</body>
</html>
"""

PLAYER_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { background: black; color: white; text-align: center; }
iframe { width: 100%; height: 250px; }
button { padding: 10px; margin-top: 20px; }
</style>
</head>
<body>

<h2>動画再生</h2>

<iframe src="https://www.youtube.com/embed/{{ video_id }}" allowfullscreen></iframe>

<br>
<a href="/"><button>戻る</button></a>

</body>
</html>
"""


def get_video_id(text):
    if "youtube.com/watch?v=" in text:
        return text.split("v=")[1].split("&")[0]
    if "youtu.be/" in text:
        return text.split("youtu.be/")[1]
    return None


@app.route("/", methods=["GET", "POST"])
def home():
    videos = None
    video_id = None

    if request.method == "POST":
        text = request.form["input"]

        video_id = get_video_id(text)

        if not video_id:
            ydl_opts = {"quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(f"ytsearch5:{text}", download=False)

                videos = []
                for e in result["entries"]:
                    videos.append({
                        "title": e.get("title"),
                        "thumbnail": e.get("thumbnail"),
                        "id": e.get("id")
                    })

    return render_template_string(HTML, videos=videos, video_id=video_id)


@app.route("/watch")
def watch():
    vid = request.args.get("v")
    return render_template_string(PLAYER_HTML, video_id=vid)


@app.route("/download")
def download():
    url = request.args.get("url")

    ydl_opts = {
        "format": "bv*+ba/best",
        "merge_output_format": "mp4",
        "outtmpl": "/tmp/%(id)s.%(ext)s",

        # 軽量化
        "quiet": True,
        "no_warnings": True,

        # Render対策リトライ
        "retries": 10,
        "fragment_retries": 10,

        # 回避系（重要）
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },

        # 最低限ヘッダー
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12)",
            "Accept-Language": "ja,en-US;q=0.9",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            file_path = ydl.prepare_filename(info)
            file_path = os.path.splitext(file_path)[0] + ".mp4"

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        return f"エラー: {str(e)}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
