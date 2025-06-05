import requests
import time
import json

# Configuração
API_BASE = "http://localhost:8000"
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll para teste

def test_api():
    print("🧪 Testando API do Gerador de Legendas")
    print("-" * 50)
    
    # 1. Testar se API está funcionando
    try:
        response = requests.get(f"{API_BASE}/")
        print(f"✅ API Status: {response.json()}")
    except Exception as e:
        print(f"❌ Erro ao conectar com API: {e}")
        return
    
    # 2. Enviar vídeo para processamento
    print(f"\n🎬 Enviando vídeo para processamento...")
    print(f"URL: {TEST_VIDEO_URL}")
    
    try:
        response = requests.post(f"{API_BASE}/generate-subtitles", json={
            "video_url": TEST_VIDEO_URL,
            "source_lang": "auto",
            "target_lang": "pt"
        })
        
        if response.status_code != 200:
            print(f"❌ Erro ao enviar: {response.status_code} - {response.text}")
            return
            
        result = response.json()
        job_id = result["job_id"]
        print(f"✅ Job criado: {job_id}")
        
    except Exception as e:
        print(f"❌ Erro ao enviar vídeo: {e}")
        return
    
    # 3. Monitorar progresso
    print(f"\n📊 Monitorando progresso...")
    
    while True:
        try:
            response = requests.get(f"{API_BASE}/status/{job_id}")
            status = response.json()
            
            progress = status["progress"]
            message = status["message"]
            status_type = status["status"]
            
            print(f"[{progress:3d}%] {message}")
            
            if status_type == "completed":
                print(f"✅ Processamento concluído!")
                download_url = status["download_url"]
                
                # 4. Fazer download
                print(f"\n📥 Fazendo download...")
                response = requests.get(f"{API_BASE}{download_url}")
                
                if response.status_code == 200:
                    filename = f"teste_legendas_{job_id}.srt"
                    with open(filename, "wb") as f:
                        f.write(response.content)
                    print(f"✅ Arquivo salvo como: {filename}")
                    
                    # Mostrar prévia do conteúdo
                    with open(filename, "r", encoding="utf-8") as f:
                        content = f.read()
                        lines = content.split('\n')
                        preview = '\n'.join(lines[:20])  # Primeiras 20 linhas
                        print(f"\n📄 Prévia do arquivo:")
                        print("-" * 30)
                        print(preview)
                        if len(lines) > 20:
                            print("...")
                else:
                    print(f"❌ Erro no download: {response.status_code}")
                break
                
            elif status_type == "error":
                print(f"❌ Erro no processamento: {message}")
                break
                
            time.sleep(3)  # Aguardar 3 segundos antes da próxima verificação
            
        except Exception as e:
            print(f"❌ Erro ao verificar status: {e}")
            break

if __name__ == "__main__":
    test_api()