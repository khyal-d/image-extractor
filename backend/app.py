import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from worker import new_job, get_job, start_job

load_dotenv()

AWS_BUCKET = (os.environ.get("AWS_BUCKET") or "").strip()
AWS_REGION = (os.environ.get("AWS_REGION") or "us-east-1").strip()
AWS_ACCESS_KEY_ID = (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip()
AWS_SECRET_ACCESS_KEY = (os.environ.get("AWS_SECRET_ACCESS_KEY") or "").strip()
N_OUT = int(os.environ.get("N_OUT") or "50")
PHASH_THRESH = int(os.environ.get("PHASH_THRESH") or "6")
MAKE_PUBLIC = (os.environ.get("MAKE_PUBLIC") or "false").lower() == "true"

if not AWS_BUCKET:
    raise RuntimeError("Missing AWS_BUCKET in .env")
if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise RuntimeError("Missing AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY in .env")

app = Flask(__name__)
CORS(app)


def is_youtube_url(u: str) -> bool:
    u = (u or "").lower()
    return ("youtube.com" in u) or ("youtu.be" in u)


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/generate")
def generate():
    data = request.get_json(force=True) or {}
    url = (data.get("youtubeUrl") or "").strip()
    if not url or not is_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL"}), 400

    job_id = new_job()
    start_job(
        job_id=job_id,
        youtube_url=url,
        bucket=AWS_BUCKET,
        region=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        n_out=N_OUT,
        phash_thresh=PHASH_THRESH,
        make_public=MAKE_PUBLIC,
    )
    return jsonify({"jobId": job_id})


@app.get("/api/jobs/<job_id>")
def job(job_id: str):
    return jsonify(get_job(job_id))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
