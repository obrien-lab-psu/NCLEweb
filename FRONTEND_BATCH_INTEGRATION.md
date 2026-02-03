# Frontend Integration Guide - Batch Submission

This guide explains how to update the frontend (`submit.html` and `app.js`) to support batch submissions.

## Overview

The frontend needs to support:
1. **Multiple file selection** - Users can select multiple .pdb files at once
2. **ZIP file upload** - Users can upload a pre-configured ZIP file
3. **Batch tracking** - Display batch ID and track status of all jobs

## HTML Changes (submit.html)

### Add Tab Navigation

Add tabs to toggle between single file, multiple files, and ZIP submission:

```html
<div class="submission-tabs">
  <button class="tab-button active" onclick="switchTab('single')">Single File</button>
  <button class="tab-button" onclick="switchTab('multiple')">Multiple Files</button>
  <button class="tab-button" onclick="switchTab('zip')">ZIP File</button>
</div>
```

### Single File Form (existing, keep as-is)
```html
<div id="single-form" class="tab-content active">
  <!-- Existing single file form -->
  <input type="file" id="pdbFile" accept=".pdb">
  <!-- ... rest of form ... -->
</div>
```

### Multiple Files Form

```html
<div id="multiple-form" class="tab-content">
  <div class="form-section">
    <label>Email</label>
    <input type="email" id="multiEmail" required>
  </div>
  
  <div class="form-section">
    <label>Batch Name</label>
    <input type="text" id="multiBatchName" placeholder="e.g., E. coli structures" required>
  </div>
  
  <div class="form-section">
    <label>PDB Files (select multiple)</label>
    <input type="file" id="multiPdbFiles" accept=".pdb" multiple required>
    <div id="multiFileList" class="file-list"></div>
  </div>
  
  <div class="form-section">
    <label>Organism</label>
    <select id="multiOrganism">
      <option value="Ecoli">E. coli</option>
      <option value="Human">Human</option>
      <option value="Yeast">Yeast</option>
      <option value="Custom">Custom</option>
    </select>
  </div>
  
  <!-- Additional options (same as single file form) -->
  <div class="form-section">
    <label>Structure Type</label>
    <select id="multiStructureType">
      <option value="EXP">Experimental (PDB)</option>
      <option value="AF">AlphaFold</option>
    </select>
  </div>
  
  <div class="form-section">
    <label>Entanglement Detection Method</label>
    <select id="multiEntMethod">
      <option value="3">Consensus (GLN + TLN)</option>
      <option value="1">GLN-based</option>
      <option value="2">TLN-based</option>
    </select>
  </div>
  
  <div class="form-section checkbox">
    <label>
      <input type="checkbox" id="multiCoarseGrained">
      Coarse-grained (C-alpha only)
    </label>
  </div>
  
  <div class="form-section checkbox">
    <label>
      <input type="checkbox" id="multiCaContact">
      C-alpha contacts
    </label>
  </div>
  
  <button onclick="submitMultipleBatch()" class="submit-btn">Submit Batch</button>
</div>
```

### ZIP File Form

```html
<div id="zip-form" class="tab-content">
  <div class="form-section">
    <label>Email</label>
    <input type="email" id="zipEmail" required>
  </div>
  
  <div class="form-section">
    <label>Batch Name</label>
    <input type="text" id="zipBatchName" placeholder="e.g., My batch analysis" required>
  </div>
  
  <div class="form-section">
    <label>ZIP File</label>
    <input type="file" id="zipFile" accept=".zip" required>
    <div class="help-text">
      ZIP must contain .pdb files and params.csv file
      <a href="#" onclick="downloadParamsTemplate()">Download params.csv template</a>
    </div>
  </div>
  
  <div class="form-section">
    <label>UniProt ID (optional, for feature generation)</label>
    <input type="text" id="zipUniprotId" placeholder="e.g., P12345">
  </div>
  
  <div class="form-section checkbox">
    <label>
      <input type="checkbox" id="zipGenerateFeatures">
      Generate entanglement features
    </label>
  </div>
  
  <button onclick="submitZipBatch()" class="submit-btn">Submit ZIP Batch</button>
</div>
```

### Batch Status Display

```html
<div id="batch-status-page" class="page" style="display: none;">
  <div class="status-header">
    <h2>Batch Status</h2>
    <div class="batch-id">
      Batch ID: <code id="batchIdDisplay"></code>
      <button onclick="copyBatchId()">Copy</button>
    </div>
  </div>
  
  <div class="batch-summary">
    <div class="summary-card">
      <div class="summary-label">Total Jobs</div>
      <div class="summary-value" id="totalJobsDisplay">0</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">Completed</div>
      <div class="summary-value" id="completedJobsDisplay">0</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">Processing</div>
      <div class="summary-value" id="processingJobsDisplay">0</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">Pending</div>
      <div class="summary-value" id="pendingJobsDisplay">0</div>
    </div>
  </div>
  
  <div class="queue-info">
    <h3>Queue Status</h3>
    <div id="queueDetails"></div>
  </div>
  
  <div class="jobs-list">
    <h3>Jobs</h3>
    <table id="batchJobsTable">
      <thead>
        <tr>
          <th>Filename</th>
          <th>Status</th>
          <th>Results</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="batchJobsTableBody">
      </tbody>
    </table>
  </div>
  
  <div class="batch-actions">
    <button id="downloadBatchBtn" onclick="downloadBatchResults()" style="display: none;">
      Download All Results
    </button>
    <button onclick="backToSubmit()">New Submission</button>
  </div>
</div>
```

## JavaScript Changes (app.js)

### Tab Navigation

```javascript
function switchTab(tabName) {
  // Hide all tabs
  document.querySelectorAll('.tab-content').forEach(tab => {
    tab.classList.remove('active');
  });
  document.querySelectorAll('.tab-button').forEach(btn => {
    btn.classList.remove('active');
  });
  
  // Show selected tab
  document.getElementById(tabName + '-form').classList.add('active');
  event.target.classList.add('active');
}
```

### File List Display

```javascript
document.getElementById('multiPdbFiles').addEventListener('change', function() {
  const fileList = document.getElementById('multiFileList');
  fileList.innerHTML = '';
  
  const files = Array.from(this.files);
  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  
  const listHtml = `
    <div class="file-count">${files.length} file(s) selected (${formatBytes(totalSize)})</div>
    <ul>
      ${files.map((f, i) => `<li>${f.name} (${formatBytes(f.size)})</li>`).join('')}
    </ul>
  `;
  
  fileList.innerHTML = listHtml;
});

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}
```

### Multiple Files Submission

```javascript
async function submitMultipleBatch() {
  const email = document.getElementById('multiEmail').value;
  const batchName = document.getElementById('multiBatchName').value;
  const files = document.getElementById('multiPdbFiles').files;
  
  if (!email || !batchName || files.length === 0) {
    alert('Please fill in all required fields');
    return;
  }
  
  // Build form data
  const formData = new FormData();
  formData.append('email', email);
  formData.append('batch_name', batchName);
  formData.append('organism', document.getElementById('multiOrganism').value);
  formData.append('structure_type', document.getElementById('multiStructureType').value);
  formData.append('ent_detection_method', document.getElementById('multiEntMethod').value);
  formData.append('coarse_grained', document.getElementById('multiCoarseGrained').checked);
  formData.append('ca_contact', document.getElementById('multiCaContact').checked);
  
  // Add all files
  for (let file of files) {
    formData.append('files', file);
  }
  
  try {
    showProcessingPage('Submitting batch...');
    
    const response = await fetch(`${API_BASE_URL}/api/submit-batch-multiple`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Submission failed');
    }
    
    const result = await response.json();
    
    // Store batch info and show status
    localStorage.setItem('currentBatchId', result.batch_id);
    showBatchStatus(result.batch_id);
    
  } catch (error) {
    alert(`Error: ${error.message}`);
    hideProcessingPage();
  }
}
```

### ZIP File Submission

```javascript
async function submitZipBatch() {
  const email = document.getElementById('zipEmail').value;
  const batchName = document.getElementById('zipBatchName').value;
  const zipFile = document.getElementById('zipFile').files[0];
  const uniprotId = document.getElementById('zipUniprotId').value;
  const generateFeatures = document.getElementById('zipGenerateFeatures').checked;
  
  if (!email || !batchName || !zipFile) {
    alert('Please fill in all required fields');
    return;
  }
  
  const formData = new FormData();
  formData.append('email', email);
  formData.append('batch_name', batchName);
  formData.append('zip_file', zipFile);
  
  if (uniprotId) {
    formData.append('uniprot_id', uniprotId);
  }
  
  formData.append('generate_features', generateFeatures);
  
  try {
    showProcessingPage('Processing ZIP file...');
    
    const response = await fetch(`${API_BASE_URL}/api/submit-batch-zip`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Submission failed');
    }
    
    const result = await response.json();
    
    // Show any errors from processing
    if (result.errors && result.errors.length > 0) {
      console.warn('Processing errors:', result.errors);
    }
    
    localStorage.setItem('currentBatchId', result.batch_id);
    showBatchStatus(result.batch_id);
    
  } catch (error) {
    alert(`Error: ${error.message}`);
    hideProcessingPage();
  }
}
```

### Batch Status Polling

```javascript
let batchStatusInterval;

async function showBatchStatus(batchId) {
  // Hide upload page, show status page
  document.getElementById('uploadPage').style.display = 'none';
  document.getElementById('batch-status-page').style.display = 'block';
  document.getElementById('batchIdDisplay').textContent = batchId.substring(0, 8);
  
  // Start polling for updates
  updateBatchStatus(batchId);
  batchStatusInterval = setInterval(() => updateBatchStatus(batchId), 2000);
}

async function updateBatchStatus(batchId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/batch/${batchId}/status`);
    
    if (!response.ok) {
      throw new Error('Failed to fetch batch status');
    }
    
    const data = await response.json();
    const status = data.status;
    const queue = data.queue;
    
    // Update summary cards
    document.getElementById('totalJobsDisplay').textContent = status.total_jobs;
    document.getElementById('completedJobsDisplay').textContent = status.status_breakdown.completed || 0;
    document.getElementById('processingJobsDisplay').textContent = status.status_breakdown.processing || 0;
    document.getElementById('pendingJobsDisplay').textContent = status.status_breakdown.pending || 0;
    
    // Update queue info
    updateQueueDisplay(queue);
    
    // Update jobs table
    updateBatchJobsTable(status.jobs);
    
    // Check if batch is complete
    const allDone = !status.status_breakdown.pending && !status.status_breakdown.processing;
    if (allDone) {
      clearInterval(batchStatusInterval);
      document.getElementById('downloadBatchBtn').style.display = 'block';
    }
    
  } catch (error) {
    console.error('Error updating batch status:', error);
  }
}

function updateQueueDisplay(queue) {
  const queueHtml = `
    <div class="queue-stat">
      <span>Pending:</span> <strong>${queue.total_pending}</strong>
    </div>
    <div class="queue-stat">
      <span>Running:</span> <strong>${queue.total_running}</strong>
    </div>
  `;
  document.getElementById('queueDetails').innerHTML = queueHtml;
}

function updateBatchJobsTable(jobs) {
  const tbody = document.getElementById('batchJobsTableBody');
  tbody.innerHTML = '';
  
  jobs.forEach(job => {
    const row = `
      <tr class="job-row ${job.status}">
        <td>${job.pdb_filename}</td>
        <td class="status-${job.status}">${job.status}</td>
        <td>${job.num_entanglements || '-'}</td>
        <td>
          ${job.status === 'completed' ? 
            `<a href="results.html?job_id=${job.job_id}">View</a>` : 
            '-'
          }
        </td>
      </tr>
    `;
    tbody.innerHTML += row;
  });
}

async function downloadBatchResults() {
  const batchId = localStorage.getItem('currentBatchId');
  
  if (!batchId) {
    alert('Batch ID not found');
    return;
  }
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/batch/${batchId}/download`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Download failed');
    }
    
    // Get filename from Content-Disposition header
    const filename = response.headers
      .get('content-disposition')
      .split('filename=')[1]
      .replace(/"/g, '');
    
    // Download the file
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

function copyBatchId() {
  const batchId = document.getElementById('batchIdDisplay').textContent;
  navigator.clipboard.writeText(batchId).then(() => {
    alert('Batch ID copied to clipboard');
  });
}

function backToSubmit() {
  clearInterval(batchStatusInterval);
  document.getElementById('batch-status-page').style.display = 'none';
  document.getElementById('uploadPage').style.display = 'block';
}

function downloadParamsTemplate() {
  const csv = `pdb_filename,organism,coarse_grained,ca_contact,cluster_cutoff,structure_type,ent_detection_method
protein1.pdb,Ecoli,false,false,,EXP,3
protein2.pdb,Human,true,false,,EXP,3
protein3.pdb,Custom,false,false,5.0,EXP,3`;
  
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'params.csv';
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}
```

## CSS Styling

Add to `styles.css`:

```css
/* Tab Navigation */
.submission-tabs {
  display: flex;
  border-bottom: 2px solid #ddd;
  margin-bottom: 20px;
}

.tab-button {
  padding: 10px 20px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 16px;
  border-bottom: 3px solid transparent;
  transition: all 0.3s ease;
}

.tab-button:hover {
  background-color: #f5f5f5;
}

.tab-button.active {
  border-bottom-color: #007bff;
  color: #007bff;
}

/* Tab Content */
.tab-content {
  display: none;
}

.tab-content.active {
  display: block;
}

/* File List */
.file-list {
  background-color: #f9f9f9;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 10px;
  margin-top: 10px;
}

.file-count {
  font-weight: bold;
  margin-bottom: 5px;
  color: #333;
}

.file-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.file-list li {
  padding: 5px;
  color: #666;
  font-size: 14px;
}

/* Batch Status */
#batch-status-page {
  max-width: 900px;
  margin: 20px auto;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  border-bottom: 2px solid #ddd;
  padding-bottom: 10px;
}

.batch-id {
  display: flex;
  align-items: center;
  gap: 10px;
}

.batch-id code {
  background-color: #f5f5f5;
  padding: 5px 10px;
  border-radius: 4px;
  font-family: monospace;
}

/* Summary Cards */
.batch-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
  margin-bottom: 30px;
}

.summary-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.summary-label {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 10px;
}

.summary-value {
  font-size: 32px;
  font-weight: bold;
}

/* Jobs Table */
#batchJobsTable {
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
}

#batchJobsTable th {
  background-color: #f5f5f5;
  padding: 12px;
  text-align: left;
  border-bottom: 2px solid #ddd;
  font-weight: bold;
}

#batchJobsTable td {
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
}

#batchJobsTable tr:hover {
  background-color: #f9f9f9;
}

.status-completed {
  color: #28a745;
  font-weight: bold;
}

.status-processing {
  color: #ffc107;
  font-weight: bold;
}

.status-pending {
  color: #999;
}

.status-failed {
  color: #dc3545;
  font-weight: bold;
}

/* Actions */
.batch-actions {
  display: flex;
  gap: 10px;
  margin-top: 30px;
  justify-content: center;
}

.batch-actions button {
  padding: 10px 20px;
  font-size: 16px;
  cursor: pointer;
  border-radius: 4px;
  border: none;
}

#downloadBatchBtn {
  background-color: #28a745;
  color: white;
}

#downloadBatchBtn:hover {
  background-color: #218838;
}

/* Help Text */
.help-text {
  font-size: 12px;
  color: #666;
  margin-top: 5px;
}

.help-text a {
  color: #007bff;
  text-decoration: none;
}

.help-text a:hover {
  text-decoration: underline;
}
```

## Integration Checklist

- [ ] Add tab navigation to `submit.html`
- [ ] Create multiple files submission form
- [ ] Create ZIP file submission form
- [ ] Add batch status display HTML
- [ ] Implement `switchTab()` function
- [ ] Implement `submitMultipleBatch()` function
- [ ] Implement `submitZipBatch()` function
- [ ] Implement `showBatchStatus()` and polling
- [ ] Add CSS styling
- [ ] Test multiple file submission
- [ ] Test ZIP file submission
- [ ] Test batch status tracking
- [ ] Test batch results download

## Testing

See `BATCH_SUBMISSION_GUIDE.md` for API testing examples.
