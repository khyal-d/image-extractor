import os
import uuid
import json
import io
import zipfile
import tempfile
import cv2
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from s3_client import (
    build_s3,
    s3_upload_bytes,
    s3_object_url,
    s3_public_url,
)
from frame_extract import (
    video_id_from_url,
    yt_title_safe,
    safe_name,
    ts_to_hhmmss,
    download_youtube,
    extract_best_frames,
)

EXEC = ThreadPoolExecutor(max_workers=2)
JOBS: Dict[str, Dict[str, Any]] = {}


def new_job() -> str:
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "status": "queued",
        "progress": 0,
        "error": None,
        "prefix": None,
        "folderLink": None,
        "images": [],
    }
    return job_id


def get_job(job_id: str) -> Dict[str, Any]:
    return JOBS.get(job_id, {"status": "not_found"})


def _set(job_id: str, **kw):
    if job_id in JOBS:
        JOBS[job_id].update(kw)


def start_job(
    job_id: str,
    youtube_url: str,
    bucket: str,
    region: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    n_out: int = 50,
    phash_thresh: int = 6,
    make_public: bool = False,
):
    EXEC.submit(
        _run_job,
        job_id,
        youtube_url,
        bucket,
        region,
        aws_access_key_id,
        aws_secret_access_key,
        n_out,
        phash_thresh,
        make_public,
    )


def _run_job(
    job_id: str,
    youtube_url: str,
    bucket: str,
    region: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    n_out: int,
    phash_thresh: int,
    make_public: bool,
):
    s3 = build_s3(aws_access_key_id, aws_secret_access_key, region)
    tmp_fd, video_path = tempfile.mkstemp(suffix=".mp4")
    os.close(tmp_fd)

    try:
        _set(job_id, status="running", progress=2)

        vid = video_id_from_url(youtube_url)
        title = safe_name(yt_title_safe(youtube_url), 40) or vid
        prefix = safe_name(f"{vid}_{title}", 80) + "/"

        _set(job_id, prefix=prefix, progress=6)

        # Upload youtube link directly from memory
        link_bytes = (youtube_url.strip() + "\n").encode("utf-8")
        s3_upload_bytes(s3, link_bytes, bucket, prefix + "youtube_link.txt", "text/plain", make_public)

        _set(job_id, progress=10)

        # Download video to a single temp file (unavoidable with yt-dlp)
        download_youtube(youtube_url, video_path)

        _set(job_id, progress=25)

        chosen, meta = extract_best_frames(
            video_path, n_out=n_out, samples_per_bucket=None, phash_thresh=phash_thresh
        )

        # Delete video immediately — frames are already in memory as numpy arrays
        os.remove(video_path)
        video_path = None

        _set(job_id, progress=40)

        images: List[Dict[str, Any]] = []
        frames_manifest = []
        frame_bytes_list = []  # (filename, bytes) kept in memory for zip
        total = max(1, len(chosen))

        for i, c in enumerate(chosen, start=1):
            fn = f"{i:03d}_{ts_to_hhmmss(c.t)}.jpg"

            # Encode JPEG in memory — no disk write
            _, buf = cv2.imencode(".jpg", c.img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            jpeg_bytes = buf.tobytes()

            key = prefix + fn
            s3_upload_bytes(s3, jpeg_bytes, bucket, key, "image/jpeg", make_public)

            frame_bytes_list.append((fn, jpeg_bytes))
            frames_manifest.append({
                "index": i,
                "timestamp_sec": float(c.t),
                "filename": fn,
                "score": float(c.score),
                "bucket_idx": int(c.bucket_idx),
            })
            images.append({
                "key": key,
                "filename": fn,
                "timestampSec": float(c.t),
                "score": float(c.score),
                "url": s3_object_url(s3, bucket, region, key, make_public),
                "thumbUrl": s3_object_url(s3, bucket, region, key, make_public),
            })

            prog = 40 + int((i / total) * 45)
            _set(job_id, progress=min(85, prog))

        # Build and upload timestamps.json from memory
        ts_bytes = json.dumps({"meta": meta, "frames": frames_manifest}, indent=2).encode("utf-8")
        s3_upload_bytes(s3, ts_bytes, bucket, prefix + "timestamps.json", "application/json", make_public)

        # Build and upload zip from memory
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn, data in frame_bytes_list:
                zf.writestr(fn, data)
            zf.writestr("timestamps.json", ts_bytes)
        s3_upload_bytes(s3, zip_buf.getvalue(), bucket, prefix + f"{vid}_frames.zip", "application/zip", make_public)

        folder_link = s3_public_url(bucket, region, prefix) if make_public else None
        _set(job_id, images=images, folderLink=folder_link, status="done", progress=100)

    except Exception as e:
        _set(job_id, status="error", error=str(e), progress=100)
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
