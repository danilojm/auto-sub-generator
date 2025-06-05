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


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Armazenar status dos jobs em memória (para teste local)
job_status_storage = {}

# Carregar modelo Whisper
print("Carregando modelo Whisper...")
whisper_model = whisper.load_model("base")
print("Modelo carregado!")

class VideoRequest(BaseModel):
    video_url: str
    source_lang: str = "auto"
    target_lang: str = "pt"

def update_job_status(job_id: str, status: str, progress: int, message: str, download_url: str = None):
    print("""Atualiza status do job""")
    job_status_storage[job_id] = {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "message": message,
        "download_url": download_url,
        "timestamp": time.time()
    }

def download_audio(video_url: str, output_dir: str) -> str:
    print("""Baixa áudio do vídeo usando yt-dlp""")
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
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
        # Retorna o caminho provável do arquivo
        return f"{output_dir}/audio.wav"

def format_timestamp(seconds: float) -> str:
    print("""Converte segundos para formato SRT timestamp""")
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")

def transcribe_audio(audio_path: str) -> str:
    print("""Transcreve áudio usando Whisper""")
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

def translate_srt(srt_content: str, target_lang: str = "pt") -> str:
    print("""Traduz conteúdo SRT""")
    if not srt_content.strip():
        return ""
        
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
                print(f"Erro na tradução: {e}")
                # Em caso de erro na tradução, manter texto original
                translated_blocks.append(block)
        else:
            translated_blocks.append(block)
    
    return "\n\n".join(translated_blocks)

async def process_video(job_id: str, video_url: str, target_lang: str):
    print("""Processa vídeo completo""")
    temp_dir = "../temp"
    os.makedirs(temp_dir, exist_ok=True)
    try:
        # Inicializar status do job
        print(f"Processando job {job_id} em {temp_dir}")
        
        # 1. Download do áudio
        update_job_status(job_id, "processing", 10, "Baixando áudio do vídeo...")
        audio_path = download_audio(video_url, temp_dir)
        
        # Verificar se arquivo foi criado
        if not os.path.exists(audio_path):
            raise Exception("Falha ao baixar áudio do vídeo")
        
        # 2. Transcrição
        update_job_status(job_id, "processing", 40, "Transcrevendo áudio...")
        srt_content = transcribe_audio(audio_path)
        
        if not srt_content.strip():
            raise Exception("Falha na transcrição do áudio")
        
        # 3. Tradução
        update_job_status(job_id, "processing", 70, "Traduzindo legendas...")
        translated_srt = translate_srt(srt_content, target_lang)
        
        # 4. Salvar arquivo final
        update_job_status(job_id, "processing", 90, "Salvando arquivo...")
        
        # Criar pasta downloads se não existir
        downloads_dir = "../downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        
        output_file = f"{downloads_dir}/legendas_{job_id}.srt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(translated_srt)
        
        update_job_status(job_id, "completed", 100, "Processamento concluído!", f"/download/{job_id}")
        print(f"Job {job_id} completado com sucesso!")
        
    except Exception as e:
        error_msg = f"Erro: {str(e)}"
        print(f"Erro no job {job_id}: {error_msg}")
        update_job_status(job_id, "error", 0, error_msg)
    finally:
        # Limpar arquivos temporários
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

@app.post("/generate-subtitles")
async def generate_subtitles(request: VideoRequest, background_tasks: BackgroundTasks):
    print("""Endpoint principal para gerar legendas""")
    job_id = str(uuid.uuid4())

    # Inicia o status logo aqui
    update_job_status(job_id, "pending", 0, "Aguardando início do processamento...")

    # Adiciona a tarefa assíncrona
    background_tasks.add_task(process_video, job_id, request.video_url, request.target_lang)

    # Retorna imediatamente com job_id
    return {"job_id": job_id, "message": "Processamento iniciado"}

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    print("""Verifica status do job""")
    if job_id not in job_status_storage:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    return job_status_storage[job_id]

@app.get("/download/{job_id}")
async def download_subtitle(job_id: str):
    print("""Download do arquivo de legenda""")
    file_path = f"../downloads/legendas_{job_id}.srt"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        file_path,
        media_type='application/octet-stream',
        filename=f"legendas_{job_id}.srt"
    )

@app.get("/")
async def root():
    return {"message": "Subtitle Generator API está funcionando!"}

if __name__ == "__main__":
    import uvicorn
    print("Iniciando servidor...")
    uvicorn.run(app, host="0.0.0.0", port=8000)