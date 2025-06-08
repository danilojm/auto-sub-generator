document.addEventListener('DOMContentLoaded', () => {
    const API_BASE = 'http://localhost:8000'; // Base URL for backend API
    let currentJobId = null;                  // Stores the current processing job ID
    let pollingActive = false;                // Controls polling loop status
    let pollingAttempts = 0;                  // Counts how many times we've polled

    // DOM elements references
    const form = document.getElementById('subtitleForm');
    const generateBtn = document.getElementById('generateBtn');
    const progressContainer = document.getElementById('progressContainer');
    const downloadContainer = document.getElementById('downloadContainer');
    const errorMessage = document.getElementById('errorMessage');
    const progressFill = document.getElementById('progressFill');
    const statusMessage = document.getElementById('statusMessage');
    const downloadBtn = document.getElementById('downloadBtn');

    // Handle form submission without page reload
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        console.log("Form submitted without reload.");

        // Get form input values
        const videoUrl = document.getElementById('videoUrl').value;
        const sourceLang = document.getElementById('sourceLang').value;
        const targetLang = document.getElementById('targetLang').value;

        resetUI();
        setButtonState(true, 'Processing...');

        try {
            // Send request to start subtitle generation and get job ID
            const jobId = await sendSubtitleRequest(videoUrl, sourceLang, targetLang);
            if (!jobId) throw new Error('Invalid Job ID received');

            currentJobId = jobId;
            showElement(progressContainer);   // Show progress bar container
            startPolling(jobId);               // Begin polling for job status
        } catch (err) {
            displayError('Error processing video: ' + err.message);
            setButtonState(false, '🚀 Generate Subtitles');
        }
    });

    /**
     * Sends POST request to backend API to start subtitle generation job.
     * @param {string} videoUrl - URL of the video to process.
     * @param {string} sourceLang - Source language code.
     * @param {string} targetLang - Target language code.
     * @returns {Promise<string>} - Returns the job ID from the backend.
     */
    async function sendSubtitleRequest(videoUrl, sourceLang, targetLang) {
        const response = await fetch(`${API_BASE}/generate-subtitles`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_url: videoUrl, source_lang: sourceLang, target_lang: targetLang })
        });

        if (!response.ok) throw new Error('Request failed');
        const data = await response.json();
        console.log('Received Job ID:', data.job_id);
        return data.job_id;
    }

    /**
     * Polls backend periodically to check the processing status of the job.
     * Uses a while loop with async/await and delays between requests.
     * Stops polling when job is completed or error occurs.
     * @param {string} jobId - ID of the job to poll status for.
     */
    async function startPolling(jobId) {
        console.log(`🚀 Starting polling for job: ${jobId}`);
        pollingActive = true;
        pollingAttempts = 0;

        while (pollingActive) {
            try {
                console.log(`🔄 Checking status for job: ${jobId} (attempt #${++pollingAttempts})`);

                const response = await fetch(`${API_BASE}/status/${jobId}`);
                if (!response.ok) throw new Error('Failed to fetch status');
                const status = await response.json();
                console.log('✅ Status received:', status);

                updateProgress(status.progress, status.message);

                if (status.status === 'completed') {
                    // Job finished successfully: stop polling and show download link
                    pollingActive = false;
                    showDownload(status.download_url);
                    setButtonState(false, '🚀 Generate Subtitles');
                    break; // exit loop immediately
                }

                if (status.status === 'error') {
                    // Backend reported an error during processing
                    pollingActive = false;
                    displayError(status.message || 'Unknown error occurred');
                    setButtonState(false, '🚀 Generate Subtitles');
                    break;
                }

            } catch (error) {
                console.error("❌ Error during polling:", error);
                pollingActive = false;
                displayError('Error checking status. Please try again.');
                setButtonState(false, '🚀 Generate Subtitles');
                break;
            }

            // Wait 2 seconds before next polling request to avoid overloading server
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    }

    /**
     * Updates the progress bar and status message.
     * @param {number} percent - Percentage progress (0-100).
     * @param {string} msg - Status message to display.
     */
    function updateProgress(percent, msg) {
        progressFill.style.width = percent + '%';
        statusMessage.textContent = msg;
    }

    /**
     * Shows the download container and sets the download button href.
     * @param {string} downloadUrl - URL to the generated subtitle file.
     */
    function showDownload(downloadUrl) {
        hideElement(progressContainer);
        showElement(downloadContainer);
        downloadBtn.href = `${API_BASE}${downloadUrl}`;
    }

    /**
     * Displays an error message on the UI.
     * @param {string} message - Error message text.
     */
    function displayError(message) {
        errorMessage.textContent = message;
        showElement(errorMessage);
    }

    /**
     * Resets the UI by hiding progress, download, and error containers.
     */
    function resetUI() {
        hideElement(progressContainer);
        hideElement(downloadContainer);
        hideElement(errorMessage);
    }

    /**
     * Enables or disables the generate button and updates its text.
     * @param {boolean} disabled - Whether the button should be disabled.
     * @param {string} text - Text to display on the button.
     */
    function setButtonState(disabled, text) {
        generateBtn.disabled = disabled;
        generateBtn.textContent = text;
    }

    // Utility functions to show/hide elements
    function showElement(el) {
        el.style.display = 'block';
    }

    function hideElement(el) {
        el.style.display = 'none';
    }
});
