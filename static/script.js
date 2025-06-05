document.addEventListener('DOMContentLoaded', () => {
    const API_BASE = 'http://127.0.0.1:8000';
    let currentJobId = null;
    let statusInterval = null;

    const form = document.getElementById('subtitleForm');
    const generateBtn = document.getElementById('generateBtn');
    const progressContainer = document.getElementById('progressContainer');
    const downloadContainer = document.getElementById('downloadContainer');
    const errorMessage = document.getElementById('errorMessage');
    const progressFill = document.getElementById('progressFill');
    const statusMessage = document.getElementById('statusMessage');
    const downloadBtn = document.getElementById('downloadBtn');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        console.log("Formulário enviado, sem recarregar!");

        const videoUrl = document.getElementById('videoUrl').value;
        const sourceLang = document.getElementById('sourceLang').value;
        const targetLang = document.getElementById('targetLang').value;

        resetUI();
        setButtonState(true, 'Processando...');

        try {
            const jobId = await sendSubtitleRequest(videoUrl, sourceLang, targetLang);
            if (!jobId) throw new Error('Job ID inválido');

            currentJobId = jobId;
            showElement(progressContainer);
            startPolling(jobId);
        } catch (err) {
            displayError('Erro ao processar vídeo: ' + err.message);
            setButtonState(false, '🚀 Gerar Legendas');
        }
    });

    // Funções

    async function sendSubtitleRequest(videoUrl, sourceLang, targetLang) {
        const response = await fetch(`${API_BASE}/generate-subtitles`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_url: videoUrl, source_lang: sourceLang, target_lang: targetLang })
        });

        if (!response.ok) throw new Error('Falha na requisição');
        const data = await response.json();
        console.log('Job ID recebido:', data.job_id);
        return data.job_id;
    }

    function startPolling(jobId) {
        statusInterval = setInterval(async () => {
            try {
                const response = await fetch(`${API_BASE}/status/${jobId}`);
                const status = await response.json();
                console.log('Status recebido:', status);

                updateProgress(status.progress, status.message);

                if (status.status === 'completed') {
                    stopPolling();
                    showDownload(status.download_url);
                    setButtonState(false, '🚀 Gerar Legendas');
                } else if (status.status === 'error') {
                    stopPolling();
                    displayError(status.message);
                    setButtonState(false, '🚀 Gerar Legendas');
                }
            } catch {
                stopPolling();
                displayError('Erro ao verificar status');
                setButtonState(false, '🚀 Gerar Legendas');
            }
        }, 2000);
    }

    function stopPolling() {
        clearInterval(statusInterval);
        statusInterval = null;
    }

    function updateProgress(percent, msg) {
        progressFill.style.width = percent + '%';
        statusMessage.textContent = msg;
    }

    function showDownload(downloadUrl) {
        hideElement(progressContainer);
        showElement(downloadContainer);
        downloadBtn.href = `${API_BASE}${downloadUrl}`;
    }

    function displayError(message) {
        errorMessage.textContent = message;
        showElement(errorMessage);
    }

    function resetUI() {
        hideElement(progressContainer);
        hideElement(downloadContainer);
        hideElement(errorMessage);
    }

    function setButtonState(disabled, text) {
        generateBtn.disabled = disabled;
        generateBtn.textContent = text;
    }

    function showElement(el) {
        el.style.display = 'block';
    }

    function hideElement(el) {
        el.style.display = 'none';
    }
});
