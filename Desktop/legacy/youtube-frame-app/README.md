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
AWS_BUCKET=your-bucket-name
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

```
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:5173

## Usage

1. Start the backend and frontend
2. Open http://localhost:5173 in your browser
3. Paste a YouTube link and click **Generate Images**
4. Wait a few minutes while frames are extracted and uploaded to S3
5. View and download the generated frames

## Notes

- Do NOT share or commit your `.env` file — it contains your AWS credentials
- The `.env` file is already excluded from git via `.gitignore`
- Processing time depends on video length (typically 3–10 minutes)
