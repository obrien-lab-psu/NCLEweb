// API Configuration
// Use relative URL for production (served by Apache)
// Use localhost for local file:// testing
const API_BASE_URL = window.location.protocol === 'file:' 
    ? 'http://127.0.0.1:8000' 
    : 'https://ncleweb.org';

// Global state
let selectedFile = null;
let resultsData = null;
let resultsTable = null;
let nglStage = null;
let pdbFileContent = null;
let isSpinning = false;
let currentComponent = null;
let availableChains = [];

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
    initNGLViewer();
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
    
    // Chain selector (will be enabled when structure loads)
    const chainSelect = document.getElementById('chainSelect');
    if (chainSelect) {
        chainSelect.addEventListener('change', handleChainChange);
    }
    
    // Clear selection button
    const clearSelectionBtn = document.getElementById('clearSelection');
    if (clearSelectionBtn) {
        clearSelectionBtn.addEventListener('click', clearEntanglementHighlight);
    }
    
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
    
    // Read file content for later use in NGL viewer
    const reader = new FileReader();
    reader.onload = function(e) {
        pdbFileContent = e.target.result;
    };
    reader.readAsText(file);
    
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
    
    // Load structure into NGL viewer
    if (pdbFileContent) {
        loadStructureIntoNGL(pdbFileContent);
    }
    
    showPage('results');
    
    // Ensure NGL viewer resizes properly after page is shown
    setTimeout(() => {
        if (nglStage) nglStage.handleResize();
    }, 100);
}

function renderTable(data) {
    // Destroy existing table if any
    if (resultsTable) {
        resultsTable.destroy();
    }
    
    // Define columns
    const columns = [
        { title: "ID", field: "ID", minWidth: 100, widthGrow: 1 },
        { title: "Chain", field: "chain", minWidth: 70, widthGrow: 1 },
        { title: "i", field: "i", minWidth: 70, widthGrow: 1 },
        { title: "j", field: "j", minWidth: 70, widthGrow: 1 },
        { title: "Crossings N", field: "crossingsN", minWidth: 150, widthGrow: 2, tooltip: true },
        { title: "Crossings C", field: "crossingsC", minWidth: 150, widthGrow: 2, tooltip: true },
        { title: "gn", field: "gn", minWidth: 90, widthGrow: 1, formatter: "money", formatterParams: { precision: 5, symbol: "" } },
        { title: "gc", field: "gc", minWidth: 90, widthGrow: 1, formatter: "money", formatterParams: { precision: 5, symbol: "" } },
        { title: "GLNn", field: "GLNn", minWidth: 70, widthGrow: 1 },
        { title: "GLNc", field: "GLNc", minWidth: 70, widthGrow: 1 },
        { title: "TLNn", field: "TLNn", minWidth: 70, widthGrow: 1 },
        { title: "TLNc", field: "TLNc", minWidth: 70, widthGrow: 1 },
        { title: "CCbond", field: "CCbond", minWidth: 90, widthGrow: 1, formatter: "tickCross", hozAlign: "center" },
        { title: "ENT", field: "ENT", minWidth: 70, widthGrow: 1, formatter: "tickCross", hozAlign: "center" }
    ];
    
    // Create table
    resultsTable = new Tabulator(resultsTable_div, {
        data: data,
        columns: columns,
        layout: "fitData",
        pagination: true,
        paginationSize: 20,
        paginationSizeSelector: [10, 20, 50, 100],
        movableColumns: true,
        resizableColumns: true,
        resizableRows: true,
        height: "600px",
        tooltips: true,
        selectable: 1,
        selectableRollingSelection: false
    });
    
    // Add row click handler for highlighting entanglements
    resultsTable.on("rowClick", function(e, row){
        highlightEntanglement(row.getData());
    });
}

function handleDownloadCSV() {
    if (!resultsData) return;
    
    // Convert results to CSV
    const headers = ['ID', 'chain', 'i', 'j', 'crossingsN', 'crossingsC', 'gn', 'gc', 'GLNn', 'GLNc', 'TLNn', 'TLNc', 'CCbond', 'ENT'];
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
    pdbFileContent = null;
    pdbFileInput.value = '';
    fileName.textContent = '';
    fileName.style.display = 'none';
    analyzeBtn.disabled = true;
    
    // Clear NGL viewer
    if (nglStage) {
        nglStage.removeAllComponents();
    }
    
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

// ===== NGL Viewer Functions =====

function initNGLViewer() {
    const viewport = document.getElementById('nglViewport');
    if (!viewport) return;
    
    nglStage = new NGL.Stage(viewport, {
        backgroundColor: 'white',
        quality: 'high',
        sampleLevel: 2
    });
    
    // Handle window resize
    window.addEventListener('resize', () => {
        if (nglStage) nglStage.handleResize();
    });
    
    // Set up viewer controls
    const resetViewBtn = document.getElementById('resetView');
    const toggleSpinBtn = document.getElementById('toggleSpin');
    
    if (resetViewBtn) {
        resetViewBtn.addEventListener('click', () => {
            if (nglStage) {
                nglStage.autoView();
            }
        });
    }
    
    if (toggleSpinBtn) {
        toggleSpinBtn.addEventListener('click', () => {
            if (nglStage) {
                isSpinning = !isSpinning;
                nglStage.setSpin(isSpinning);
                toggleSpinBtn.textContent = isSpinning ? 'Stop Spin' : 'Toggle Spin';
            }
        });
    }
}

function loadStructureIntoNGL(pdbContent) {
    if (!nglStage || !pdbContent) return;
    
    // Clear existing structures
    nglStage.removeAllComponents();
    
    // Load PDB from string
    const blob = new Blob([pdbContent], { type: 'text/plain' });
    
    nglStage.loadFile(blob, { ext: 'pdb' }).then(component => {
        currentComponent = component;
        
        // Get available chains (unique only)
        const chainSet = new Set();
        component.structure.eachChain(chain => {
            chainSet.add(chain.chainname);
        });
        availableChains = Array.from(chainSet).sort();
        
        // Update chain selector
        updateChainSelector();
        
        // Add cartoon representation (grey by default)
        component.addRepresentation('cartoon', {
            color: 'grey',
            aspectRatio: 4,
            scale: 1.5
        });
        
        // Center and zoom
        component.autoView();
        
        // Optional: add subtle spin
        nglStage.setSpin(false);
    }).catch(error => {
        console.error('Error loading structure:', error);
    });
}

function updateChainSelector() {
    const chainSelect = document.getElementById('chainSelect');
    if (!chainSelect) return;
    
    // Clear existing options
    chainSelect.innerHTML = '<option value="all">All Chains</option>';
    
    // Add option for each chain
    availableChains.forEach(chain => {
        const option = document.createElement('option');
        option.value = chain;
        option.textContent = `Chain ${chain}`;
        chainSelect.appendChild(option);
    });
    
    // Enable selector if multiple chains
    chainSelect.disabled = availableChains.length <= 1;
}

function handleChainChange(event) {
    if (!currentComponent) return;
    
    const selectedChain = event.target.value;
    
    // Remove all existing representations
    currentComponent.removeAllRepresentations();
    
    // Determine selection string
    const sele = selectedChain === 'all' ? '' : `:${selectedChain}`;
    
    // Add cartoon representation for selected chain(s) - grey
    currentComponent.addRepresentation('cartoon', {
        sele: sele,
        color: 'grey',
        aspectRatio: 4,
        scale: 1.5
    });
    
    // Re-center view
    currentComponent.autoView(sele);
}

function highlightEntanglement(rowData) {
    if (!currentComponent) return;
    
    const chain = rowData.chain || '';
    const i = parseInt(rowData.i);
    const j = parseInt(rowData.j);
    const crossingsN = rowData.crossingsN || '';
    const crossingsC = rowData.crossingsC || '';
    
    // Parse crossing residues (comma-separated)
    const parseResidues = (str) => {
        if (!str || str === '') return [];
        return str.split(',').map(r => parseInt(r.trim())).filter(r => !isNaN(r));
    };
    
    const crossingResN = parseResidues(crossingsN);
    const crossingResC = parseResidues(crossingsC);
    const allCrossings = [...crossingResN, ...crossingResC];
    
    // Build selection strings
    const chainSele = chain ? `:${chain}` : '';
    
    // Remove existing highlight representations (keep base cartoon/ball+stick)
    currentComponent.reprList.forEach((repr, index) => {
        if (repr.name && repr.name.startsWith('highlight_')) {
            currentComponent.removeRepresentation(repr);
        }
    });
    
    // 1. Color residues i to j RED (cartoon)
    const loopSele = `${chainSele} and ${i}-${j}`;
    currentComponent.addRepresentation('cartoon', {
        sele: loopSele,
        color: 'red',
        aspectRatio: 5,
        scale: 1.8,
        name: 'highlight_loop'
    });
    
    // 2. Color crossing residues ±3 BLUE (cartoon)
    if (allCrossings.length > 0) {
        const crossingSelections = [];
        allCrossings.forEach(res => {
            const start = Math.max(1, res - 3);
            const end = res + 3;
            crossingSelections.push(`${start}-${end}`);
        });
        const crossingSele = `${chainSele} and (${crossingSelections.join(' or ')})`;
        currentComponent.addRepresentation('cartoon', {
            sele: crossingSele,
            color: 'blue',
            aspectRatio: 5,
            scale: 1.8,
            name: 'highlight_crossings'
        });
    }
    
    // 3. Add VDW (spacefill) for i and j in RED
    const loopEndsSele = `${chainSele} and (${i} or ${j})`;
    currentComponent.addRepresentation('spacefill', {
        sele: loopEndsSele,
        color: 'red',
        scale: 0.8,
        name: 'highlight_vdw_loop'
    });
    
    // 4. Add VDW (spacefill) for crossing residues in BLUE
    if (allCrossings.length > 0) {
        const crossingVdwSele = `${chainSele} and (${allCrossings.join(' or ')})`;
        currentComponent.addRepresentation('spacefill', {
            sele: crossingVdwSele,
            color: 'blue',
            scale: 0.8,
            name: 'highlight_vdw_crossings'
        });
    }
    
    // Center view on the entanglement region
    const viewSele = `${chainSele} and ${Math.min(i, ...allCrossings)}-${Math.max(j, ...allCrossings)}`;
    currentComponent.autoView(viewSele, 500);
    
    console.log(`Highlighted entanglement: i=${i}, j=${j}, crossings=${allCrossings.join(',')}`);
}

function clearEntanglementHighlight() {
    if (!currentComponent) return;
    
    // Remove all highlight representations
    const reprToRemove = [];
    currentComponent.reprList.forEach((repr) => {
        if (repr.name && repr.name.startsWith('highlight_')) {
            reprToRemove.push(repr);
        }
    });
    
    reprToRemove.forEach(repr => {
        currentComponent.removeRepresentation(repr);
    });
    
    // Deselect table row
    if (resultsTable) {
        resultsTable.deselectRow();
    }
    
    // Reset view
    currentComponent.autoView();
    
    console.log('Cleared entanglement highlight');
}
