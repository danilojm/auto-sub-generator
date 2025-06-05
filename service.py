from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import yt_dlp
import whisper
import os
import tempfile
import uuid
from pathlib import Path
import redis
import json
from deep_translator import GoogleTranslator
import re
import shutil
from typing import Optional

app = FastAPI(title="Subtitle Generator API")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis para armazenar status dos jobs
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Carregar modelo Whisper (fazer isso uma vez na inicialização)
whisper_model = whisper.load_model("base")

class VideoRequest(BaseModel):
    video_url: HttpUrl
    source_lang: str = "auto"
    target_lang: str = "pt"

class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, error
    progress: int
    message: str
    download_url: Optional[str] = None

def update_job_status(job_id: str, status: str, progress: int, message: str, download_url: str = None):
    """Atualiza status do job no Redis"""
    job_data = {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "message": message,
        "download_url": download_url
    }
    redis_client.setex(f"job:{job_id}", 3600, json.dumps(job_data))  # Expira em 1 hora

def download_audio(video_url: str, output_path: str) -> str:
    """Baixa áudio do vídeo usando yt-dlp"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        title = info.get('title', 'video')
        # Retorna o caminho do arquivo de áudio
        return f"{output_path}/{title}.wav"

def transcribe_audio(audio_path: str) -> str:
    """Transcreve áudio usando Whisper"""
    result = whisper_model.transcribe(audio_path)
    
    # Gerar arquivo SRT
    srt_content = []
    for i, segment in enumerate(result["segments"], 1):
        start_time = format_timestamp(segment["start"])
        end_time = format_timestamp(segment["end"])
        text = segment["text"].strip()
        
        srt_content.append(f"{i}")
        srt_content.append(f"{start_time} --> {end_time}")
        srt_content.append(text)
        srt_content.append("")
    
    return "\n".join(srt_content)

def format_timestamp(seconds: float) -> str:
    """Converte segundos para formato SRT timestamp"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace(".", ",")

def translate_srt(srt_content: str, target_lang: str = "pt") -> str:
    """Traduz conteúdo SRT usando seu código melhorado"""
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
                # Em caso de erro na tradução, manter texto original
                translated_blocks.append(block)
        else:
            translated_blocks.append(block)
    
    return "\n\n".join(translated_blocks)

async def process_video(job_id: str, video_url: str, target_lang: str):
    """Processa vídeo completo - função assíncrona"""
    try:
        # Criar diretório temporário
        temp_dir = tempfile.mkdtemp()
        
        # 1. Download do áudio
        update_job_status(job_id, "processing", 20, "Baixando áudio do vídeo...")
        audio_path = download_audio(str(video_url), temp_dir)
        
        # 2. Transcrição
        update_job_status(job_id, "processing", 50, "Transcrevendo áudio...")
        srt_content = transcribe_audio(audio_path)
        
        # 3. Tradução
        update_job_status(job_id, "processing", 80, "Traduzindo legendas...")
        translated_srt = translate_srt(srt_content, target_lang)
        
        # 4. Salvar arquivo final
        output_file = f"{temp_dir}/legendas_traduzidas_{job_id}.srt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(translated_srt)
        
        # 5. Mover para pasta de downloads (ou upload para S3)
        final_path = f"downloads/legendas_{job_id}.srt"
        os.makedirs("downloads", exist_ok=True)
        shutil.move(output_file, final_path)
        
        update_job_status(job_id, "completed", 100, "Processamento concluído!", f"/download/{job_id}")
        
        # Limpar arquivos temporários
        shutil.rmtree(temp_dir)
        
    except Exception as e:
        update_job_status(job_id, "error", 0, f"Erro: {str(e)}")

@app.post("/generate-subtitles")
async def generate_subtitles(request: VideoRequest, background_tasks: BackgroundTasks):
    """Endpoint principal para gerar legendas"""
    job_id = str(uuid.uuid4())
    
    # Inicializar job
    update_job_status(job_id, "pending", 0, "Iniciando processamento...")
    
    # Adicionar tarefa em background
    background_tasks.add_task(process_video, job_id, request.video_url, request.target_lang)
    
    return {"job_id": job_id, "message": "Processamento iniciado"}

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Verifica status do job"""
    job_data = redis_client.get(f"job:{job_id}")
    if not job_data:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    return json.loads(job_data)

@app.get("/download/{job_id}")
async def download_subtitle(job_id: str):
    """Download do arquivo de legenda"""
    from fastapi.responses import FileResponse
    
    file_path = f"downloads/legendas_{job_id}.srt"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        file_path,
        media_type='application/octet-stream',
        filename=f"legendas_{job_id}.srt"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)