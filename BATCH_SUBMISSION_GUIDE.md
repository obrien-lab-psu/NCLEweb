# Batch Submission Feature

## Overview

The NCLE Web application now supports batch submissions to allow users to analyze multiple protein structures efficiently. The system includes a priority-based queuing mechanism that ensures smaller jobs aren't starved while larger jobs process.

## Features

### 1. **Multiple File Submission (Same Parameters)**
Submit multiple `.pdb` files with identical analysis parameters through a single form.

**Use Case**: Analyzing multiple proteins from the same organism with the same settings.

**Endpoint**: `POST /api/submit-batch-multiple`

**Parameters**:
- `email` - User's email
- `batch_name` - Name for the batch
- `files` - List of .pdb files (max 100 per batch)
- `organism` - Organism for clustering (Ecoli, Human, Yeast, or Custom)
- `structure_type` - EXP or AF
- `coarse_grained` - Use C-alpha only (boolean)
- `ca_contact` - Use C-alpha contacts (boolean)
- `cluster_cutoff` - Custom clustering cutoff (optional, for Custom organisms)
- `ent_detection_method` - 1=GLN-based, 2=TLN-based, 3=Consensus (default)
- `uniprot_id` - UniProt ID for feature generation (optional)
- `generate_features` - Generate entanglement features (boolean)

### 2. **ZIP File Submission (Per-File Parameters)**
Submit a ZIP archive containing multiple `.pdb` files and a `params.csv` file that specifies parameters for each structure.

**Use Case**: Analyzing diverse structures with different analysis settings.

**Endpoint**: `POST /api/submit-batch-zip`

**ZIP Structure**:
```
batch.zip
├── protein1.pdb
├── protein2.pdb
├── protein3.pdb
└── params.csv
```

**params.csv Format**:
```csv
pdb_filename,organism,coarse_grained,ca_contact,cluster_cutoff,structure_type,ent_detection_method
protein1.pdb,Ecoli,false,false,,EXP,3
protein2.pdb,Human,true,false,,EXP,3
protein3.pdb,Custom,false,false,5.0,EXP,3
```

**Parameters**:
- `email` - User's email
- `batch_name` - Name for the batch
- `zip_file` - ZIP archive (max 500 MB)
- `uniprot_id` - UniProt ID (optional, applies to all jobs if provided)
- `generate_features` - Generate features for all jobs (boolean)

## Priority Queue System

### Architecture

The queuing system uses a priority-based scheduler with resource allocation slots:

**Priority Levels** (0 = highest priority):
- Priority 0: Single small jobs (< 100 KB) - **High priority**
- Priority 1: Single large jobs (≥ 100 KB) - **Medium priority**
- Priority 2: Batch submissions - **Low priority**

**Resource Allocation**:
- Total worker slots: 4
- Small jobs: Up to 4 concurrent (when no large jobs running)
- Large jobs: 1 maximum (blocks small jobs)
- Strategy: Small jobs can run alongside each other, but large jobs run in isolation

### Why This Design?

1. **No Job Starvation**: Small jobs get priority and execute quickly, even during large job processing
2. **Efficient Resource Use**: Multiple small jobs utilize resources better than idle workers
3. **User Experience**: Users submitting small structures get results faster
4. **Flexibility**: Large jobs still run, but don't monopolize all resources

### Job Size Calculation

File size is used as a proxy for processing time:
- **Small**: < 100 KB estimated file size
- **Large**: ≥ 100 KB estimated file size

## API Endpoints

### Submit Multiple Files (Same Parameters)
```
POST /api/submit-batch-multiple
Content-Type: multipart/form-data

{
  "email": "user@example.com",
  "batch_name": "E. coli structures",
  "files": [file1.pdb, file2.pdb, file3.pdb],
  "organism": "Ecoli",
  "structure_type": "EXP",
  "coarse_grained": false,
  "ca_contact": false,
  "ent_detection_method": 3
}
```

**Response**:
```json
{
  "success": true,
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_ids": [
    "job-uuid-1",
    "job-uuid-2", 
    "job-uuid-3"
  ],
  "total_jobs": 3,
  "errors": [],
  "message": "Batch submission created with 3 jobs"
}
```

### Submit ZIP File (Per-File Parameters)
```
POST /api/submit-batch-zip
Content-Type: multipart/form-data

{
  "email": "user@example.com",
  "batch_name": "Mixed structures",
  "zip_file": batch.zip,
  "uniprot_id": "P12345",
  "generate_features": true
}
```

**Response**:
```json
{
  "success": true,
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_ids": ["job-uuid-1", "job-uuid-2"],
  "total_jobs": 2,
  "errors": ["protein3.pdb: File corrupted"],
  "message": "Batch submission created with 2 jobs"
}
```

### Get Batch Status
```
GET /api/batch/{batch_id}/status
```

**Response**:
```json
{
  "success": true,
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": {
    "batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "total_jobs": 3,
    "status_breakdown": {
      "completed": 2,
      "processing": 1,
      "pending": 0
    },
    "total_entanglements": 42,
    "total_hq_entanglements": 15,
    "total_clustered_entanglements": 8,
    "jobs": [...]
  },
  "queue": {
    "batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "pending_jobs": ["job-uuid-2"],
    "running_jobs": ["job-uuid-1"],
    "total_pending": 1,
    "total_running": 1
  }
}
```

### Download Batch Results
```
GET /api/batch/{batch_id}/download
```

Returns a ZIP file containing:
```
batch_download.zip
├── protein1.pdb_uuid1/
│   ├── Native_GE_results.csv
│   ├── Native_HQ_GE_results.csv
│   ├── Native_clustered_HQ_GE_results.csv
│   └── Features_results.csv
├── protein2.pdb_uuid2/
│   ├── ...
└── batch_summary.csv
```

### Get Queue Status (Monitoring)
```
GET /api/queue/status
```

**Response**:
```json
{
  "success": true,
  "queue_status": {
    "queue_length": 5,
    "running_jobs": 2,
    "small_jobs_running": 2,
    "large_jobs_running": 0,
    "total_slots_used": 2,
    "total_slots": 4
  }
}
```

## Database Changes

### New Job Fields

The `jobs` table now includes batch-related fields:

| Column | Type | Purpose |
|--------|------|---------|
| `batch_id` | String | UUID linking jobs in a batch (NULL for single jobs) |
| `estimated_size` | Integer | Estimated file size in bytes for queue prioritization |
| `queue_priority` | Integer | Priority level (0=high, 2=low) |
| `queue_position` | Integer | Position in queue when submitted |
| `status` | String | Added 'queued' status alongside existing statuses |

## Implementation Details

### Job Queue Manager (`py/job_queue.py`)

- **JobQueueManager**: Thread-safe priority queue implementation
- **QueuedJob**: Data class representing a job in queue
- **JobPriority**: Enum for priority levels
- **get_queue_manager()**: Singleton function to get global queue instance

**Key Methods**:
- `enqueue_job()` - Add job to queue
- `dequeue_job()` - Move job from queue to running
- `finish_job()` - Remove job from running
- `get_next_runnable_job()` - Get next job respecting resource constraints
- `get_queue_status()` - Current queue statistics
- `get_batch_status()` - Status of batch jobs

### Batch Submission Handler (`py/batch_submission.py`)

- **parse_params_csv()** - Parse CSV parameter file
- **extract_batch_zip()** - Extract PDB files from ZIP
- **create_batch_jobs()** - Create multiple jobs and enqueue them
- **get_batch_download_zip()** - Aggregate results into ZIP

### Backend Integration (`py/backend.py`)

New endpoints added:
- `POST /api/submit-batch-multiple` - Multiple files, same params
- `POST /api/submit-batch-zip` - ZIP with params.csv
- `GET /api/batch/{batch_id}/status` - Batch status
- `GET /api/batch/{batch_id}/download` - Download batch results
- `GET /api/queue/status` - Monitor queue

## Limitations & Constraints

### Per-Batch
- Maximum 100 files per `submit-batch-multiple` request
- Maximum 500 MB per ZIP file for `submit-batch-zip`

### Per-File
- Maximum 20 MB per individual PDB file
- Files must have `.pdb` extension

### Queue Behavior
- No hard limit on total jobs (unlimited submissions allowed)
- Small jobs execute with priority
- Batch jobs don't block future submissions

## Frontend Integration

The `submit.html` and `app.js` files should be updated to:

1. **Add multiple file selection**:
   - Use HTML5 `<input multiple>` attribute
   - Display list of selected files
   - Show batch-specific form options

2. **Add ZIP upload option**:
   - Alternative form for ZIP submission
   - Help text explaining ZIP structure
   - Example params.csv download

3. **Add batch tracking**:
   - Display batch ID after submission
   - Show status of all jobs in batch
   - Enable batch results download when complete

4. **Add queue monitoring** (optional):
   - Display queue status widget
   - Show estimated wait times
   - Indicate resource utilization

## Example Usage

### Python Example: Batch via Multiple Files

```python
import requests

files = [
    ('files', open('protein1.pdb', 'rb')),
    ('files', open('protein2.pdb', 'rb')),
]

data = {
    'email': 'user@example.com',
    'batch_name': 'My batch',
    'organism': 'Ecoli',
    'structure_type': 'EXP',
    'ent_detection_method': 3
}

response = requests.post(
    'https://ncleweb.org/api/submit-batch-multiple',
    data=data,
    files=files
)

batch_id = response.json()['batch_id']
print(f"Batch submitted: {batch_id}")
```

### Python Example: Batch via ZIP

```python
import requests
import zipfile

# Create ZIP with PDB files and params.csv
with zipfile.ZipFile('batch.zip', 'w') as z:
    z.write('protein1.pdb')
    z.write('protein2.pdb')
    z.write('params.csv')

# Submit
with open('batch.zip', 'rb') as f:
    response = requests.post(
        'https://ncleweb.org/api/submit-batch-zip',
        data={
            'email': 'user@example.com',
            'batch_name': 'My batch'
        },
        files={'zip_file': f}
    )

batch_id = response.json()['batch_id']
print(f"Batch submitted: {batch_id}")
```

## Monitoring & Troubleshooting

### Check Queue Status
```bash
curl https://ncleweb.org/api/queue/status
```

### Check Batch Progress
```bash
curl https://ncleweb.org/api/batch/{batch_id}/status
```

### Common Issues

1. **"params.csv references 'file.pdb' but file not found"**
   - Ensure all PDB files in params.csv are present in ZIP

2. **"ZIP file must contain 'params.csv'"**
   - params.csv is required in ZIP root directory

3. **"pdb_filename must end with .pdb"**
   - Check CSV column values don't have extra whitespace

4. **Max 100 files per batch**
   - Split large batches into multiple submissions

## Future Enhancements

1. **Resumable uploads** - Support for re-upload of failed jobs
2. **Email notifications** - Per-job or per-batch completion emails
3. **Bandwidth throttling** - Limit concurrent downloads
4. **Job prioritization** - Allow users to prioritize jobs within batch
5. **Estimated wait times** - Better queue time predictions
6. **Partial results** - Stream results as individual jobs complete
