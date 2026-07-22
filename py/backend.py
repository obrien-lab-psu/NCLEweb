#!/usr/bin/env python3
"""
FastAPI Backend for NCLE Web Application
Provides REST API endpoints for Gaussian Entanglement analysis
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import tempfile
import os
import shutil
import sys
import re
import json
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor
import zipfile
import io

# Load environment variables from .env file
load_dotenv()

# Add py directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# DEBUG: Log which NCLEdetector is being used
import NCLEdetector
with open('/tmp/ncledetector_debug.log', 'a') as f:
    f.write(f"Backend started at {datetime.now()}\n")
    f.write(f"Python: {sys.executable}\n")
    f.write(f"Python version: {sys.version}\n")
    f.write(f"NCLEdetector: {NCLEdetector.__file__}\n")
    f.write(f"sys.path[0]: {sys.path[0]}\n")
    f.write("---\n")

from api_wrapper import calculate_native_ge
from database import db, Job, Result, HQResult, ClusteredResult
from email_notifier import email_notifier
from job_queue import get_queue_manager
from batch_submission import create_batch_jobs, get_batch_download_zip
from proteome_loader import proteome_loader


def split_combined_crossings(hq_results: list) -> list:
    """
    Split combined 'c' column back into crossingsN and crossingsC for frontend.
    HQResult table stores combined crossings in 'c' column as 'crossingsN;crossingsC'.
    This function splits it back for consistent frontend handling.
    """
    if not hq_results:
        return hq_results
    
    processed_results = []
    for result in hq_results:
        result_copy = result.copy()
        c_value = result_copy.get('c', '')
        
        if c_value and ';' in c_value:
            parts = c_value.split(';', 1)
            result_copy['crossingsN'] = parts[0]
            result_copy['crossingsC'] = parts[1] if len(parts) > 1 else ''
        else:
            result_copy['crossingsN'] = c_value if c_value else ''
            result_copy['crossingsC'] = ''
        
        # Keep 'c' for backward compatibility
        processed_results.append(result_copy)
    
    return processed_results


def fetch_pdb_from_rcsb(pdb_id: str, output_path: str) -> bool:
    """
    Download a PDB file from RCSB database
    Tries PDB format first, falls back to CIF format for newer structures
    
    Parameters
    ----------
    pdb_id : str
        4-character PDB ID (e.g., '1PKL')
    output_path : str
        Path where the PDB file should be saved
        
    Returns
    -------
    bool
        True if download successful, False otherwise
    """
    # Ensure PDB ID is uppercase and 4 characters
    pdb_id_upper = pdb_id.strip().upper()
    pdb_id_lower = pdb_id.strip().lower()
    
    if len(pdb_id_upper) != 4:
        raise ValueError(f"Invalid PDB ID: {pdb_id}. Must be 4 characters.")
    
    # Try PDB format first
    pdb_url = f"https://files.rcsb.org/download/{pdb_id_upper}.pdb"
    
    try:
        response = requests.get(pdb_url, timeout=30)
        
        if response.status_code == 200:
            # PDB format available
            content = response.text
            if not any(content.startswith(keyword) for keyword in ['HEADER', 'TITLE', 'ATOM', 'MODEL']):
                raise ValueError(f"Downloaded file for {pdb_id} does not appear to be a valid PDB file")
            
            with open(output_path, 'w') as f:
                f.write(content)
            return True
            
        elif response.status_code == 404:
            # PDB format not available, try CIF format (newer structures)
            print(f"PDB format not available for {pdb_id_upper}, trying CIF format...")
            cif_url = f"https://files.rcsb.org/download/{pdb_id_lower}.cif"
            
            cif_response = requests.get(cif_url, timeout=30)
            
            if cif_response.status_code == 200:
                # Convert CIF to PDB using BioPython
                try:
                    from Bio.PDB import MMCIFParser, PDBIO
                    import tempfile
                    
                    # Save CIF to temp file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as tmp_cif:
                        tmp_cif.write(cif_response.text)
                        tmp_cif_path = tmp_cif.name
                    
                    try:
                        # Parse CIF and write as PDB
                        parser = MMCIFParser(QUIET=True)
                        structure = parser.get_structure(pdb_id_upper, tmp_cif_path)
                        
                        io = PDBIO()
                        io.set_structure(structure)
                        io.save(output_path)
                        
                        print(f"Successfully converted CIF to PDB format for {pdb_id_upper}")
                        return True
                    finally:
                        # Clean up temp CIF file
                        os.unlink(tmp_cif_path)
                        
                except ImportError:
                    raise HTTPException(
                        status_code=500, 
                        detail=f"PDB ID {pdb_id_upper} only available in CIF format, but BioPython not installed for conversion"
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error converting CIF to PDB for {pdb_id_upper}: {str(e)}"
                    )
            else:
                # Neither PDB nor CIF format available
                raise HTTPException(
                    status_code=404, 
                    detail=f"PDB ID {pdb_id_upper} not found in RCSB database (tried both PDB and CIF formats)"
                )
        else:
            raise HTTPException(
                status_code=502, 
                detail=f"Error fetching PDB from RCSB: HTTP {response.status_code}"
            )
            
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Network error fetching PDB: {str(e)}")
    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing PDB file: {str(e)}")
        response.raise_for_status()
        
        # Check if we got a valid PDB file (should start with HEADER, TITLE, or ATOM)
        content = response.text
        if not any(content.startswith(keyword) for keyword in ['HEADER', 'TITLE', 'ATOM', 'MODEL']):
            raise ValueError(f"Downloaded file for {pdb_id} does not appear to be a valid PDB file")
        
        # Save to file
        with open(output_path, 'w') as f:
            f.write(content)
        
        return True
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"PDB ID {pdb_id} not found in RCSB database")
        else:
            raise HTTPException(status_code=502, detail=f"Error fetching PDB from RCSB: {str(e)}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Network error fetching PDB: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing PDB file: {str(e)}")


# Initialize FastAPI app
app = FastAPI(
    title="NCLE Gaussian Entanglement API",
    description="API for calculating Native Gaussian Entanglement from PDB structures",
    version="1.0.0"
)

# Thread pool for running heavy computations without blocking workers
executor = ThreadPoolExecutor(max_workers=4)

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


async def process_job_async(job_id: str, temp_pdb_path: str, base_url: str, structure_type: str = "EXP", organism: str = "Ecoli", coarse_grained: bool = False, ca_contact: bool = False, cluster_cutoff: Optional[int] = None, ent_detection_method: int = 3, uniprot_id: Optional[str] = None, generate_features: bool = False):
    """Background task to process job
    
    Parameters
    ----------
    job_id : str
        Unique job identifier
    temp_pdb_path : str
        Path to temporary PDB file
    base_url : str
        Base URL for email links
    structure_type : str
        Structure type: "EXP" for experimental or "AF" for AlphaFold
    organism : str
        Organism for clustering: "Ecoli", "Human", "Yeast", or custom name
    coarse_grained : bool
        Whether the structure is coarse-grained (C-alpha only) - sets CG parameter
    ca_contact : bool
        Whether to use C-alpha contacts (vs heavy atom contacts) - sets Calpha parameter
    cluster_cutoff : int, optional
        Custom clustering cutoff (only for non-standard organisms)
    ent_detection_method : int, optional
        Entanglement detection method: 1=GLN-based, 2=TLN-based, 3=Consensus (default)
    uniprot_id : str, optional
        UniProt accession ID for generating features
    generate_features : bool
        Whether to generate entanglement features
    """
    try:
        # Update status to processing
        db.update_job_status(job_id, 'processing')
        
        # Run analysis in thread pool to avoid blocking the worker
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor, 
            calculate_native_ge, 
            temp_pdb_path, 
            False,  # cleanup
            structure_type, 
            organism, 
            coarse_grained, 
            ca_contact, 
            cluster_cutoff,
            ent_detection_method,
            uniprot_id,
            generate_features
        )
        
        if not result['success']:
            # Job failed - cleanup temp file
            os.remove(temp_pdb_path)
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
        
        # Save PDB file to permanent storage: data/pdb_files/{job_id}/structure.pdb
        pdb_dir = os.path.join('data', 'pdb_files', job_id)
        os.makedirs(pdb_dir, exist_ok=True)
        pdb_storage_path = os.path.join(pdb_dir, 'structure.pdb')
        
        # Copy temp file to permanent location
        shutil.copy2(temp_pdb_path, pdb_storage_path)
        
        # Cleanup temp file
        os.remove(temp_pdb_path)
        
        # Save results to database (Native_GE, Native_HQ_GE, and Native_clustered_HQ_GE)
        db.save_results(
            job_id, 
            result['data'], 
            hq_results_df=result.get('hq_data'),
            clustered_results_df=result.get('clustered_data'),
            skipped_chains=result.get('skipped_chains', [])
        )
        
        # Load entanglement features if requested
        # Currently only supports features from FeatureGen if it was successfully generated
        if generate_features and uniprot_id:
            try:
                # Only save features if FeatureGen actually generated them during processing
                if result.get('features_data') is not None:
                    features_df = result.get('features_data')
                    if isinstance(features_df, pd.DataFrame) and len(features_df) > 0:
                        db.save_entanglement_features(job_id, features_df)
                        print(f"✓ Saved {len(features_df)} entanglement features for job {job_id}")
                else:
                    print(f"⚠ Feature generation was requested but no features were returned by FeatureGen")
            except Exception as e:
                import traceback
                print(f"⚠ Warning: Feature handling failed for job {job_id}: {e}")
                traceback.print_exc()
        
        db.update_job_status(job_id, 'completed')
        
        # Send completion email
        session = db.get_session()
        job = session.query(Job).filter_by(job_id=job_id).first()
        if job:
            # Use domain name for public-facing URLs
            results_url = f"https://ncleweb.org/results.html?job_id={job_id}"
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
    email: str = Form(...),
    job_name: str = Form(...),
    uniprot_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    structure_type: str = Form("EXP"),
    organism: str = Form("Ecoli"),
    cluster_cutoff: Optional[int] = Form(None),
    coarse_grained: bool = Form(False),
    ca_contact: bool = Form(False),
    ent_detection_method: int = Form(3),
    generate_features: bool = Form(False),
    input_type: str = Form("file"),
    rcsb_pdb_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
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
    structure_type : str
        Structure type: "EXP" or "AF"
    organism : str
        Organism for clustering: "Ecoli", "Human", "Yeast", or custom name
    cluster_cutoff : int, optional
        Custom clustering cutoff (only for non-standard organisms)
    coarse_grained : bool
        Whether the structure is coarse-grained (C-alpha only) - sets CG parameter
    ca_contact : bool
        Whether to use C-alpha contacts (vs heavy atom contacts) - sets Calpha parameter
    ent_detection_method : int
        Entanglement detection method: 1=GLN-based, 2=TLN-based, 3=Consensus (default)
    generate_features : bool
        Whether to generate entanglement features (requires uniprot_id)
    input_type : str
        Type of input: "file" or "pdb_id"
    rcsb_pdb_id : str, optional
        RCSB PDB ID to fetch (if input_type is "pdb_id")
    file : UploadFile, optional
        PDB file to analyze (if input_type is "file")
        
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
    
    # If generate_features is requested, uniprot_id is required
    if generate_features and not uniprot_id:
        raise HTTPException(status_code=400, detail="UniProt Accession ID is required when generating entanglement features")
    
    # Handle PDB ID input type
    if input_type == "pdb_id":
        if not rcsb_pdb_id:
            raise HTTPException(status_code=400, detail="PDB ID is required when input_type is pdb_id")
        
        # Normalize PDB ID
        rcsb_pdb_id = rcsb_pdb_id.strip().upper()
        
        if len(rcsb_pdb_id) != 4:
            raise HTTPException(status_code=400, detail="PDB ID must be exactly 4 characters")
        
        # Check if this PDB ID has already been analyzed
        existing_job = db.get_job_by_rcsb_pdb_id(rcsb_pdb_id)
        if existing_job:
            return JSONResponse(content={
                'success': True,
                'job_id': existing_job.job_id,
                'message': f'PDB {rcsb_pdb_id} has already been analyzed. Returning existing results.',
                'is_cached': True
            })
        
        # Create job in database with RCSB PDB ID
        job_id = db.create_job(
            email=email.strip(),
            job_name=job_name.strip(),
            pdb_filename=f"{rcsb_pdb_id}.pdb",
            uniprot_id=uniprot_id.strip() if uniprot_id else None,
            description=description.strip() if description else None,
            coarse_grained=coarse_grained,
            ca_contact=ca_contact,
            rcsb_pdb_id=rcsb_pdb_id,
            structure_type=structure_type,
            ent_detection_method=ent_detection_method,
            generate_features=generate_features
        )
        
        # Download PDB file from RCSB
        temp_pdb = tempfile.NamedTemporaryFile(mode='w', suffix='.pdb', delete=False)
        temp_pdb.close()
        
        try:
            fetch_pdb_from_rcsb(rcsb_pdb_id, temp_pdb.name)
        except HTTPException as e:
            # Clean up and delete the job if download fails
            db.update_job_status(job_id, 'failed', error_message=str(e.detail))
            os.unlink(temp_pdb.name)
            raise
    
    # Handle file upload input type
    else:
        if not file:
            raise HTTPException(status_code=400, detail="PDB file is required when input_type is file")
        
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
            description=description.strip() if description else None,
            coarse_grained=coarse_grained,
            ca_contact=ca_contact,
            rcsb_pdb_id=None,
            structure_type=structure_type,
            ent_detection_method=ent_detection_method,
            generate_features=generate_features
        )
        
        # Save PDB file temporarily
        temp_pdb = tempfile.NamedTemporaryFile(mode='wb', suffix='.pdb', delete=False)
        temp_pdb.write(contents)
        temp_pdb.close()
    
    # Get base URL for email links
    base_url = os.getenv('BASE_URL', 'http://localhost:8000')
    
    # Start processing job in background (fire and forget)
    asyncio.create_task(process_job_async(job_id, temp_pdb.name, base_url, structure_type, organism, coarse_grained, ca_contact, cluster_cutoff, ent_detection_method, uniprot_id, generate_features))
    
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
        
        # Read PDB content from filesystem if available
        pdb_content = None
        pdb_file_path = os.path.join('data', 'pdb_files', job_id, 'structure.pdb')
        if os.path.exists(pdb_file_path):
            try:
                with open(pdb_file_path, 'r') as f:
                    pdb_content = f.read()
            except Exception as e:
                print(f"Error reading PDB file: {e}")
        
        # Get clustered results (harmonized format with crossingsN/crossingsC)
        clustered_results = job_data.get('clustered_results', [])
        
        # Split HQ results 'c' column back to crossingsN and crossingsC
        hq_results = split_combined_crossings(job_data.get('hq_results', []))
        
        # Get entanglement features if they exist
        features_data = []
        if job_data['job'].get('generate_features'):
            features_data = db.get_entanglement_features(job_id)
        
        return JSONResponse(content={
            'success': True,
            'job_name': job_data['job']['job_name'],
            'uniprot_id': job_data['job']['uniprot_id'],
            'description': job_data['job']['description'],
            'created_at': job_data['job']['upload_timestamp'],
            'completed_at': job_data['job']['completion_timestamp'],
            'status': job_data['job']['status'],
            'num_entanglements': job_data['job']['num_entanglements'],
            'num_hq_entanglements': job_data['job']['num_hq_entanglements'],
            'num_clustered_entanglements': job_data['job']['num_clustered_entanglements'],
            'num_chains': job_data['job']['num_chains'],
            'coarse_grained': job_data['job']['coarse_grained'],
            'ca_contact': job_data['job']['ca_contact'],
            'generate_features': job_data['job'].get('generate_features', False),
            'results': job_data['results'],
            'hq_results': hq_results,
            'clustered_results': clustered_results,
            'features_data': features_data,
            'error_message': job_data['job'].get('error_message'),
            'pdb_content': pdb_content
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


@app.get("/api/jobs/{job_id}/download-results")
async def download_job_results(job_id: str):
    """
    Download all analysis results as a zip file
    
    Parameters
    ----------
    job_id : str
        Job UUID
        
    Returns
    -------
    StreamingResponse
        Zip file containing Native_GE, Native_HQ_GE, Native_clustered_HQ_GE, and features CSV files
    """
    try:
        # Get job info
        session = db.get_session()
        job = session.query(Job).filter_by(job_id=job_id).first()
        session.close()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        if job.status != 'completed':
            raise HTTPException(status_code=400, detail=f"Job {job_id} has not completed yet")
        
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Get results from database and create CSV files
            session = db.get_session()
            
            # Native_GE results
            native_results = session.query(Result).filter_by(job_id=job_id).all()
            if native_results:
                native_df = pd.DataFrame([r.to_dict() for r in native_results])
                native_csv = native_df.to_csv(index=False, sep='|')
                zip_file.writestr('Native_GE/results.csv', native_csv)
            
            # Native_HQ_GE results
            hq_results = session.query(HQResult).filter_by(job_id=job_id).all()
            if hq_results:
                hq_df = pd.DataFrame([r.to_dict() for r in hq_results])
                hq_csv = hq_df.to_csv(index=False, sep='|')
                zip_file.writestr('Native_HQ_GE/results.csv', hq_csv)
            
            # Native_clustered_HQ_GE results
            clustered_results = session.query(ClusteredResult).filter_by(job_id=job_id).all()
            if clustered_results:
                clustered_df = pd.DataFrame([r.to_dict() for r in clustered_results])
                clustered_csv = clustered_df.to_csv(index=False, sep='|')
                zip_file.writestr('Native_clustered_HQ_GE/results.csv', clustered_csv)
            
            # Entanglement features
            from database import EntanglementFeature
            features = session.query(EntanglementFeature).filter_by(job_id=job_id).all()
            if features:
                features_df = pd.DataFrame([f.to_dict() for f in features])
                features_csv = features_df.to_csv(index=False, sep='|')
                zip_file.writestr('Native_clustered_HQ_GE_features/results.csv', features_csv)
            
            session.close()
        
        # Prepare zip file for streaming
        zip_buffer.seek(0)
        
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=ncle_results_{job_id[:8]}.zip"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error downloading results for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error downloading results: {str(e)}")


# ============================================================================
# BATCH SUBMISSION ENDPOINTS
# ============================================================================

@app.post("/api/submit-batch-multiple")
async def submit_batch_multiple(
    email: str = Form(...),
    batch_name: str = Form(...),
    organism: str = Form("Ecoli"),
    structure_type: str = Form("EXP"),
    coarse_grained: bool = Form(False),
    ca_contact: bool = Form(False),
    cluster_cutoff: Optional[int] = Form(None),
    ent_detection_method: int = Form(3),
    uniprot_id: Optional[str] = Form(None),
    uniprot_ids: Optional[str] = Form(None),
    generate_features: bool = Form(False),
    per_file_options: Optional[str] = Form(None),
    files: List[UploadFile] = File(...)
):
    """
    Submit multiple PDB files with the same parameters.
    
    Parameters
    ----------
    email : str
        User's email for notifications
    batch_name : str
        Name for this batch submission
    organism : str
        Organism for clustering
    structure_type : str
        Structure type: "EXP" or "AF"
    coarse_grained : bool
        Whether to use coarse-grained (C-alpha only) structures
    ca_contact : bool
        Whether to use C-alpha contacts
    cluster_cutoff : int, optional
        Custom clustering cutoff
    ent_detection_method : int
        Entanglement detection method (1, 2, or 3)
    uniprot_id : str, optional
        UniProt ID for feature generation
    uniprot_ids : str, optional
        JSON string mapping filenames to UniProt IDs
    generate_features : bool
        Whether to generate entanglement features
    per_file_options : str, optional
        JSON string mapping filenames to per-file options
    files : List[UploadFile]
        PDB files to analyze
        
    Returns
    -------
    JSONResponse
        Batch ID and list of job IDs
    """
    
    # Validate inputs
    if not validate_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    
    if not batch_name or len(batch_name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Batch name is required")
    
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="At least one PDB file is required")
    
    if len(files) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 files per batch")
    
    # Check if generate_features requires UniProt IDs
    if generate_features:
        has_uniprot = False
        if uniprot_id:  # Legacy single UniProt ID
            has_uniprot = True
        elif uniprot_ids:  # Per-file UniProt IDs
            try:
                per_file_ids = json.loads(uniprot_ids)
                # Check if at least one file has a UniProt ID
                has_uniprot = any(per_file_ids.get(file.filename, '').strip() for file in files)
            except (json.JSONDecodeError, TypeError):
                pass
        
        if not has_uniprot:
            raise HTTPException(status_code=400, detail="UniProt ID is required when generating features")
    
    # Read all PDB files
    MAX_SIZE = 20 * 1024 * 1024  # 20 MB per file
    pdb_files = {}
    
    try:
        for file in files:
            if not file.filename.endswith('.pdb'):
                raise HTTPException(status_code=400, detail=f"Invalid file: {file.filename}. Only .pdb files accepted")
            
            contents = await file.read()
            if len(contents) > MAX_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File {file.filename} too large. Maximum 20 MB per file"
                )
            
            pdb_files[file.filename] = contents
        
        # Parse per-file UniProt IDs if provided
        per_file_uniprot_ids = {}
        if uniprot_ids:
            try:
                per_file_uniprot_ids = json.loads(uniprot_ids)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse uniprot_ids JSON: {uniprot_ids}")
        
        # Parse per-file options if provided
        per_file_opts = {}
        if per_file_options:
            try:
                per_file_opts = json.loads(per_file_options)
                print(f"DEBUG backend: per_file_opts parsed: {list(per_file_opts.keys())}")
                for fname, opts in per_file_opts.items():
                    print(f"DEBUG backend:   {fname}: generate_features={opts.get('generate_features', 'NOT FOUND')}, keys={list(opts.keys())}")
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse per_file_options JSON: {per_file_options}")
        
        # Create base parameters
        base_params = {
            'organism': organism,
            'coarse_grained': coarse_grained,
            'ca_contact': ca_contact,
            'structure_type': structure_type,
            'ent_detection_method': ent_detection_method,
            'cluster_cutoff': cluster_cutoff
        }
        
        # Create batch jobs
        base_url = os.getenv('BASE_URL', 'http://localhost:8000')
        batch_id, job_ids, errors = create_batch_jobs(
            email=email.strip(),
            batch_name=batch_name.strip(),
            pdb_files=pdb_files,
            base_uniprot_id=uniprot_id.strip() if uniprot_id else None,
            per_file_uniprot_ids=per_file_uniprot_ids if per_file_uniprot_ids else None,
            per_file_options=per_file_opts if per_file_opts else None,
            base_params=base_params,
            generate_features=generate_features,
            base_url=base_url,
            job_processor=process_job_async
        )
        
        if not job_ids:
            raise HTTPException(status_code=400, detail=f"No jobs created. Errors: {'; '.join(errors)}")
        
        return JSONResponse(content={
            'success': True,
            'batch_id': batch_id,
            'job_ids': job_ids,
            'total_jobs': len(job_ids),
            'errors': errors if errors else None,
            'message': f'Batch submission created with {len(job_ids)} jobs'
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating batch: {str(e)}")


@app.get("/api/batch/{batch_id}/status")
async def get_batch_status(batch_id: str):
    """
    Get status of a batch submission.
    
    Parameters
    ----------
    batch_id : str
        Batch UUID
        
    Returns
    -------
    JSONResponse
        Batch status and job information
    """
    try:
        batch_status = db.get_batch_status(batch_id)
        
        if not batch_status:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        # Add queue information
        queue_manager = get_queue_manager()
        queue_info = queue_manager.get_batch_status(batch_id)
        
        return JSONResponse(content={
            'success': True,
            'batch_id': batch_id,
            'status': batch_status,
            'queue': queue_info
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching batch status: {str(e)}")


@app.get("/api/batch/{batch_id}/download")
async def download_batch_results(batch_id: str):
    """
    Download all results for a batch as a ZIP file.
    
    Parameters
    ----------
    batch_id : str
        Batch UUID
        
    Returns
    -------
    StreamingResponse
        ZIP file containing all results
    """
    try:
        batch_status = db.get_batch_status(batch_id)
        
        if not batch_status:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        # Check if all jobs are completed
        pending = batch_status['status_breakdown'].get('pending', 0)
        processing = batch_status['status_breakdown'].get('processing', 0)
        queued = batch_status['status_breakdown'].get('queued', 0)
        
        if pending > 0 or processing > 0 or queued > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Batch not complete. Pending: {pending}, Processing: {processing}, Queued: {queued}"
            )
        
        # Create ZIP with results
        zip_data = get_batch_download_zip(batch_id)
        
        return StreamingResponse(
            iter([zip_data]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=ncle_batch_{batch_id[:8]}.zip"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading batch results: {str(e)}")


@app.get("/api/queue/status")
async def get_queue_status():
    """
    Get current queue status (useful for monitoring).
    
    Returns
    -------
    JSONResponse
        Queue statistics
    """
    try:
        queue_manager = get_queue_manager()
        queue_status = queue_manager.get_queue_status()
        
        return JSONResponse(content={
            'success': True,
            'queue_status': queue_status
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching queue status: {str(e)}")


# ============================================================================
# PROTEOME-WIDE NCLE BROWSER ENDPOINTS
# ============================================================================

@app.get("/api/proteome/organisms")
async def get_proteome_organisms():
    """
    Get list of available organisms with statistics
    
    Returns
    -------
    JSONResponse
        List of organisms with protein counts and availability
    """
    try:
        organisms = proteome_loader.get_available_organisms()
        return JSONResponse(content={
            'success': True,
            'organisms': organisms
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching organisms: {str(e)}")


@app.get("/api/proteome/{organism}")
async def get_proteome_proteins(
    organism: str,
    offset: int = 0,
    limit: int = 50,
    search: Optional[str] = None
):
    """
    Get list of proteins for a given organism with optional searching
    
    Parameters
    ----------
    organism : str
        Organism name (Yeast, Human, Ecoli)
    offset : int
        Pagination offset
    limit : int
        Number of results per page
    search : str, optional
        Search query for protein ID
    
    Returns
    -------
    JSONResponse
        Paginated list of proteins with entanglement counts
    """
    try:
        if search:
            all_proteins = proteome_loader.search_proteins(search, organism)
        else:
            all_proteins = proteome_loader.load_proteome_data(organism)
        
        total = len(all_proteins)
        proteins = all_proteins[offset:offset + limit]
        
        return JSONResponse(content={
            'success': True,
            'organism': organism,
            'total': total,
            'count': len(proteins),
            'offset': offset,
            'limit': limit,
            'proteins': proteins
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching proteins: {str(e)}")


@app.get("/api/proteome/{organism}/{protein_id}")
async def get_protein_entanglements(organism: str, protein_id: str):
    """
    Get detailed entanglement data for a specific protein from all sources
    
    Parameters
    ----------
    organism : str
        Organism name
    protein_id : str
        UniProt ID
    
    Returns
    -------
    JSONResponse
        Protein info and entanglement data from all sources (Native_GE, HQ, Clustered, Features)
    """
    try:
        # Get all data types
        native_ge = proteome_loader.get_protein_entanglements(protein_id, organism)
        native_hq = proteome_loader.get_hq_entanglements(protein_id, organism)
        native_clustered = proteome_loader.get_clustered_entanglements(protein_id, organism)
        features = proteome_loader.get_entanglement_features(protein_id, organism)
        
        # Convert to dicts if they're DictReader objects
        if native_ge and hasattr(native_ge[0], '__getitem__'):
            native_ge = [dict(e) for e in native_ge]
        if native_hq and hasattr(native_hq[0], '__getitem__'):
            native_hq = [dict(e) for e in native_hq]
        if native_clustered and hasattr(native_clustered[0], '__getitem__'):
            native_clustered = [dict(e) for e in native_clustered]
        if features and hasattr(features[0], '__getitem__'):
            features = [dict(e) for e in features]
        
        return JSONResponse(content={
            'success': True,
            'protein_id': protein_id,
            'organism': organism,
            'num_entanglements': len(native_ge),
            'entanglements': native_ge,
            'native_ge': native_ge,
            'native_hq': native_hq,
            'native_clustered': native_clustered,
            'features': features
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching protein data: {str(e)}")


@app.get("/api/proteome/{organism}/{protein_id}/pdb")
async def get_protein_pdb(organism: str, protein_id: str):
    """
    Get PDB structure file for a protein
    
    Parameters
    ----------
    organism : str
        Organism name
    protein_id : str
        UniProt ID
    
    Returns
    -------
    PlainTextResponse
        PDB file content
    """
    try:
        pdb_path = proteome_loader.get_structure_path(protein_id)
        
        if not pdb_path:
            raise HTTPException(status_code=404, detail=f"PDB file not found for {protein_id}")
        
        with open(pdb_path, 'r') as f:
            pdb_content = f.read()
        
        return PlainTextResponse(pdb_content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching PDB file: {str(e)}")


@app.get("/api/proteome/{organism}/{protein_id}/download")
async def download_protein_data(organism: str, protein_id: str):
    """
    Download entanglement data for a single protein
    
    Parameters
    ----------
    organism : str
        Organism name
    protein_id : str
        UniProt ID
    
    Returns
    -------
    StreamingResponse
        Zip file with Native_GE, Native_HQ_GE, Native_clustered_HQ_GE, and features data
    """
    try:
        from pathlib import Path
        
        base_path = Path("/home/ianms/NCLE_DB/NCLE_results") / f"{organism}/AlphaFoldv4"
        
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Subdirectories with data types
            subdirs = [
                "Native_GE",
                "Native_HQ_GE", 
                "Native_clustered_HQ_GE",
                "Native_clustered_HQ_GE_features"
            ]
            
            for subdir in subdirs:
                csv_path = base_path / subdir / f"{protein_id}.csv"
                if csv_path.exists():
                    with open(csv_path, 'r') as f:
                        csv_content = f.read()
                    zip_file.writestr(f"{subdir}/{protein_id}.csv", csv_content)
        
        zip_buffer.seek(0)
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={protein_id}_{organism}.zip"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating download: {str(e)}")


@app.post("/api/proteome/{organism}/download-filtered")
async def download_filtered_proteome_data(organism: str, protein_ids: List[str] = None):
    """
    Download entanglement data for multiple proteins
    
    Parameters
    ----------
    organism : str
        Organism name
    protein_ids : List[str]
        List of protein IDs to download
    
    Returns
    -------
    StreamingResponse
        Zip file with data for all requested proteins
    """
    try:
        from pathlib import Path
        
        if not protein_ids:
            raise HTTPException(status_code=400, detail="No proteins specified")
        
        base_path = Path("/home/ianms/NCLE_DB/NCLE_results") / f"{organism}/AlphaFoldv4"
        
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Subdirectories with data types
            subdirs = [
                "Native_GE",
                "Native_HQ_GE",
                "Native_clustered_HQ_GE",
                "Native_clustered_HQ_GE_features"
            ]
            
            for subdir in subdirs:
                for protein_id in protein_ids:
                    csv_path = base_path / subdir / f"{protein_id}.csv"
                    if csv_path.exists():
                        with open(csv_path, 'r') as f:
                            csv_content = f.read()
                        zip_file.writestr(f"{subdir}/{protein_id}.csv", csv_content)
        
        zip_buffer.seek(0)
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={organism}_proteome_data.zip"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating download: {str(e)}")


@app.post("/api/contact")
async def send_contact_message(
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...)
):
    """
    Handle contact form submissions
    Sends email to administrator
    """
    try:
        # Validate inputs
        if not name or not email or not subject or not message:
            raise HTTPException(status_code=400, detail="All fields are required")
        
        # Send email to admin
        admin_email = os.getenv('ADMIN_EMAIL', 'ims86@psu.edu')
        email_notifier.send_email(
            to_email=admin_email,
            subject=f"[NCLE Contact] {subject}",
            body=f"""
New contact message from NCLE Web Platform:

From: {name} ({email})
Subject: {subject}

Message:
{message}

---
Reply to: {email}
            """
        )
        
        return JSONResponse(content={
            'success': True,
            'message': 'Your message has been sent successfully'
        })
    except Exception as e:
        logger.error(f"Error sending contact message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending message: {str(e)}")


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
