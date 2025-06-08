
# 🎬 Automatic Subtitle Generator with Translation

This project is a **FastAPI-based API** that extracts audio from a YouTube video, transcribes the content using **Whisper**, translates the subtitles using **Google Translate**, and generates a downloadable `.srt` file. A simple frontend interface allows users to submit a video link and download the generated subtitles in just a few minutes.

---

## 🚀 Technologies Used

- **Python 3.10+**
- **FastAPI**
- **Uvicorn**
- **Whisper (OpenAI)**
- **yt-dlp**
- **Deep Translator (Google Translate)**
- **HTML, JavaScript (frontend)**
- **VS Code + Live Server (dev)**

---

## ⚙️ Requirements & Dependencies

### Python Packages for Video Processing and Subtitles

- `torch==2.7.1`
- `torchaudio==2.7.1`
- `torchvision==0.22.1`
- `openai-whisper==20231117`
- `yt-dlp==2025.03.31`
- `pillow==11.0.0`

### Backend (FastAPI and related)

- `fastapi==0.104.1`
- `uvicorn[standard]==0.24.0`
- `python-multipart==0.0.6`
- `pydantic==2.5.0`
- `setuptools==70.2.0`

### Translation

- `deep-translator==1.11.4`

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/danilojm/auto-sub-generator.git
cd auto-sub-generator
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate         # Windows
```

### 3. Install the dependencies

```bash
pip install -r requirements.txt
```

### 4. Enable GPU support (optional)

If you want to run Whisper with **GPU (CUDA)** support, check with:

```python
import torch
print(torch.cuda.is_available())  # should return True
```

Otherwise, it will fall back to CPU using FP32.

---

## 📁 Project Structure

```
subtitle-generator/
│
├── backend/
│   └── main.py          # Main FastAPI backend code
│
├── frontend/
│   └── index.html       # Frontend interface to use the API
│
├── static/
│   ├── style.css        # CSS stylesheet
│   └── script.js        # JavaScript frontend code
│
├── downloads/           # Generated subtitle files (.srt)
│
├── temp/                # Temporary audio and processing files
│
├── requirements.txt     # Python dependencies
│
└── README.md            # This file
```

---

## ▶️ Running the Project

### Backend (FastAPI API)

```bash
uvicorn main:app --reload
```

API will be available at:  
📡 `http://localhost:8000`

### Frontend (Live Server or manual)

1. Open `frontend/index.html` using Live Server (VS Code)  
   or  
2. Navigate manually to `http://localhost:5500/frontend/index.html`

---

## ✨ Features

- ✅ Supports multiple jobs running concurrently in the background  
- ✅ Automatic transcription using **Whisper**  
- ✅ Subtitle translation via **Google Translator**  
- ✅ Real-time progress bar in frontend  
- ✅ Direct download link for translated `.srt` files  

---

## 🧪 API Endpoints

### POST `/generate-subtitles`

**Request body:**

```json
{
  "video_url": "https://www.youtube.com/watch?v=XXXXXX",
  "source_lang": "auto",
  "target_lang": "pt"
}
```

**Response:**

```json
{
  "job_id": "abcd-1234-uuid",
  "message": "Processing started"
}
```

### GET `/status/{job_id}`

Returns job progress and status:

```json
{
  "job_id": "...",
  "status": "processing",
  "progress": 70,
  "message": "Translating subtitles...",
  "download_url": null
}
```

### GET `/download/{job_id}`

Downloads the generated `.srt` subtitle file.

---

## 📌 Notes

- Whisper model `base` is used by default. You may switch to `"small"`, `"medium"`, or `"large"` depending on your hardware and accuracy needs:

```python
whisper_model = whisper.load_model("base")
```

- The `temp/` directory is automatically cleaned after each job.
- CORS is fully open (`allow_origins=["*"]`) for development only; restrict in production.

---

## 💡 Future Improvements

- 📤 Support for local video file uploads  
- 🌐 Multiple translation engines/options  
- 🔒 User authentication and IP quota management  
- 📁 File upload support via frontend  

---

## 🤝 Contributing

Feel free to open issues and pull requests. Suggestions and feedback are welcome!

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 👨‍💻 Developed by

Danilo Mendes de Oliveira  
📧 d.mendes0924@gmail.com  
📍 Toronto, Canada  
🔗 [LinkedIn](https://www.linkedin.com/in/danilo-mendes-de-oliveira/?locale=en_US)
