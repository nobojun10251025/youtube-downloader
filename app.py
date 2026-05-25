from flask import Flask, render_template_string, request, send_file
import yt_dlp
import os

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Downloader</title>
</head>
<body style="text-align:center; font-family:sans-serif;">
    <h2>🔥 YouTubeダウンローダー</h2>
    <form method="post">
        <input type="text" name="url" placeholder="URLを入力" style="width:300px;">
        <br><br>
        <button type="submit">ダウンロード</button>
    </form>
    <p>{{ message }}</p>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")

        if not url:
            return render_template_string(HTML, message="URLを入力してね")

        filename = "video.mp4"

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            'outtmpl': filename,
            'merge_output_format': 'mp4',
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            return send_file(filename, as_attachment=True)

        except Exception as e:
            return render_template_string(HTML, message=str(e))

    return render_template_string(HTML, message="")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)