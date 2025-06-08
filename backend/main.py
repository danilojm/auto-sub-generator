from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

app = FastAPI(title="Subtitle Generator API")

app.mount("/static", StaticFiles(directory="../static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

job_status_storage = {}

try:
    whisper_model = whisper.load_model("base")
    print("[INFO] Modelo Whisper carregado com sucesso.")
except Exception as e:
    print(f"[ERROR] Falha ao carregar o modelo Whisper: {e}")
    whisper_model = None  # Pode decidir parar o app se necessário

class VideoRequest(BaseModel):
    video_url: str
    source_lang: str = "auto"
    target_lang: str = "pt"

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
        print(f"[ERROR] Falha ao atualizar status do job {job_id}: {e}")

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
            raise Exception("Arquivo de áudio não encontrado após download.")
        print(f"[INFO] Áudio baixado com sucesso em {audio_path}")
        return audio_path
    except Exception as e:
        print(f"[ERROR] Falha ao baixar áudio: {e}")
        return None

def format_timestamp(seconds: float) -> str:
    try:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")
    except Exception as e:
        print(f"[ERROR] Falha ao formatar timestamp: {e}")
        return "00:00:00,000"

def transcribe_audio(audio_path: str) -> str:
    if whisper_model is None:
        raise Exception("Modelo Whisper não está carregado.")
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
        print(f"[INFO] Transcrição concluída com sucesso.")
        return "\n".join(srt_content)
    except Exception as e:
        print(f"[ERROR] Falha na transcrição do áudio: {e}")
        raise

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
                    print(f"[WARN] Falha na tradução de bloco, usando original. Erro: {e}")
                    translated_blocks.append(block)
            else:
                translated_blocks.append(block)
        print(f"[INFO] Tradução concluída com sucesso.")
        return "\n\n".join(translated_blocks)
    except Exception as e:
        print(f"[ERROR] Falha durante tradução: {e}")
        raise

def process_video(job_id: str, video_url: str, target_lang: str):
    print(f"[PROCESSAMENTO] Iniciando job {job_id}")
    
    temp_dir = "../temp"
    os.makedirs(temp_dir, exist_ok=True)
    try:
        update_job_status(job_id, "processing", 10, "Baixando áudio do vídeo...")
        audio_path = download_audio(video_url, temp_dir)
        if not audio_path or not os.path.exists(audio_path):
            raise Exception("Falha ao baixar áudio do vídeo")

        update_job_status(job_id, "processing", 40, "Transcrevendo áudio...")
        srt_content = transcribe_audio(audio_path)
        if not srt_content.strip():
            raise Exception("Falha na transcrição do áudio")

        update_job_status(job_id, "processing", 70, "Traduzindo legendas...")
        translated_srt = translate_srt(srt_content, target_lang)

        update_job_status(job_id, "processing", 90, "Salvando arquivo...")
        downloads_dir = "../downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        output_file = f"{downloads_dir}/legendas_{job_id}.srt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(translated_srt)

        download_url = f"/download/{job_id}"
        update_job_status(job_id, "completed", 100, "Processamento concluído!", download_url)
    except Exception as e:
        error_msg = f"Erro: {str(e)}"
        print(f"[ERROR] {error_msg}")
        update_job_status(job_id, "error", 0, error_msg)
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"[INFO] Diretório temporário removido.")
            except Exception as e:
                print(f"[WARN] Falha ao remover diretório temporário: {e}")

@app.post("/generate-subtitles")
async def generate_subtitles(request: VideoRequest, background_tasks: BackgroundTasks):
    try:
        job_id = str(uuid.uuid4())
        update_job_status(job_id, "pending", 0, "Aguardando início do processamento...")
        background_tasks.add_task(process_video, job_id, request.video_url, request.target_lang)
        return {"job_id": job_id, "message": "Processamento iniciado"}
    except Exception as e:
        print(f"[ERROR] Falha ao iniciar processamento: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao iniciar processamento")

@app.get("/status/{job_id}")
def get_job_status(job_id: str):
    try:
        print(f"Consultando status do job: {job_id}")
        if job_id not in job_status_storage:
            raise HTTPException(status_code=404, detail="Job não encontrado")
        
        print(f"Status do job {job_id}: {job_status_storage[job_id]}")
        return job_status_storage[job_id]
    except Exception as e:
        print(f"[ERROR] Erro ao consultar status do job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao consultar status")

@app.get("/download/{job_id}")
async def download_subtitle(job_id: str):
    try:
        file_path = f"../downloads/legendas_{job_id}.srt"
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        return FileResponse(
            file_path,
            media_type='application/octet-stream',
            filename=f"legendas_{job_id}.srt"
        )
    except Exception as e:
        print(f"[ERROR] Erro no download do arquivo do job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno no download")

@app.get("/")
async def root():
    return {"message": "Subtitle Generator API is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
