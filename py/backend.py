#!/usr/bin/env python3
"""
FastAPI Backend for NCLE Web Application
Provides REST API endpoints for Gaussian Entanglement analysis
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
import tempfile
import os
import sys
import re
import pandas as pd
from pathlib import Path
from datetime import datetime

# Add py directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from api_wrapper import calculate_native_ge
from database import db, Job, Result
from email_notifier import email_notifier

# Initialize FastAPI app
app = FastAPI(
    title="NCLE Gaussian Entanglement API",
    description="API for calculating Native Gaussian Entanglement from PDB structures",
    version="1.0.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "NCLE Gaussian Entanglement API",
        "version": "1.0.0"
    }


@app.post("/api/analyze")
async def analyze_pdb(file: UploadFile = File(...)):
    """
    Analyze a PDB file and return Native Gaussian Entanglement results.
    
    Parameters
    ----------
    file : UploadFile
        PDB file to analyze (must have .pdb extension)
        
    Returns
    -------
    JSONResponse or PlainTextResponse
        Results in CSV format (pipe-delimited)
    """
    
    # Validate file extension
    if not file.filename.endswith('.pdb'):
        raise HTTPException(
            status_code=400, 
            detail="Only PDB files are accepted. File must have .pdb extension."
        )
    
    # Validate file size (max 20 MB)
    MAX_SIZE = 20 * 1024 * 1024  # 20 MB in bytes
    
    # Create temporary file to store upload
    temp_pdb = None
    try:
        # Read file content
        contents = await file.read()
        
        # Check size
        if len(contents) > MAX_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is 20 MB, got {len(contents) / 1024 / 1024:.2f} MB"
            )
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdb', delete=False) as tmp:
            tmp.write(contents)
            temp_pdb = tmp.name
        
        # Run analysis
        result = calculate_native_ge(temp_pdb, cleanup=True)
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {result['error']}"
            )
        
        # Return CSV results with proper content type
        return PlainTextResponse(
            content=result['csv'],
            media_type='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{result["pdb_id"]}_GE.csv"'
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        # Catch any other errors
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during analysis: {str(e)}"
        )
        
    finally:
        # Clean up temporary file
        if temp_pdb and os.path.exists(temp_pdb):
            os.unlink(temp_pdb)


@app.post("/api/analyze-json")
async def analyze_pdb_json(file: UploadFile = File(...)):
    """
    Analyze a PDB file and return results as JSON.
    
    Parameters
    ----------
    file : UploadFile
        PDB file to analyze
        
    Returns
    -------
    JSONResponse
        JSON object with analysis results and metadata
    """
    
    # Validate file extension
    if not file.filename.endswith('.pdb'):
        raise HTTPException(
            status_code=400, 
            detail="Only PDB files are accepted."
        )
    
    # Validate file size
    MAX_SIZE = 20 * 1024 * 1024
    
    temp_pdb = None
    try:
        contents = await file.read()
        
        if len(contents) > MAX_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is 20 MB"
            )
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdb', delete=False) as tmp:
            tmp.write(contents)
            temp_pdb = tmp.name
        
        # Run analysis
        result = calculate_native_ge(temp_pdb, cleanup=True)
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {result['error']}"
            )
        
        # Convert DataFrame to records for JSON
        # Replace NaN/Inf values with None for JSON compatibility
        import numpy as np
        df_clean = result['data'].replace([np.nan, np.inf, -np.inf], None)
        records = df_clean.to_dict(orient='records')
        
        return JSONResponse(content={
            'success': True,
            'pdb_id': result['pdb_id'],
            'num_entanglements': len(records),
            'results': records
        })
        
    except HTTPException:
        raise
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
        
    finally:
        if temp_pdb and os.path.exists(temp_pdb):
            os.unlink(temp_pdb)


# ============================================================================
# NEW DATABASE-BACKED ENDPOINTS
# ============================================================================

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


async def process_job_async(job_id: str, temp_pdb_path: str, base_url: str):
    """Background task to process job"""
    try:
        # Update status to processing
        db.update_job_status(job_id, 'processing')
        
        # Run analysis
        result = calculate_native_ge(temp_pdb_path, cleanup=True)
        
        if not result['success']:
            # Job failed
            db.update_job_status(job_id, 'failed', error_message=result['error'])
            
            # Get job info for email
            session = db.get_session()
            job = session.query(Job).filter_by(job_id=job_id).first()
            if job:
                email_notifier.send_error_email(
                    job.email,
                    job.job_name,
                    job_id,
                    result['error']
                )
            session.close()
            return
        
        # Save results to database
        db.save_results(job_id, result['data'], pdb_id=result['pdb_id'])
        db.update_job_status(job_id, 'completed')
        
        # Send completion email
        session = db.get_session()
        job = session.query(Job).filter_by(job_id=job_id).first()
        if job:
            results_url = f"{base_url}/results.html?job_id={job_id}"
            email_notifier.send_completion_email(
                job.email,
                job.job_name,
                job_id,
                job.num_entanglements or 0,
                results_url
            )
        session.close()
        
    except Exception as e:
        # Unexpected error
        db.update_job_status(job_id, 'failed', error_message=str(e))
        print(f"Job {job_id} failed with error: {e}")
    finally:
        # Clean up temp file
        if os.path.exists(temp_pdb_path):
            os.unlink(temp_pdb_path)


@app.post("/api/submit-job")
async def submit_job(
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    job_name: str = Form(...),
    uniprot_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...)
):
    """
    Submit a new analysis job with user metadata
    
    Parameters
    ----------
    email : str
        User's email for notifications
    job_name : str
        Name for this job
    uniprot_id : str, optional
        Uniprot ID if available
    description : str, optional
        Job description
    file : UploadFile
        PDB file to analyze
        
    Returns
    -------
    JSONResponse
        Job ID and status
    """
    
    # Validate inputs
    if not validate_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    
    if not job_name or len(job_name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Job name is required")
    
    if not file.filename.endswith('.pdb'):
        raise HTTPException(status_code=400, detail="Only PDB files are accepted")
    
    # Validate file size
    MAX_SIZE = 20 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is 20 MB"
        )
    
    # Create job in database
    job_id = db.create_job(
        email=email.strip(),
        job_name=job_name.strip(),
        pdb_filename=file.filename,
        uniprot_id=uniprot_id.strip() if uniprot_id else None,
        description=description.strip() if description else None
    )
    
    # Save PDB file temporarily
    temp_pdb = tempfile.NamedTemporaryFile(mode='wb', suffix='.pdb', delete=False)
    temp_pdb.write(contents)
    temp_pdb.close()
    
    # Get base URL for email links
    base_url = os.getenv('BASE_URL', 'http://localhost:8000')
    
    # Add background task to process the job
    background_tasks.add_task(process_job_async, job_id, temp_pdb.name, base_url)
    
    return JSONResponse(content={
        'success': True,
        'job_id': job_id,
        'message': 'Job submitted successfully. You will receive an email when processing is complete.'
    })


@app.get("/api/jobs")
async def get_jobs(limit: int = 50, offset: int = 0):
    """
    Get list of all jobs
    
    Parameters
    ----------
    limit : int
        Maximum number of jobs to return
    offset : int
        Pagination offset
        
    Returns
    -------
    JSONResponse
        List of jobs with metadata
    """
    try:
        jobs = db.get_all_jobs(limit=min(limit, 100), offset=offset)
        total_count = db.count_jobs()
        
        return JSONResponse(content={
            'success': True,
            'total': total_count,
            'count': len(jobs),
            'offset': offset,
            'jobs': [job.to_dict(include_email=False) for job in jobs]
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}")
async def get_job_details(job_id: str):
    """
    Get detailed job information including results
    
    Parameters
    ----------
    job_id : str
        Job UUID
        
    Returns
    -------
    JSONResponse
        Job metadata and results
    """
    try:
        job_data = db.get_job_with_results(job_id)
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JSONResponse(content={
            'success': True,
            'pdb_id': job_data['job']['pdb_id'],
            'job_name': job_data['job']['job_name'],
            'uniprot_id': job_data['job']['uniprot_id'],
            'description': job_data['job']['description'],
            'created_at': job_data['job']['upload_timestamp'],
            'completed_at': job_data['job']['completion_timestamp'],
            'status': job_data['job']['status'],
            'num_entanglements': job_data['job']['num_entanglements'],
            'num_chains': job_data['job']['num_chains'],
            'results': job_data['results'],
            'error_message': job_data['job'].get('error_message'),
            'pdb_content': None  # PDB files are not stored after processing
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}/pdb")
async def get_job_pdb(job_id: str):
    """
    Get the original PDB file for a job
    Note: PDB files are stored temporarily during processing.
    This endpoint will need modification if you want to permanently store PDB files.
    
    Parameters
    ----------
    job_id : str
        Job UUID
        
    Returns
    -------
    PlainTextResponse
        PDB file content
    """
    raise HTTPException(
        status_code=501,
        detail="PDB file retrieval not implemented yet. PDB files are not permanently stored."
    )


if __name__ == "__main__":
    import uvicorn
    
    # Run with: python backend.py
    # Or: uvicorn backend:app --reload --host 0.0.0.0 --port 8000
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
