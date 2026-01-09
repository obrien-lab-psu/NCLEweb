# NCLEweb - Database-Backed Job Management System

## Overview

The NCLEweb application now includes a complete database-backed job management system that allows users to:
- Submit analysis jobs with metadata (email, job name, UniProt ID, description)
- Track job status (pending, processing, completed, failed)
- Browse all submitted jobs
- View detailed results for completed jobs
- Receive email notifications upon completion

## System Architecture

### Backend (FastAPI + SQLite)
- **API Server**: FastAPI running on port 8000
- **Database**: SQLite with SQLAlchemy ORM (`data/ncle.db`)
- **Backup**: Automatic JSON backup after each job (`data/jobs_backup.json`)
- **Email**: SMTP-based notifications (optional)

### Frontend (HTML/CSS/JavaScript)
- **Landing Page** (`landing.html` → `index.html`): Entry point with two actions
- **Submit Page** (`submit.html`): Job submission form
- **Browse Page** (`browse.html`): Job listing with Tabulator table
- **Results Page** (`results.html`): Detailed results viewer with NGL molecular viewer

### Database Schema

**Job Table:**
- `job_id` (UUID, primary key)
- `email` (string)
- `job_name` (string)
- `uniprot_id` (string, optional)
- `description` (text, optional)
- `pdb_filename` (string)
- `pdb_id` (string, extracted from file)
- `created_at` (datetime)
- `completed_at` (datetime, nullable)
- `status` (enum: pending, processing, completed, failed)
- `error_message` (text, nullable)
- `num_entanglements` (integer)
- `num_chains` (integer)

**Result Table:**
- `result_id` (integer, primary key)
- `job_id` (UUID, foreign key)
- `chain` (string)
- `i`, `j` (integers - loop endpoints)
- `crossingsN`, `crossingsC` (text - comma-separated residue numbers)
- `gn`, `gc` (floats - Gaussian entanglement values)
- `GLNn`, `GLNc`, `TLNn`, `TLNc` (integers)
- `CCbond` (boolean)
- `ENT` (boolean)

## API Endpoints

### 1. Health Check
```
GET /
```
Returns: `{"status": "online", "service": "NCLE Gaussian Entanglement API", "version": "1.0.0"}`

### 2. Submit Job
```
POST /api/submit-job
Content-Type: multipart/form-data

Fields:
- email (required): User's email for notifications
- job_name (required): Name for this analysis job
- file (required): PDB file (max 20 MB)
- uniprot_id (optional): UniProt identifier
- description (optional): Job description
```

Returns:
```json
{
  "success": true,
  "job_id": "ea6a730e-a451-465c-ad57-a4f633c2f69b",
  "message": "Job submitted successfully. You will receive an email when processing is complete."
}
```

### 3. List Jobs
```
GET /api/jobs?limit=100&offset=0
```

Returns:
```json
{
  "success": true,
  "total": 10,
  "count": 10,
  "offset": 0,
  "jobs": [
    {
      "job_id": "...",
      "job_name": "Test Analysis",
      "status": "completed",
      "pdb_id": "1PKL",
      "email": "u***@example.com",
      "num_entanglements": 7881,
      ...
    }
  ]
}
```

### 4. Get Job Details
```
GET /api/jobs/{job_id}
```

Returns:
```json
{
  "success": true,
  "pdb_id": "1PKL",
  "job_name": "Test Analysis",
  "status": "completed",
  "created_at": "2026-01-09T20:37:08.905940",
  "completed_at": "2026-01-09T20:37:49.012566",
  "results": [
    {
      "chain": "A",
      "i": 10,
      "j": 50,
      "g": 0.123,
      ...
    }
  ]
}
```

## Configuration

### SMTP Email Notifications (Optional)

To enable email notifications, set these environment variables:

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your_email@gmail.com"
export SMTP_PASS="your_app_password"
export FROM_EMAIL="noreply@yourserver.com"
```

**For Gmail:**
1. Enable 2-factor authentication
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use the app password as `SMTP_PASS`

**Without SMTP configuration:**
- Jobs will still be processed
- A warning will appear in logs: "Email notifications disabled - SMTP credentials not configured"
- Users won't receive email notifications

### Starting the Backend

```bash
cd /home/ianms/git_repos/NCLEweb
source venv/bin/activate
uvicorn py.backend:app --host 0.0.0.0 --port 8000
```

Or run in background:
```bash
nohup uvicorn py.backend:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
```

### Accessing the Application

1. Open a web browser
2. Navigate to the HTML files (since static file serving is not configured):
   - Landing page: `file:///home/ianms/git_repos/NCLEweb/landing.html`
   - Or set up a simple HTTP server:
     ```bash
     python3 -m http.server 8080
     ```
     Then visit: `http://localhost:8080/landing.html`

## Data Storage

### Database Location
- **SQLite file**: `/home/ianms/git_repos/NCLEweb/data/ncle.db`
- **JSON backup**: `/home/ianms/git_repos/NCLEweb/data/jobs_backup.json`

### PDB Files
- **NOT stored permanently** - PDB files are deleted after processing
- Only the filename and extracted PDB ID are stored in the database
- 3D visualization in results.html will show a "not available" message

**To enable PDB storage:**
1. Modify `py/backend.py` to save PDB files to a permanent location
2. Add a `pdb_content` or `pdb_path` field to the database
3. Update the API to return PDB content in `/api/jobs/{job_id}`

### Data Retention
- Jobs are stored **forever** (no automatic deletion)
- Email addresses are masked in public views: `test@example.com` → `t***@example.com`
- Full email only visible in database and JSON backup

## Privacy & Security

### Current Implementation
- Email addresses are partially masked in the public browse interface
- Email addresses are visible in:
  - Database (`data/ncle.db`)
  - JSON backup (`data/jobs_backup.json`)
  - Email notifications (obviously)
  - Admin access to the server

### Recommendations for Production
1. **HTTPS**: Use a reverse proxy (Apache/Nginx) with SSL/TLS
2. **CORS**: Configure proper CORS policies in FastAPI
3. **Rate Limiting**: Add rate limiting to prevent abuse
4. **File Validation**: Enhanced PDB file validation
5. **Authentication**: Add admin authentication for sensitive operations
6. **Backup Strategy**: Regular database backups
7. **Monitoring**: Log monitoring and error alerting
8. **Firewall**: Restrict API access to known IPs if needed

## Testing the System

### Test Job Submission (CLI)
```bash
curl -X POST http://localhost:8000/api/submit-job \
  -F "email=test@example.com" \
  -F "job_name=Test 1PKL Analysis" \
  -F "uniprot_id=P12345" \
  -F "description=Testing the system" \
  -F "file=@structure_files/1PKL.pdb"
```

Expected response:
```json
{
  "success": true,
  "job_id": "ea6a730e-a451-465c-ad57-a4f633c2f69b",
  "message": "Job submitted successfully..."
}
```

### View Jobs
```bash
curl http://localhost:8000/api/jobs | python3 -m json.tool
```

### View Job Results
```bash
curl http://localhost:8000/api/jobs/{job_id} | python3 -m json.tool
```

## Troubleshooting

### Backend Not Starting
- Check if port 8000 is already in use: `lsof -i :8000`
- Check logs: `tail -f backend.log`
- Verify virtual environment is activated: `which python`

### Jobs Stay in "Processing" State
- Check backend logs for errors
- Verify the gaussian_entanglement.py script is working
- Check file permissions on uploaded files

### Email Notifications Not Sent
- Verify SMTP environment variables are set
- Check backend logs for SMTP errors
- Test SMTP credentials manually

### Database Errors
- Check if `data/` directory exists and is writable
- Verify database file permissions
- Check SQLite version: `sqlite3 --version`

### Results Page Shows "No 3D Visualization"
- This is expected - PDB files are not stored after processing
- To enable, modify backend to store PDB content

## Future Enhancements

1. **PDB Storage**: Option to permanently store PDB files
2. **Job Cancellation**: Allow users to cancel pending jobs
3. **Admin Dashboard**: Monitoring and management interface
4. **API Authentication**: JWT tokens for secure API access
5. **User Accounts**: Multi-user support with authentication
6. **Job History**: Track multiple submissions per user
7. **Export Options**: Additional export formats (JSON, XML)
8. **Batch Processing**: Submit multiple PDB files at once
9. **Progress Updates**: WebSocket-based real-time progress
10. **Advanced Filtering**: Search by date range, structure properties

## Files Changed in This Update

### New Files
- `py/database.py` - SQLAlchemy database layer
- `py/email_notifier.py` - SMTP email notifications
- `landing.html` - New homepage
- `submit.html` - Job submission form
- `browse.html` - Job browser
- `results.html` - Results viewer
- `SETUP_GUIDE.md` - This file

### Modified Files
- `py/backend.py` - Added 3 new endpoints, database integration
- `index.html` - Now a symlink to landing.html
- `old_index.html` - Backup of original upload interface

### Dependencies Added
- `sqlalchemy>=2.0.0`
- `aiosqlite>=0.17.0`

## Contact & Support

For issues, questions, or contributions, please refer to the project repository.

---
Last updated: January 9, 2026
