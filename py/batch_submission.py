#!/usr/bin/env python3
"""
Batch submission handling for NCLE Web Application

Supports two types of batch submissions:
1. Multiple PDB files with same parameters (form-based)
2. ZIP file containing PDB files + params.csv (file-based)
"""

import zipfile
import csv
import io
import os
import tempfile
import asyncio
from typing import List, Dict, Optional, Tuple, Callable
import uuid
import pandas as pd
from pathlib import Path

from database import db
from job_queue import get_queue_manager, JobPriority


def parse_params_csv(csv_data: str) -> List[Dict]:
    """
    Parse params.csv from batch submission.
    
    CSV format (comma-separated):
    pdb_filename, organism, coarse_grained, ca_contact, cluster_cutoff, structure_type, ent_detection_method
    
    Example:
    protein_1.pdb, Ecoli, false, false, , EXP, 3
    protein_2.pdb, Human, true, false, , EXP, 3
    protein_3.pdb, Custom, false, false, 5.0, EXP, 3
    
    Returns
    -------
    list
        List of parameter dictionaries
    """
    params_list = []
    
    try:
        reader = csv.DictReader(io.StringIO(csv_data))
        
        if not reader.fieldnames:
            raise ValueError("params.csv is empty or invalid format")
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            try:
                # Parse each field
                pdb_filename = row.get('pdb_filename', '').strip()
                if not pdb_filename:
                    raise ValueError(f"Row {row_num}: pdb_filename is required")
                
                if not pdb_filename.endswith('.pdb'):
                    raise ValueError(f"Row {row_num}: pdb_filename must end with .pdb")
                
                organism = row.get('organism', 'Ecoli').strip() or 'Ecoli'
                coarse_grained = row.get('coarse_grained', 'false').strip().lower() in ('true', '1', 'yes')
                ca_contact = row.get('ca_contact', 'false').strip().lower() in ('true', '1', 'yes')
                structure_type = row.get('structure_type', 'EXP').strip().upper() or 'EXP'
                ent_detection_method = int(row.get('ent_detection_method', '3').strip() or '3')
                
                # Validate ent_detection_method
                if ent_detection_method not in (1, 2, 3):
                    raise ValueError(f"Row {row_num}: ent_detection_method must be 1, 2, or 3")
                
                # Parse optional cluster_cutoff
                cluster_cutoff = None
                cluster_cutoff_str = row.get('cluster_cutoff', '').strip()
                if cluster_cutoff_str:
                    try:
                        cluster_cutoff = int(cluster_cutoff_str)
                    except ValueError:
                        raise ValueError(f"Row {row_num}: cluster_cutoff must be an integer")
                
                params_list.append({
                    'pdb_filename': pdb_filename,
                    'organism': organism,
                    'coarse_grained': coarse_grained,
                    'ca_contact': ca_contact,
                    'structure_type': structure_type,
                    'ent_detection_method': ent_detection_method,
                    'cluster_cutoff': cluster_cutoff
                })
            
            except Exception as e:
                raise ValueError(f"Row {row_num}: {str(e)}")
    
    except csv.Error as e:
        raise ValueError(f"Error parsing CSV: {str(e)}")
    
    if not params_list:
        raise ValueError("params.csv contains no data rows")
    
    return params_list


def extract_batch_zip(zip_data: bytes) -> Tuple[List[str], str, Dict]:
    """
    Extract PDB files and params from a ZIP file.
    
    Parameters
    ----------
    zip_data : bytes
        ZIP file contents
        
    Returns
    -------
    tuple
        (pdb_files_dict, params_csv_content, validation_errors)
        where pdb_files_dict maps filename -> file_content
        
    Raises
    ------
    ValueError
        If ZIP format is invalid or required files missing
    """
    pdb_files = {}
    params_csv = None
    
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zip_ref:
            # Get list of files
            file_list = zip_ref.namelist()
            
            # Look for params.csv
            for file in file_list:
                if file.lower().endswith('params.csv'):
                    params_csv = zip_ref.read(file).decode('utf-8')
                    break
            
            if not params_csv:
                raise ValueError("ZIP file must contain 'params.csv'")
            
            # Extract PDB files
            for file in file_list:
                if file.lower().endswith('.pdb') and not file.startswith('__MACOSX'):
                    pdb_content = zip_ref.read(file).decode('utf-8')
                    filename = os.path.basename(file)
                    pdb_files[filename] = pdb_content
            
            if not pdb_files:
                raise ValueError("ZIP file must contain at least one .pdb file")
    
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP file format")
    except Exception as e:
        raise ValueError(f"Error extracting ZIP file: {str(e)}")
    
    return pdb_files, params_csv


def create_batch_jobs(
    email: str,
    batch_name: str,
    pdb_files: Dict[str, bytes],
    params_list: List[Dict],
    base_uniprot_id: Optional[str] = None,
    per_file_uniprot_ids: Optional[Dict[str, str]] = None,
    generate_features: bool = False,
    base_url: str = None,
    job_processor: Optional[Callable] = None
) -> Tuple[str, List[str], List[str]]:
    """
    Create multiple jobs from batch submission.
    
    Parameters
    ----------
    email : str
        User's email
    batch_name : str
        Name for the batch
    pdb_files : dict
        Map of pdb_filename -> file_content
    params_list : list
        List of parameter dictionaries from params.csv
    base_uniprot_id : str, optional
        Optional uniprot ID for feature generation
    generate_features : bool
        Whether to generate features
    base_url : str, optional
        Base URL for emails
    job_processor : callable, optional
        Optional async function to process jobs. If provided, will be called
        for each job with (job_id, temp_pdb_path, **params)
        
    Returns
    -------
    tuple
        (batch_id, job_ids, errors)
    """
    batch_id = str(uuid.uuid4())
    job_ids = []
    errors = []
    queue_manager = get_queue_manager()
    
    for params in params_list:
        pdb_filename = params['pdb_filename']
        
        # Check if PDB file exists in submission
        if pdb_filename not in pdb_files:
            errors.append(f"PDB file '{pdb_filename}' specified in params.csv but not found in ZIP")
            continue
        
        try:
            pdb_content = pdb_files[pdb_filename]
            
            # Calculate file size
            file_size = len(pdb_content.encode('utf-8') if isinstance(pdb_content, str) else pdb_content)
            
            # Get per-file UniProt ID if provided
            file_uniprot_id = None
            if per_file_uniprot_ids and pdb_filename in per_file_uniprot_ids:
                file_uniprot_id = per_file_uniprot_ids[pdb_filename]
            elif base_uniprot_id:
                file_uniprot_id = base_uniprot_id
            
            # Create job in database
            job_id = db.create_job(
                email=email,
                job_name=f"{batch_name} - {pdb_filename}",
                pdb_filename=pdb_filename,
                uniprot_id=file_uniprot_id,
                description=f"Batch submission: {batch_name}",
                coarse_grained=params['coarse_grained'],
                ca_contact=params['ca_contact'],
                structure_type=params['structure_type'],
                ent_detection_method=params['ent_detection_method'],
                generate_features=generate_features,
                batch_id=batch_id,
                estimated_size=file_size
            )
            
            # Enqueue in job queue
            priority, queue_position = queue_manager.enqueue_job(
                job_id=job_id,
                file_size=file_size,
                batch_id=batch_id
            )
            
            # Update database with queue info
            db.update_job_queue_info(job_id, int(priority), queue_position)
            
            # Save PDB file to temporary location
            temp_dir = tempfile.gettempdir()
            temp_pdb_path = os.path.join(temp_dir, f"ncle_batch_{job_id}.pdb")
            
            with open(temp_pdb_path, 'w') as f:
                if isinstance(pdb_content, bytes):
                    f.write(pdb_content.decode('utf-8'))
                else:
                    f.write(pdb_content)
            
            job_ids.append(job_id)
            
            # If job_processor callback is provided, trigger async job processing
            if job_processor:
                try:
                    asyncio.create_task(job_processor(
                        job_id=job_id,
                        temp_pdb_path=temp_pdb_path,
                        base_url=base_url or 'http://localhost:8000',
                        structure_type=params['structure_type'],
                        organism=params.get('organism', 'Ecoli'),
                        coarse_grained=params.get('coarse_grained', False),
                        ca_contact=params.get('ca_contact', False),
                        cluster_cutoff=params.get('cluster_cutoff'),
                        ent_detection_method=params.get('ent_detection_method', 3),
                        uniprot_id=file_uniprot_id,
                        generate_features=generate_features
                    ))
                except Exception as e:
                    # Log but don't fail - job will be picked up by background processing
                    print(f"Warning: Could not schedule async processing for job {job_id}: {str(e)}")
        
        except Exception as e:
            errors.append(f"Error creating job for '{pdb_filename}': {str(e)}")
    
    return batch_id, job_ids, errors


def get_batch_download_zip(batch_id: str) -> bytes:
    """
    Create a ZIP file containing all results for a batch.
    
    Parameters
    ----------
    batch_id : str
        Batch ID
        
    Returns
    -------
    bytes
        ZIP file contents
        
    Raises
    ------
    ValueError
        If batch not found or no results available
    """
    from database import Result, HQResult, ClusteredResult, EntanglementFeature
    
    # Get all jobs in batch
    batch_status = db.get_batch_status(batch_id)
    
    if not batch_status:
        raise ValueError(f"Batch {batch_id} not found")
    
    # Create zip file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        session = db.get_session()
        
        # Get all jobs in batch
        from database import Job
        jobs = session.query(Job).filter_by(batch_id=batch_id).all()
        
        for job in jobs:
            job_id = job.job_id
            job_prefix = f"{job.pdb_filename}_{job_id[:8]}"
            
            # Native_GE results
            native_results = session.query(Result).filter_by(job_id=job_id).all()
            if native_results:
                native_df = pd.DataFrame([r.to_dict() for r in native_results])
                native_csv = native_df.to_csv(index=False, sep='|')
                zip_file.writestr(f'{job_prefix}/Native_GE_results.csv', native_csv)
            
            # Native_HQ_GE results
            hq_results = session.query(HQResult).filter_by(job_id=job_id).all()
            if hq_results:
                hq_df = pd.DataFrame([r.to_dict() for r in hq_results])
                hq_csv = hq_df.to_csv(index=False, sep='|')
                zip_file.writestr(f'{job_prefix}/Native_HQ_GE_results.csv', hq_csv)
            
            # Native_clustered_HQ_GE results
            clustered_results = session.query(ClusteredResult).filter_by(job_id=job_id).all()
            if clustered_results:
                clustered_df = pd.DataFrame([r.to_dict() for r in clustered_results])
                clustered_csv = clustered_df.to_csv(index=False, sep='|')
                zip_file.writestr(f'{job_prefix}/Native_clustered_HQ_GE_results.csv', clustered_csv)
            
            # Entanglement features
            features = session.query(EntanglementFeature).filter_by(job_id=job_id).all()
            if features:
                features_df = pd.DataFrame([f.to_dict() for f in features])
                features_csv = features_df.to_csv(index=False, sep='|')
                zip_file.writestr(f'{job_prefix}/Features_results.csv', features_csv)
        
        # Add batch summary
        summary_data = []
        for job in jobs:
            summary_data.append({
                'job_id': job.job_id,
                'pdb_filename': job.pdb_filename,
                'status': job.status,
                'num_entanglements': job.num_entanglements or 0,
                'num_hq_entanglements': job.num_hq_entanglements or 0,
                'num_clustered': job.num_clustered_entanglements or 0,
                'upload_time': job.upload_timestamp.isoformat() if job.upload_timestamp else '',
                'completion_time': job.completion_timestamp.isoformat() if job.completion_timestamp else '',
                'error': job.error_message or ''
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_csv = summary_df.to_csv(index=False, sep='|')
        zip_file.writestr('batch_summary.csv', summary_csv)
        
        session.close()
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
