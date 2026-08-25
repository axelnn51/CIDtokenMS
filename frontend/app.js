const extractBtn = document.getElementById('extract-btn');
const btnText = extractBtn.querySelector('.btn-text');
const spinner = extractBtn.querySelector('.spinner');
const statusContainer = document.getElementById('status-container');
const progressBar = document.getElementById('progress-bar');
const statusText = document.getElementById('status-text');
const terminalContent = document.getElementById('terminal-content');
const resultsSection = document.getElementById('results-section');
const resultCode = document.getElementById('result-code');
const copyBtn = document.getElementById('copy-btn');
const apiStatusBadge = document.getElementById('api-status');

let currentJobId = null;
let pollInterval = null;
let logsInterval = null;
let lastLogCount = 0;

// Check API Health on load
async function checkHealth() {
    try {
        const res = await fetch('/health');
        if (res.ok) {
            apiStatusBadge.textContent = 'API Online';
            apiStatusBadge.style.color = 'var(--success)';
            apiStatusBadge.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
            apiStatusBadge.style.borderColor = 'rgba(16, 185, 129, 0.2)';
            extractBtn.disabled = false;
        } else {
            throw new Error('API Offline');
        }
    } catch (e) {
        apiStatusBadge.textContent = 'API Offline';
        apiStatusBadge.style.color = 'var(--error)';
        apiStatusBadge.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
        apiStatusBadge.style.borderColor = 'rgba(239, 68, 68, 0.2)';
        extractBtn.disabled = true;
    }
}

// Start the extraction job
async function startExtraction() {
    // Reset UI
    btnText.classList.add('hidden');
    spinner.classList.remove('hidden');
    extractBtn.disabled = true;
    statusContainer.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    terminalContent.innerHTML = '<div class="log-line">> Initiating extraction protocol...</div>';
    progressBar.style.width = '10%';
    statusText.textContent = 'Sending request to API...';
    lastLogCount = 0;

    try {
        const res = await fetch('/api/v1/get-token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_url: "https://my.visualstudio.com/" })
        });
        
        if (!res.ok) throw new Error('Failed to start job');
        
        const data = await res.json();
        currentJobId = data.job_id;
        
        progressBar.style.width = '20%';
        statusText.textContent = `Job created (${currentJobId}). Waiting for worker...`;
        
        // Start polling status and logs
        pollInterval = setInterval(checkJobStatus, 2000);
        logsInterval = setInterval(fetchLogs, 1500);
        
    } catch (e) {
        handleError(e.message);
    }
}

// Poll the job status
async function checkJobStatus() {
    if (!currentJobId) return;
    
    try {
        const res = await fetch(`/api/v1/jobs/${currentJobId}`);
        if (!res.ok) return;
        
        const data = await res.json();
        
        // Update UI based on state
        switch (data.status) {
            case 'STARTING_BROWSER':
                progressBar.style.width = '40%';
                statusText.textContent = 'Spinning up Chromium browser...';
                break;
            case 'AUTHENTICATING':
                progressBar.style.width = '60%';
                statusText.textContent = 'Navigating to Microsoft and logging in...';
                break;
            case 'EXECUTING':
                progressBar.style.width = '80%';
                statusText.textContent = 'Extracting cookies and LocalStorage...';
                break;
            case 'COMPLETED':
                progressBar.style.width = '100%';
                statusText.textContent = 'Extraction complete!';
                handleSuccess(data.result);
                break;
            case 'CHALLENGE_REQUIRED':
                handleError('Manual intervention required (2FA/CAPTCHA). Check server VNC.');
                break;
            case 'FAILED_PERMANENTLY':
                handleError(`Extraction failed: ${data.result?.error_message || 'Unknown error'}`);
                break;
        }
    } catch (e) {
        console.error("Status check failed", e);
    }
}

// Fetch logs and update terminal
async function fetchLogs() {
    try {
        const res = await fetch('/api/v1/logs?limit=20');
        if (!res.ok) return;
        
        const data = await res.json();
        const logs = data.logs.reverse(); // Newest at bottom
        
        if (logs.length > lastLogCount || lastLogCount === 0) {
            terminalContent.innerHTML = '';
            logs.forEach(log => {
                const div = document.createElement('div');
                div.className = 'log-line';
                // Very basic highlight for log levels
                let formatted = log;
                if (log.includes('INFO')) formatted = `<span style="color: #61afef">INFO</span> ${log.split('INFO')[1]}`;
                if (log.includes('ERROR')) formatted = `<span style="color: #e06c75">ERROR</span> ${log.split('ERROR')[1]}`;
                if (log.includes('WARNING')) formatted = `<span style="color: #d19a66">WARN</span> ${log.split('WARNING')[1]}`;
                
                div.innerHTML = `> ${formatted}`;
                terminalContent.appendChild(div);
            });
            // Auto scroll to bottom
            terminalContent.scrollTop = terminalContent.scrollHeight;
            lastLogCount = logs.length;
        }
    } catch (e) {
        console.error("Logs fetch failed", e);
    }
}

// Handle job success
function handleSuccess(result) {
    cleanup();
    
    // Format JSON beautifully
    let displayJson = {};
    try {
        displayJson = JSON.parse(result.token);
    } catch (e) {
        displayJson = result;
    }
    
    resultCode.textContent = JSON.stringify(displayJson, null, 2);
    resultsSection.classList.remove('hidden');
    
    // Reset button
    btnText.classList.remove('hidden');
    spinner.classList.add('hidden');
    extractBtn.disabled = false;
    btnText.textContent = "Run Again";
}

// Handle job errors
function handleError(message) {
    cleanup();
    progressBar.style.backgroundColor = 'var(--error)';
    statusText.textContent = message;
    statusText.style.color = 'var(--error)';
    
    // Reset button
    btnText.classList.remove('hidden');
    spinner.classList.add('hidden');
    extractBtn.disabled = false;
    btnText.textContent = "Retry";
}

// Clean intervals
function cleanup() {
    if (pollInterval) clearInterval(pollInterval);
    if (logsInterval) clearInterval(logsInterval);
    pollInterval = null;
    logsInterval = null;
}

// Copy to clipboard
copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(resultCode.textContent);
    const originalText = copyBtn.textContent;
    copyBtn.textContent = 'Copied!';
    setTimeout(() => {
        copyBtn.textContent = originalText;
    }, 2000);
});

// Event Listeners
extractBtn.addEventListener('click', startExtraction);

// Initialize
checkHealth();
