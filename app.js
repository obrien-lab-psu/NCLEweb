// API Configuration
// Use relative URL so it works both locally (with proxy) and in production
const API_BASE_URL = window.location.origin;

// Global state
let selectedFile = null;
let resultsData = null;
let resultsTable = null;

// DOM Elements
const pdbFileInput = document.getElementById('pdbFile');
const fileName = document.getElementById('fileName');
const analyzeBtn = document.getElementById('analyzeBtn');
const uploadPage = document.getElementById('uploadPage');
const processingPage = document.getElementById('processingPage');
const resultsPage = document.getElementById('resultsPage');
const processingMessage = document.getElementById('processingMessage');
const newAnalysisBtn = document.getElementById('newAnalysisBtn');
const downloadCSV = document.getElementById('downloadCSV');
const resultsTable_div = document.getElementById('resultsTable');
const noResults = document.getElementById('noResults');
const resultsStats = document.getElementById('resultsStats');
const resultsTitle = document.getElementById('resultsTitle');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
});

function setupEventListeners() {
    // File selection
    pdbFileInput.addEventListener('change', handleFileSelect);
    
    // Analyze button
    analyzeBtn.addEventListener('click', handleAnalyze);
    
    // New analysis button
    newAnalysisBtn.addEventListener('click', resetToUpload);
    
    // Download CSV
    downloadCSV.addEventListener('click', handleDownloadCSV);
    
    // Drag and drop (optional enhancement)
    const uploadBox = document.querySelector('.upload-box');
    uploadBox.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadBox.classList.add('dragover');
    });
    
    uploadBox.addEventListener('dragleave', () => {
        uploadBox.classList.remove('dragover');
    });
    
    uploadBox.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadBox.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file && file.name.endsWith('.pdb')) {
            pdbFileInput.files = e.dataTransfer.files;
            handleFileSelect();
        } else {
            alert('Please upload a .pdb file');
        }
    });
}

function handleFileSelect() {
    const file = pdbFileInput.files[0];
    if (!file) return;
    
    if (!file.name.endsWith('.pdb')) {
        alert('Please select a PDB file (.pdb extension)');
        pdbFileInput.value = '';
        return;
    }
    
    if (file.size > 20 * 1024 * 1024) {
        alert('File too large. Maximum size is 20 MB.');
        pdbFileInput.value = '';
        return;
    }
    
    selectedFile = file;
    fileName.textContent = `Selected: ${file.name} (${formatFileSize(file.size)})`;
    fileName.style.display = 'block';
    analyzeBtn.disabled = false;
}

async function handleAnalyze() {
    if (!selectedFile) return;
    
    // Show processing page
    showPage('processing');
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    try {
        processingMessage.textContent = 'Uploading file to server...';
        
        const response = await fetch(`${API_BASE_URL}/api/analyze-json`, {
            method: 'POST',
            body: formData
        });
        
        processingMessage.textContent = 'Analyzing structure...';
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Analysis failed');
        }
        
        const data = await response.json();
        
        if (data.success) {
            resultsData = data;
            displayResults(data);
        } else {
            throw new Error('Analysis failed: ' + (data.error || 'Unknown error'));
        }
        
    } catch (error) {
        console.error('Error during analysis:', error);
        alert(`Analysis failed: ${error.message}`);
        showPage('upload');
    }
}

function displayResults(data) {
    // Update title
    resultsTitle.textContent = `Results for ${data.pdb_id}`;
    
    // Display stats
    const numEntanglements = data.num_entanglements || 0;
    const hasEntanglements = data.results && data.results.length > 0;
    
    resultsStats.innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${numEntanglements}</div>
            <div class="stat-label">Total Results</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${data.pdb_id}</div>
            <div class="stat-label">Structure ID</div>
        </div>
    `;
    
    if (!hasEntanglements || numEntanglements === 0) {
        noResults.style.display = 'block';
        resultsTable_div.style.display = 'none';
    } else {
        noResults.style.display = 'none';
        resultsTable_div.style.display = 'block';
        renderTable(data.results);
    }
    
    showPage('results');
}

function renderTable(data) {
    // Destroy existing table if any
    if (resultsTable) {
        resultsTable.destroy();
    }
    
    // Define columns
    const columns = [
        { title: "ID", field: "ID", width: 100 },
        { title: "i", field: "i", width: 80 },
        { title: "j", field: "j", width: 80 },
        { title: "Crossings N", field: "crossingsN", width: 150 },
        { title: "Crossings C", field: "crossingsC", width: 150 },
        { title: "gn", field: "gn", width: 100, formatter: "money", formatterParams: { precision: 5, symbol: "" } },
        { title: "gc", field: "gc", width: 100, formatter: "money", formatterParams: { precision: 5, symbol: "" } },
        { title: "GLNn", field: "GLNn", width: 80 },
        { title: "GLNc", field: "GLNc", width: 80 },
        { title: "TLNn", field: "TLNn", width: 80 },
        { title: "TLNc", field: "TLNc", width: 80 },
        { title: "CCbond", field: "CCbond", width: 100, formatter: "tickCross" },
        { title: "ENT", field: "ENT", width: 80, formatter: "tickCross" }
    ];
    
    // Create table
    resultsTable = new Tabulator(resultsTable_div, {
        data: data,
        columns: columns,
        layout: "fitDataStretch",
        pagination: true,
        paginationSize: 20,
        paginationSizeSelector: [10, 20, 50, 100],
        movableColumns: true,
        resizableRows: true,
        height: "500px"
    });
}

function handleDownloadCSV() {
    if (!resultsData) return;
    
    // Convert results to CSV
    const headers = ['ID', 'i', 'j', 'crossingsN', 'crossingsC', 'gn', 'gc', 'GLNn', 'GLNc', 'TLNn', 'TLNc', 'CCbond', 'ENT'];
    const rows = resultsData.results.map(row => 
        headers.map(header => {
            const value = row[header];
            // Handle values that might contain commas or quotes
            if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
                return `"${value.replace(/"/g, '""')}"`;
            }
            return value;
        }).join(',')
    );
    
    const csv = [headers.join(','), ...rows].join('\n');
    
    // Create download link
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${resultsData.pdb_id}_GE.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

function resetToUpload() {
    selectedFile = null;
    resultsData = null;
    pdbFileInput.value = '';
    fileName.textContent = '';
    fileName.style.display = 'none';
    analyzeBtn.disabled = true;
    showPage('upload');
}

function showPage(page) {
    uploadPage.style.display = page === 'upload' ? 'block' : 'none';
    processingPage.style.display = page === 'processing' ? 'block' : 'none';
    resultsPage.style.display = page === 'results' ? 'block' : 'none';
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
