#!/usr/bin/env python3
"""
FastAPI Backend for NCLE Web Application
Provides REST API endpoints for Gaussian Entanglement analysis
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
import tempfile
import os
import shutil
import sys
import re
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

from api_wrapper import calculate_native_ge
from database import db, Job, Result, HQResult, ClusteredResult
from email_notifier import email_notifier


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
        import shutil
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
    
    # Auto-enable C-alpha contacts for AlphaFold models (same as run_nativeNCLE.py)
    # This reduces memory usage and is the standard approach for AF structures
    if structure_type.upper() == 'AF' and not ca_contact and not coarse_grained:
        ca_contact = True
        print(f"Auto-enabling C-alpha contacts for AlphaFold structure: {job_name}")
    
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
