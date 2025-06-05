const API_BASE = 'http://localhost:8000';
        let currentJobId = null;
        let statusInterval = null;

        document.getElementById('subtitleForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const videoUrl = document.getElementById('videoUrl').value;
            const sourceLang = document.getElementById('sourceLang').value;
            const targetLang = document.getElementById('targetLang').value;
            
            // Reset UI
            hideAllMessages();
            setGenerateButtonState(true, 'Processando...');
            
            try {
                const response = await fetch(`${API_BASE}/generate-subtitles`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        video_url: videoUrl,
                        source_lang: sourceLang,
                        target_lang: targetLang
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Erro ao iniciar processamento');
                }
                
                const data = await response.json();
                currentJobId = data.job_id;
                
                // Mostrar progresso e iniciar polling
                showProgress();
                startStatusPolling();
                
            } catch (error) {
                showError('Erro ao processar vídeo: ' + error.message);
                setGenerateButtonState(false, '🚀 Gerar Legendas');
            }
        });

        function startStatusPolling() {
            statusInterval = setInterval(async () => {
                if (!currentJobId) return;
                
                try {
                    const response = await fetch(`${API_BASE}/status/${currentJobId}`);
                    const status = await response.json();
                    
                    updateProgress(status.progress, status.message);
                    
                    if (status.status === 'completed') {
                        clearInterval(statusInterval);
                        showDownload(status.download_url);
                        setGenerateButtonState(false, '🚀 Gerar Legendas');
                    } else if (status.status === 'error') {
                        clearInterval(statusInterval);
                        showError(status.message);
                        setGenerateButtonState(false, '🚀 Gerar Legendas');
                    }
                    
                } catch (error) {
                    clearInterval(statusInterval);
                    showError('Erro ao verificar status');
                    setGenerateButtonState(false, '🚀 Gerar Legendas');
                }
            }, 2000);
        }

        function updateProgress(progress, message) {
            document.getElementById('progressFill').style.width = progress + '%';
            document.getElementById('statusMessage').textContent = message;
        }

        function showProgress() {
            document.getElementById('progressContainer').style.display = 'block';
        }

        function showDownload(downloadUrl) {
            document.getElementById('progressContainer').style.display = 'none';
            document.getElementById('downloadContainer').style.display = 'block';
            document.getElementById('downloadBtn').href = `${API_BASE}${downloadUrl}`;
        }

        function showError(message) {
            const errorEl = document.getElementById('errorMessage');
            errorEl.textContent = message;
            errorEl.style.display = 'block';
        }

        function hideAllMessages() {
            document.getElementById('progressContainer').style.display = 'none';
            document.getElementById('downloadContainer').style.display = 'none';
            document.getElementById('errorMessage').style.display = 'none';
        }

        function setGenerateButtonState(disabled, text) {
            const btn = document.getElementById('generateBtn');
            btn.disabled = disabled;
            btn.textContent = text;
        }