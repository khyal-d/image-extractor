# YouTube → 50 Frames

Paste a YouTube link, generate 50 best frames, and view images saved in AWS S3.

## Prerequisites

Install these once on your system:

- [Python 3.x](https://www.python.org/downloads/)
- [Node.js](https://nodejs.org/)
- FFmpeg (includes ffprobe):
  ```
  winget install ffmpeg
  ```

## Setup

### 1. Backend

```
cd backend
pip install -r requirements.txt
```

Create a `backend/.env` file with your AWS credentials:

```
AWS_BUCKET=your-s3-bucket-name
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
N_OUT=50
PHASH_THRESH=6
MAKE_PUBLIC=true
```

Run the backend:

```
python app.py
```

Backend runs on http://127.0.0.1:8000

### 2. Frontend

Open a new terminal:

```
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:5173

## Usage

1. Start both backend and frontend
2. Open http://localhost:5173 in your browser
3. Paste a YouTube link and click **Generate Images**
4. Wait while frames are extracted and uploaded to S3 (3–10 minutes depending on video length)
5. View and download the generated frames in the gallery

## How It Works

1. Backend downloads the YouTube video using `pytubefix`
2. Video is split into 50 equal time buckets
3. Best frame per bucket is selected based on sharpness, exposure, and face detection
4. Frames are uploaded to your AWS S3 bucket
5. Frontend polls the backend every 1.5 seconds for progress updates
6. Gallery displays all 50 frames with timestamps once done

## Progress Breakdown

| Progress | What Happens |
|---|---|
| 2% | Job starts, status set to `running` |
| 6% | Video title fetched, S3 folder prefix created |
| 10% | `youtube_link.txt` uploaded to S3 |
| 25% | Video fully downloaded via pytubefix |
| 40% | 50 best frames extracted (scored by sharpness, exposure, face detection) |
| 40–85% | Each frame encoded as JPEG and uploaded to S3 one by one |
| 85–99% | `timestamps.json` and zip file built and uploaded to S3 |
| 100% | Job marked `done` — gallery is ready |

## Notes

- Do NOT share or commit your `.env` file — it contains your AWS credentials
- The `.env` file is already excluded from git via `.gitignore`
- The video is downloaded temporarily and deleted immediately after frame extraction
- Frames, a zip file, and a timestamps.json are saved in S3 under a folder named after the video
