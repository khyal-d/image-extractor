import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";

const API = "http://127.0.0.1:8000";

export default function App() {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState(null);
  const timerRef = useRef(null);

  const status = job?.status || "idle";
  const progress = job?.progress ?? 0;

  async function onGenerate() {
    setJob(null);
    setJobId("");
    const { data } = await axios.post(`${API}/api/generate`, { youtubeUrl });
    setJobId(data.jobId);
  }

  useEffect(() => {
    if (!jobId) return;

    async function poll() {
      const { data } = await axios.get(`${API}/api/jobs/${jobId}`);
      setJob(data);
      if (data.status === "done" || data.status === "error") {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    poll();
    timerRef.current = setInterval(poll, 1500);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
    };
  }, [jobId]);

  const images = useMemo(() => job?.images || [], [job]);

  return (
    <div style={{ maxWidth: 1100, margin: "40px auto", padding: 16, fontFamily: "system-ui" }}>
      <h1 style={{ marginBottom: 8 }}>YouTube → 50 Frames</h1>
      <p style={{ marginTop: 0, color: "#555" }}>
        Paste a YouTube link, generate frames, and view images saved in AWS S3.
      </p>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 18 }}>
        <input
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=..."
          style={{ flex: 1, padding: 12, borderRadius: 10, border: "1px solid #ddd" }}
        />
        <button
          onClick={onGenerate}
          disabled={!youtubeUrl || status === "running" || status === "queued"}
          style={{ padding: "12px 16px", borderRadius: 10, border: "1px solid #ddd", cursor: "pointer" }}
        >
          Generate Images
        </button>
      </div>

      {job && (
        <div style={{ marginTop: 18, padding: 14, border: "1px solid #eee", borderRadius: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div>
              <div><b>Status:</b> {job.status}</div>
              <div><b>Progress:</b> {progress}%</div>
              {job.error && <div style={{ color: "crimson" }}><b>Error:</b> {job.error}</div>}
            </div>
            {job.folderLink && (
              <a href={job.folderLink} target="_blank" rel="noreferrer">
                Open S3 Folder
              </a>
            )}
          </div>

          <div style={{ height: 10, background: "#f2f2f2", borderRadius: 999, marginTop: 12 }}>
            <div style={{ width: `${progress}%`, height: "100%", background: "#111", borderRadius: 999 }} />
          </div>
        </div>
      )}

      {status === "done" && (
        <div style={{ marginTop: 18 }}>
          <h2 style={{ marginBottom: 10 }}>Gallery ({images.length})</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
            {images.map((img) => (
              <a
                key={img.key}
                href={img.url}
                target="_blank"
                rel="noreferrer"
                style={{ textDecoration: "none", color: "inherit" }}
                title={img.filename}
              >
                <div style={{ border: "1px solid #eee", borderRadius: 12, overflow: "hidden" }}>
                  <img
                    src={img.thumbUrl || img.url}
                    alt={img.filename}
                    style={{ width: "100%", aspectRatio: "1 / 1", objectFit: "cover", display: "block" }}
                    loading="lazy"
                  />
                  <div style={{ padding: 8, fontSize: 12 }}>
                    <div style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {img.filename}
                    </div>
                    {typeof img.timestampSec === "number" && (
                      <div style={{ color: "#666" }}>t={img.timestampSec.toFixed(1)}s</div>
                    )}
                  </div>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}