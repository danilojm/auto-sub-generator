# FastAPI and dependencies
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Utility libraries
from pydantic import BaseModel
import yt_dlp
import whisper
import os
import tempfile
import uuid
from pathlib import Path
import json
from deep_translator import GoogleTranslator
import re
import shutil
from typing import Optional
import time

# Initialize the FastAPI app
app = FastAPI(title="Subtitle Generator API")

# Serve static files (e.g., frontend)
app.mount("/static", StaticFiles(directory="../static"), name="static")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dictionary to track job statuses
job_status_storage = {}

# Load the Whisper model
try:
    whisper_model = whisper.load_model("base")
    print("[INFO] Whisper model loaded successfully.")
except Exception as e:
    print(f"[ERROR] Failed to load Whisper model: {e}")
    whisper_model = None  # Optional: you could stop the app here

# Data model for incoming POST requests
class VideoRequest(BaseModel):
    video_url: str
    source_lang: str = "auto"
    target_lang: str = "pt"

# Helper to update job status in memory
def update_job_status(job_id: str, status: str, progress: int, message: str, download_url: str = None):
    try:
        job_status_storage[job_id] = {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "message": message,
            "download_url": download_url,
            "timestamp": time.time()
        }
        print(f"[STATUS UPDATE] Job {job_id}: {status} - {progress}% - {message}")
    except Exception as e:
        print(f"[ERROR] Failed to update job status {job_id}: {e}")

# Download and convert video audio to WAV
def download_audio(video_url: str, output_dir: str) -> Optional[str]:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/audio.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'quiet': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        audio_path = f"{output_dir}/audio.wav"
        if not os.path.exists(audio_path):
            raise Exception("Audio file not found after download.")
        print(f"[INFO] Audio successfully downloaded to {audio_path}")
        return audio_path
    except Exception as e:
        print(f"[ERROR] Audio download failed: {e}")
        return None

# Format float seconds to SRT timestamp
def format_timestamp(seconds: float) -> str:
    try:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")
    except Exception as e:
        print(f"[ERROR] Failed to format timestamp: {e}")
        return "00:00:00,000"

# Transcribe audio using Whisper
def transcribe_audio(audio_path: str) -> str:
    if whisper_model is None:
        raise Exception("Whisper model is not loaded.")
    try:
        result = whisper_model.transcribe(audio_path)
        srt_content = []
        for i, segment in enumerate(result["segments"], 1):
            start_time = format_timestamp(segment["start"])
            end_time = format_timestamp(segment["end"])
            text = segment["text"].strip()
            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(text)
            srt_content.append("")
        print(f"[INFO] Transcription completed successfully.")
        return "\n".join(srt_content)
    except Exception as e:
        print(f"[ERROR] Audio transcription failed: {e}")
        raise

# Translate SRT subtitles
def translate_srt(srt_content: str, target_lang: str = "pt") -> str:
    if not srt_content.strip():
        return ""
    try:
        blocks = re.split(r"\n\s*\n", srt_content.strip())
        translated_blocks = []
        translator = GoogleTranslator(source='auto', target=target_lang)
        for block in blocks:
            if not block.strip():
                continue
            lines = block.split("\n")
            if len(lines) >= 3:
                index = lines[0]
                timecode = lines[1]
                text_lines = lines[2:]
                original_text = " ".join(text_lines)
                try:
                    translated_text = translator.translate(original_text)
                    translated_block = f"{index}\n{timecode}\n{translated_text}"
                    translated_blocks.append(translated_block)
                except Exception as e:
                    print(f"[WARN] Failed to translate block. Keeping original. Error: {e}")
                    translated_blocks.append(block)
            else:
                translated_blocks.append(block)
        print(f"[INFO] Translation completed successfully.")
        return "\n\n".join(translated_blocks)
    except Exception as e:
        print(f"[ERROR] Translation error: {e}")
        raise

# Complete processing pipeline: download, transcribe, translate, save
def process_video(job_id: str, video_url: str, target_lang: str):
    print(f"[PROCESSING] Starting job {job_id}")
    
    temp_dir = "../temp"
    os.makedirs(temp_dir, exist_ok=True)
    try:
        update_job_status(job_id, "processing", 10, "Downloading video audio...")
        audio_path = download_audio(video_url, temp_dir)
        if not audio_path or not os.path.exists(audio_path):
            raise Exception("Failed to download audio from video.")

        update_job_status(job_id, "processing", 40, "Transcribing audio...")
        srt_content = transcribe_audio(audio_path)
        if not srt_content.strip():
            raise Exception("Transcription failed.")

        update_job_status(job_id, "processing", 70, "Translating subtitles...")
        translated_srt = translate_srt(srt_content, target_lang)

        update_job_status(job_id, "processing", 90, "Saving subtitle file...")
        downloads_dir = "../downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        output_file = f"{downloads_dir}/subtitles_{job_id}.srt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(translated_srt)

        download_url = f"/download/{job_id}"
        update_job_status(job_id, "completed", 100, "Processing completed successfully!", download_url)
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"[ERROR] {error_msg}")
        update_job_status(job_id, "error", 0, error_msg)
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"[INFO] Temporary directory removed.")
            except Exception as e:
                print(f"[WARN] Failed to remove temporary directory: {e}")

# API endpoint to start background subtitle generation
@app.post("/generate-subtitles")
async def generate_subtitles(request: VideoRequest, background_tasks: BackgroundTasks):
    try:
        job_id = str(uuid.uuid4())
        update_job_status(job_id, "pending", 0, "Waiting for processing to start...")
        background_tasks.add_task(process_video, job_id, request.video_url, request.target_lang)
        return {"job_id": job_id, "message": "Processing started"}
    except Exception as e:
        print(f"[ERROR] Failed to start processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during processing start")

# API endpoint to check job status
@app.get("/status/{job_id}")
def get_job_status(job_id: str):
    try:
        print(f"Checking status for job: {job_id}")
        if job_id not in job_status_storage:
            raise HTTPException(status_code=404, detail="Job not found")
        
        print(f"Job {job_id} status: {job_status_storage[job_id]}")
        return job_status_storage[job_id]
    except Exception as e:
        print(f"[ERROR] Failed to retrieve job status {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal error retrieving status")

# API endpoint to download subtitles
@app.get("/download/{job_id}")
async def download_subtitle(job_id: str):
    try:
        file_path = f"../downloads/subtitles_{job_id}.srt"
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(
            file_path,
            media_type='application/octet-stream',
            filename=f"subtitles_{job_id}.srt"
        )
    except Exception as e:
        print(f"[ERROR] File download error for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal error during file download")

# Root route
@app.get("/")
async def root():
    return {"message": "Subtitle Generator API is running!"}

# Run the app manually if needed
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
