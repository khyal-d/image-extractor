import os, re, math, subprocess
from dataclasses import dataclass
from typing import List, Tuple, Optional
from urllib.parse import urlparse, parse_qs

import cv2
import numpy as np
from PIL import Image
import imagehash

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def safe_name(s: str, max_len: int = 80) -> str:
    s = re.sub(r"[\\/:*?\"<>|]+", "_", (s or "")).strip()
    s = re.sub(r"\s+", " ", s)
    return (s[:max_len].strip() or "video")


def video_id_from_url(url: str) -> str:
    u = urlparse(url)
    q = parse_qs(u.query)
    vid = (q.get("v") or [""])[0].strip()
    if vid:
        return vid
    path = (u.path or "").strip("/")
    if path:
        return path.split("/")[-1]
    return "unknown_video"


def yt_title_safe(url: str) -> str:
    try:
        p = subprocess.run(
            ["yt-dlp", "--get-title", "--no-warnings", "--no-playlist", url],
            capture_output=True,
            text=True,
        )
        return (p.stdout or "").strip()
    except Exception:
        return ""


def download_youtube(url: str, out_path: str) -> str:
    if os.path.exists(out_path):
        os.remove(out_path)
    cmd = [
        "yt-dlp",
        "-f",
        "bv*[ext=mp4][height<=480]+ba[ext=m4a]/b[ext=mp4][height<=480]/b",
        "--merge-output-format",
        "mp4",
        "--no-playlist",
        "-o",
        out_path,
        url,
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"yt-dlp failed\n{(p.stderr or p.stdout or '')[:1500]}")
    if not os.path.exists(out_path):
        raise RuntimeError("Download failed: output mp4 not found.")
    return out_path


def get_video_meta(path: str) -> Tuple[float, float, int, int]:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError("Could not open video.")
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if fps <= 0:
        fps = 30.0
    duration = frame_count / fps if frame_count > 0 else 0.0

    if duration <= 0:
        p = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
        )
        if p.returncode == 0 and (p.stdout or "").strip():
            duration = float(p.stdout.strip())

    return float(duration), float(fps), int(w), int(h)


def ts_to_hhmmss(t: float) -> str:
    t = max(0.0, float(t))
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    return f"{h:02d}h{m:02d}m{s:02d}s"


def face_score_simple(img_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
    face_count = int(len(faces))
    h, w = gray.shape[:2]
    max_area_ratio = 0.0
    for (x, y, fw, fh) in faces:
        max_area_ratio = max(max_area_ratio, (fw * fh) / max(1.0, float(w * h)))
    score = 0.9 * math.log1p(face_count) + 1.6 * math.sqrt(max_area_ratio)
    return float(score)


def sharpness_score(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def exposure_score(gray: np.ndarray) -> float:
    mean = float(np.mean(gray))
    return float(math.exp(-((mean - 120.0) ** 2) / (2 * (45.0 ** 2))))


def edge_density_score(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 80, 160)
    return float(np.mean(edges > 0))


def compute_photo_score(img_bgr: np.ndarray) -> float:
    h, w = img_bgr.shape[:2]
    target_w = 640
    if w > target_w:
        new_h = int(h * (target_w / w))
        img_small = cv2.resize(img_bgr, (target_w, new_h), interpolation=cv2.INTER_AREA)
    else:
        img_small = img_bgr

    gray = cv2.cvtColor(img_small, cv2.COLOR_BGR2GRAY)
    sh = sharpness_score(gray)
    ex = exposure_score(gray)
    ed = edge_density_score(gray)

    flat_penalty = 0.0
    mean_gray = float(np.mean(gray))
    if ed < 0.01:
        flat_penalty = 0.6
    if mean_gray < 15 or mean_gray > 245:
        flat_penalty = max(flat_penalty, 0.8)

    fscore = face_score_simple(img_small)

    sh_term = math.log(1.0 + sh) / 8.0
    ed_term = min(1.0, ed * 10.0)
    score = 1.3 * sh_term + 1.0 * ex + 0.8 * ed_term + 1.4 * fscore
    score *= (1.0 - flat_penalty)
    return float(score)


def frame_phash(img_bgr: np.ndarray) -> imagehash.ImageHash:
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    return imagehash.phash(Image.fromarray(img_rgb))


@dataclass
class FrameCandidate:
    bucket_idx: int
    t: float
    score: float
    img_bgr: np.ndarray
    phash: Optional[imagehash.ImageHash] = None


def sample_times_in_bucket(t0: float, t1: float, k: int) -> List[float]:
    if t1 <= t0:
        return [t0]
    k = max(1, int(k))
    eps = (t1 - t0) * 0.08
    a, b = t0 + eps, t1 - eps
    if b <= a:
        a, b = t0, t1
    if k <= 1:
        return [0.5 * (a + b)]
    return [a + (i / (k - 1)) * (b - a) for i in range(k)]


def read_frame_at(cap: cv2.VideoCapture, t: float) -> Optional[np.ndarray]:
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    return frame


def auto_samples_per_bucket(duration_sec: float) -> int:
    if duration_sec <= 3 * 60:
        return 40
    if duration_sec <= 10 * 60:
        return 24
    if duration_sec <= 30 * 60:
        return 16
    if duration_sec <= 120 * 60:
        return 12
    if duration_sec <= 240 * 60:
        return 10
    return 8


def extract_best_frames(
    video_path: str,
    n_out: int = 50,
    samples_per_bucket: Optional[int] = None,
    phash_thresh: int = 6,
):
    duration, fps, w, h = get_video_meta(video_path)
    if samples_per_bucket is None:
        samples_per_bucket = max(4, auto_samples_per_bucket(duration))

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Could not open video with OpenCV.")

    bucket_len = duration / n_out
    bucket_ranges = [(i * bucket_len, (i + 1) * bucket_len) for i in range(n_out)]
    per_bucket = [[] for _ in range(n_out)]

    for i, (t0, t1) in enumerate(bucket_ranges):
        times = sample_times_in_bucket(t0, t1, samples_per_bucket)
        cand_list = []
        for t in times:
            frame = read_frame_at(cap, t)
            if frame is None:
                continue
            cand_list.append(FrameCandidate(i, t, compute_photo_score(frame), frame))

        if not cand_list:
            mid = 0.5 * (t0 + t1)
            frame = read_frame_at(cap, mid)
            if frame is not None:
                cand_list.append(FrameCandidate(i, mid, compute_photo_score(frame), frame))

        cand_list.sort(key=lambda x: x.score, reverse=True)
        per_bucket[i] = cand_list[: max(6, samples_per_bucket)]

    cap.release()

    chosen, chosen_hashes = [], []

    def is_dup(hh):
        return any((hh - ex) <= phash_thresh for ex in chosen_hashes)

    for i in range(n_out):
        if not per_bucket[i]:
            raise RuntimeError("Empty bucket encountered unexpectedly.")

        picked = None
        for cand in per_bucket[i]:
            cand.phash = frame_phash(cand.img_bgr)
            if not is_dup(cand.phash):
                picked = cand
                break

        if picked is None:
            picked = per_bucket[i][0]
            picked.phash = picked.phash or frame_phash(picked.img_bgr)

        chosen.append(picked)
        chosen_hashes.append(picked.phash)

    meta = {
        "duration_sec": duration,
        "width": w,
        "height": h,
        "n_out": n_out,
        "samples_per_bucket": samples_per_bucket,
        "phash_thresh": phash_thresh,
    }
    return chosen, meta


