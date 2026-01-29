#!/usr/bin/env python3
"""
Database models and utilities for NCLE Web Application
Using SQLAlchemy with SQLite
"""

from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
import json
import os
import pandas as pd
from pathlib import Path

Base = declarative_base()

class Job(Base):
    """Job submission table"""
    __tablename__ = 'jobs'
    
    job_id = Column(String, primary_key=True)
    email = Column(String, nullable=False, index=True)
    job_name = Column(String, nullable=False)
    uniprot_id = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    pdb_filename = Column(String, nullable=False)
    rcsb_pdb_id = Column(String, nullable=True, index=True)
    upload_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    completion_timestamp = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default='pending')  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    num_entanglements = Column(Integer, nullable=True)
    num_hq_entanglements = Column(Integer, nullable=True)
    num_clustered_entanglements = Column(Integer, nullable=True)
    num_chains = Column(Integer, nullable=True)
    coarse_grained = Column(Boolean, nullable=False, default=False)
    ca_contact = Column(Boolean, nullable=False, default=False)
    skipped_chains = Column(Text, nullable=True)  # JSON array of chains that failed QC
    structure_type = Column(String, nullable=True, default='EXP')  # EXP or AF
    ent_detection_method = Column(Integer, nullable=True, default=3)  # 1=GLN, 2=TLN, 3=Consensus
    generate_features = Column(Boolean, nullable=False, default=False)  # Whether to generate entanglement features
    
    # Relationship to results
    results = relationship("Result", back_populates="job", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Job(job_id='{self.job_id}', job_name='{self.job_name}', status='{self.status}')>"
    
    def to_dict(self, include_email=False):
        """Convert to dictionary for JSON serialization"""
        data = {
            'job_id': self.job_id,
            'job_name': self.job_name,
            'uniprot_id': self.uniprot_id,
            'description': self.description,
            'pdb_filename': self.pdb_filename,
            'rcsb_pdb_id': self.rcsb_pdb_id,
            'upload_timestamp': self.upload_timestamp.isoformat() if self.upload_timestamp else None,
            'completion_timestamp': self.completion_timestamp.isoformat() if self.completion_timestamp else None,
            'status': self.status,
            'error_message': self.error_message,
            'num_entanglements': self.num_entanglements,
            'num_hq_entanglements': self.num_hq_entanglements,
            'num_clustered_entanglements': self.num_clustered_entanglements,
            'num_chains': self.num_chains,
            'coarse_grained': self.coarse_grained,
            'ca_contact': self.ca_contact,
            'skipped_chains': json.loads(self.skipped_chains) if self.skipped_chains else [],
            'structure_type': self.structure_type,
            'ent_detection_method': self.ent_detection_method,
            'generate_features': self.generate_features
        }
        if include_email:
            data['email'] = self.email
        else:
            data['email'] = self.mask_email(self.email)
        return data
    
    @staticmethod
    def mask_email(email):
        """Mask email for privacy: user@example.com -> u***@example.com"""
        if not email or '@' not in email:
            return email
        username, domain = email.split('@', 1)
        if len(username) <= 1:
            return f"{username}***@{domain}"
        return f"{username[0]}***@{domain}"


class Result(Base):
    """Entanglement results table (Native_GE)"""
    __tablename__ = 'results'
    
    result_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.job_id'), nullable=False, index=True)
    chain = Column(String, nullable=False)
    i = Column(Integer, nullable=False)
    j = Column(Integer, nullable=False)
    crossingsN = Column(String, nullable=True)
    crossingsC = Column(String, nullable=True)
    gn = Column(Float, nullable=False)
    gc = Column(Float, nullable=False)
    GLNn = Column(Integer, nullable=False)
    GLNc = Column(Integer, nullable=False)
    TLNn = Column(Integer, nullable=False)
    TLNc = Column(Integer, nullable=False)
    CCbond = Column(Boolean, nullable=False)
    ENT = Column(Boolean, nullable=False)
    
    # Relationship to job
    job = relationship("Job", back_populates="results")
    
    def __repr__(self):
        return f"<Result(job_id='{self.job_id}', chain='{self.chain}', i={self.i}, j={self.j})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'result_id': self.result_id,
            'job_id': self.job_id,
            'chain': self.chain,
            'i': self.i,
            'j': self.j,
            'crossingsN': self.crossingsN,
            'crossingsC': self.crossingsC,
            'gn': self.gn,
            'gc': self.gc,
            'GLNn': self.GLNn,
            'GLNc': self.GLNc,
            'TLNn': self.TLNn,
            'TLNc': self.TLNc,
            'CCbond': self.CCbond,
            'ENT': self.ENT
        }


class HQResult(Base):
    """High-quality entanglement results table (Native_HQ_GE)"""
    __tablename__ = 'hq_results'
    
    result_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.job_id'), nullable=False, index=True)
    ID = Column(String)  # Structure/PDB ID
    chain = Column(String, nullable=False)
    i = Column(Integer, nullable=False)
    j = Column(Integer, nullable=False)
    c = Column(String, nullable=True)  # Combined crossings (crossingsN + crossingsC)
    gn = Column(Float, nullable=False)
    gc = Column(Float, nullable=False)
    GLNn = Column(Integer, nullable=False)
    GLNc = Column(Integer, nullable=False)
    CCbond = Column(Boolean, nullable=False)
    ENT = Column(Boolean, nullable=False)
    
    def __repr__(self):
        return f"<HQResult(job_id='{self.job_id}', chain='{self.chain}', i={self.i}, j={self.j})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'result_id': self.result_id,
            'job_id': self.job_id,
            'ID': self.ID,
            'chain': self.chain,
            'i': self.i,
            'j': self.j,
            'c': self.c,
            'gn': self.gn,
            'gc': self.gc,
            'Gn': self.GLNn,
            'Gc': self.GLNc,
            'CCbond': self.CCbond,
            'ENT': self.ENT
        }


class ClusteredResult(Base):
    """Clustered Native_HQ_GE results table"""
    __tablename__ = 'clustered_results'
    
    result_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.job_id'), nullable=False)
    ID = Column(String)  # PDB ID / Structure ID
    chain = Column(String)  # Chain identifier
    i = Column(Integer, nullable=False)
    j = Column(Integer, nullable=False)
    crossingsN = Column(String)  # N-terminal crossings (e.g., "+12,+15")
    crossingsC = Column(String)  # C-terminal crossings (e.g., "+354,-355")
    gn = Column(Float)
    gc = Column(Float)
    GLNn = Column(Integer)  # Gaussian linking number N-terminal
    GLNc = Column(Integer)  # Gaussian linking number C-terminal
    TLNn = Column(Integer)  # Topological linking number N-terminal
    TLNc = Column(Integer)  # Topological linking number C-terminal
    num_contacts = Column(Integer)  # Number of native contacts in this cluster
    contacts = Column(String)  # Semicolon-separated contact ranges (e.g., "96-135;102-128")
    CCBond = Column(Boolean)  # Whether this involves a disulfide bond
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'result_id': self.result_id,
            'job_id': self.job_id,
            'ID': self.ID,
            'chain': self.chain,
            'i': self.i,
            'j': self.j,
            'crossingsN': self.crossingsN,
            'crossingsC': self.crossingsC,
            'gn': self.gn,
            'gc': self.gc,
            'GLNn': self.GLNn,
            'GLNc': self.GLNc,
            'TLNn': self.TLNn,
            'TLNc': self.TLNc,
            'num_contacts': self.num_contacts,
            'contacts': self.contacts,
            'CCBond': self.CCBond
        }


class EntanglementFeature(Base):
    """Entanglement features table (Native_clustered_HQ_GE_features)
    
    Updated for EntDetect 0.2.0+ with new column names:
    - pdb -> PDB
    - ent_id -> ENT-ID
    - n_term_thread -> N_term_thread
    - c_term_thread -> C_term_thread
    - nc -> NC
    - nc_wbuff -> NC_wbuff
    - nc_region -> NC_region
    - crossings -> split into crossingsN, crossingsC, crossingsN_wbuff, etc.
    - min_n_* -> min_N_*
    - min_c_* -> min_C_*
    - aco -> ACO
    - rco -> RCO
    - cc_bond -> CCBond
    """
    __tablename__ = 'entanglement_features'
    
    feature_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.job_id'), nullable=False, index=True)
    gene = Column(String, nullable=False)  # UniProt gene name
    PDB = Column(String, nullable=False)  # PDB/Structure ID
    chain = Column(String, nullable=False)
    ENT_ID = Column(Integer, nullable=False)  # Entanglement ID (note: using ENT_ID in DB to avoid dash)
    gn = Column(Float)  # Gaussian linking number N-terminal
    N_term_thread = Column(Integer)  # N-terminal threading
    gc = Column(Float)  # Gaussian linking number C-terminal
    C_term_thread = Column(Integer)  # C-terminal threading
    i = Column(Integer)  # Residue index i
    j = Column(Integer)  # Residue index j
    NC = Column(String)  # Native contacts (i,j)
    NC_wbuff = Column(String)  # Native contacts with buffer
    NC_region = Column(String)  # NC region
    crossingsN = Column(String)  # N-terminal crossing residues
    crossingsC = Column(String)  # C-terminal crossing residues
    crossingsN_wbuff = Column(String)  # N-terminal crossings with buffer
    crossingsC_wbuff = Column(String)  # C-terminal crossings with buffer
    crossingsN_region = Column(String)  # N-terminal crossings region
    crossingsC_region = Column(String)  # C-terminal crossings region
    ent_region = Column(String)  # Entanglement region
    loopsize = Column(Integer)  # Loop size
    num_zipper_nc = Column(Integer)  # Number of zipper contacts
    perc_bb_loop = Column(Float)  # Percentage backbone loop
    num_loop_contacting_res = Column(Integer)  # Number of loop contacting residues
    num_cross_nearest_neighbors = Column(Integer)  # Number of crossing nearest neighbors
    ent_coverage = Column(Float)  # Entanglement coverage
    min_N_prot_depth_left = Column(Float)  # Min N protein depth left
    min_N_thread_depth_left = Column(Float)  # Min N thread depth left
    min_N_thread_slippage_left = Column(Float)  # Min N thread slippage left
    min_C_prot_depth_right = Column(Float)  # Min C protein depth right
    min_C_thread_depth_right = Column(Float)  # Min C thread depth right
    min_C_thread_slippage_right = Column(Float)  # Min C thread slippage right
    prot_size = Column(Integer)  # Protein size
    ACO = Column(Float)  # ACO metric
    RCO = Column(Float)  # RCO metric
    CCBond = Column(Boolean)  # Cysteine-cysteine bond
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'feature_id': self.feature_id,
            'job_id': self.job_id,
            'gene': self.gene,
            'PDB': self.PDB,
            'chain': self.chain,
            'ENT_ID': self.ENT_ID,
            'gn': self.gn,
            'N_term_thread': self.N_term_thread,
            'gc': self.gc,
            'C_term_thread': self.C_term_thread,
            'i': self.i,
            'j': self.j,
            'NC': self.NC,
            'NC_wbuff': self.NC_wbuff,
            'NC_region': self.NC_region,
            'crossingsN': self.crossingsN,
            'crossingsC': self.crossingsC,
            'crossingsN_wbuff': self.crossingsN_wbuff,
            'crossingsC_wbuff': self.crossingsC_wbuff,
            'crossingsN_region': self.crossingsN_region,
            'crossingsC_region': self.crossingsC_region,
            'ent_region': self.ent_region,
            'loopsize': self.loopsize,
            'num_zipper_nc': self.num_zipper_nc,
            'perc_bb_loop': self.perc_bb_loop,
            'num_loop_contacting_res': self.num_loop_contacting_res,
            'num_cross_nearest_neighbors': self.num_cross_nearest_neighbors,
            'ent_coverage': self.ent_coverage,
            'min_N_prot_depth_left': self.min_N_prot_depth_left,
            'min_N_thread_depth_left': self.min_N_thread_depth_left,
            'min_N_thread_slippage_left': self.min_N_thread_slippage_left,
            'min_C_prot_depth_right': self.min_C_prot_depth_right,
            'min_C_thread_depth_right': self.min_C_thread_depth_right,
            'min_C_thread_slippage_right': self.min_C_thread_slippage_right,
            'prot_size': self.prot_size,
            'ACO': self.ACO,
            'RCO': self.RCO,
            'CCBond': self.CCBond
        }


class Database:
    """Database manager class"""
    
    def __init__(self, db_path='data/ncle.db', json_backup_path='data/jobs_backup.json'):
        self.db_path = db_path
        self.json_backup_path = json_backup_path
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Create engine and session
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(self.engine)
        
        self.Session = sessionmaker(bind=self.engine)
    
    def get_session(self):
        """Get a new database session"""
        return self.Session()
    
    def create_job(self, email, job_name, pdb_filename, uniprot_id=None, description=None, coarse_grained=False, ca_contact=False, rcsb_pdb_id=None, structure_type='EXP', ent_detection_method=3, generate_features=False):
        """Create a new job entry"""
        session = self.get_session()
        try:
            job = Job(
                job_id=str(uuid.uuid4()),
                email=email,
                job_name=job_name,
                pdb_filename=pdb_filename,
                uniprot_id=uniprot_id,
                description=description,
                status='pending',
                coarse_grained=coarse_grained,
                ca_contact=ca_contact,
                rcsb_pdb_id=rcsb_pdb_id,
                structure_type=structure_type,
                ent_detection_method=ent_detection_method,
                generate_features=generate_features
            )
            session.add(job)
            session.commit()
            job_id = job.job_id
            self.backup_to_json()
            return job_id
        finally:
            session.close()
    
    def get_job(self, job_id):
        """Get a job by ID"""
        session = self.get_session()
        try:
            return session.query(Job).filter_by(job_id=job_id).first()
        finally:
            session.close()
    
    def get_job_by_rcsb_pdb_id(self, rcsb_pdb_id):
        """Get a completed job by RCSB PDB ID"""
        session = self.get_session()
        try:
            # Return the most recent completed job for this PDB ID
            return session.query(Job).filter_by(
                rcsb_pdb_id=rcsb_pdb_id.upper(),
                status='completed'
            ).order_by(Job.completion_timestamp.desc()).first()
        finally:
            session.close()
    
    def update_job_status(self, job_id, status, error_message=None):
        """Update job status"""
        session = self.get_session()
        try:
            job = session.query(Job).filter_by(job_id=job_id).first()
            if job:
                job.status = status
                if error_message:
                    job.error_message = error_message
                if status == 'completed':
                    job.completion_timestamp = datetime.utcnow()
                session.commit()
                self.backup_to_json()
        finally:
            session.close()
    
    def save_results(self, job_id, results_df, hq_results_df=None, clustered_results_df=None, skipped_chains=None):
        """Save analysis results for a job (Native_GE, Native_HQ_GE, and optionally Native_clustered_HQ_GE)"""
        session = self.get_session()
        try:
            # Update job with metadata
            job = session.query(Job).filter_by(job_id=job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            job.num_entanglements = len(results_df)
            job.num_hq_entanglements = len(hq_results_df) if hq_results_df is not None else None
            job.num_clustered_entanglements = len(clustered_results_df) if clustered_results_df is not None else None
            
            # Store skipped chains as JSON
            if skipped_chains:
                job.skipped_chains = json.dumps(skipped_chains)
            
            # Extract unique chains from the dataframe
            # EntDetect doesn't have a 'chain' column, so we need to extract it from residue ranges
            # For now, default to 'A' if not present
            if 'chain' in results_df.columns:
                job.num_chains = results_df['chain'].nunique()
            else:
                job.num_chains = 1  # Single chain assumed
            
            # Save Native_GE results
            for _, row in results_df.iterrows():
                # Get chain - EntDetect may not have this column, default to 'A'
                chain = row.get('chain', 'A') if row.get('chain') else 'A'
                
                result = Result(
                    job_id=job_id,
                    chain=chain,
                    i=int(row['i']),
                    j=int(row['j']),
                    crossingsN=str(row.get('crossingsN', '')) if row.get('crossingsN') and not pd.isna(row.get('crossingsN')) else '',
                    crossingsC=str(row.get('crossingsC', '')) if row.get('crossingsC') and not pd.isna(row.get('crossingsC')) else '',
                    gn=float(row['gn']),
                    gc=float(row['gc']),
                    GLNn=int(row['GLNn']),
                    GLNc=int(row['GLNc']),
                    TLNn=int(row['TLNn']),
                    TLNc=int(row['TLNc']),
                    CCbond=bool(row['CCbond']),
                    ENT=bool(row['ENT'])
                )
                session.add(result)
            
            # Save Native_HQ_GE results if available
            if hq_results_df is not None and len(hq_results_df) > 0:
                for _, row in hq_results_df.iterrows():
                    # Get crossingsN and crossingsC directly
                    crossings_n = str(row.get('crossingsN', '')) if pd.notna(row.get('crossingsN')) else ''
                    crossings_c = str(row.get('crossingsC', '')) if pd.notna(row.get('crossingsC')) else ''
                    # Combine for storage in 'c' column (for backward compatibility with HQResult table)
                    combined_crossings = f"{crossings_n};{crossings_c}" if crossings_n or crossings_c else ''
                    
                    hq_result = HQResult(
                        job_id=job_id,
                        ID=str(row.get('ID', '')),
                        chain=str(row.get('chain', '')),
                        i=int(row['i']),
                        j=int(row['j']),
                        c=combined_crossings,
                        gn=float(row['gn']),
                        gc=float(row['gc']),
                        GLNn=int(row['GLNn']),
                        GLNc=int(row['GLNc']),
                        CCbond=bool(row['CCbond']),
                        ENT=bool(row['ENT'])
                    )
                    session.add(hq_result)
            
            # Save clustered results if available
            if clustered_results_df is not None and len(clustered_results_df) > 0:
                for _, row in clustered_results_df.iterrows():
                    clustered_result = ClusteredResult(
                        job_id=job_id,
                        ID=str(row.get('ID', '')),
                        chain=str(row.get('chain', '')),
                        i=int(row['i']),
                        j=int(row['j']),
                        crossingsN=str(row.get('crossingsN', '')) if pd.notna(row.get('crossingsN')) else '',
                        crossingsC=str(row.get('crossingsC', '')) if pd.notna(row.get('crossingsC')) else '',
                        gn=float(row['gn']),
                        gc=float(row['gc']),
                        GLNn=int(row.get('GLNn', 0)),
                        GLNc=int(row.get('GLNc', 0)),
                        TLNn=int(row.get('TLNn', 0)),
                        TLNc=int(row.get('TLNc', 0)),
                        num_contacts=int(row.get('num_contacts', 1)),
                        contacts=str(row.get('contacts', '')) if pd.notna(row.get('contacts')) else '',
                        CCBond=bool(row.get('CCBond', False))
                    )
                    session.add(clustered_result)
            
            session.commit()
            self.backup_to_json()
        finally:
            session.close()
    
    def save_entanglement_features(self, job_id, features_df):
        """Save entanglement features for a job (Native_clustered_HQ_GE_features)
        
        Handles EntDetect 1.1.1+ column names:
        - PDB, ENT-ID, N_term_thread, C_term_thread, NC, NC_wbuff, NC_region
        - crossingsN, crossingsC, crossingsN_wbuff, crossingsC_wbuff, crossingsN_region, crossingsC_region
        - min_N_prot_depth_left, min_C_prot_depth_right, ACO, RCO, CCBond
        
        Properly handles NaN/None values from pandas DataFrames.
        """
        import pandas as pd
        import numpy as np
        
        # DEBUG: Log what columns are in the dataframe
        print(f"\n[DEBUG] save_entanglement_features for job {job_id}")
        print(f"[DEBUG] DataFrame columns: {list(features_df.columns)}")
        if len(features_df) > 0:
            print(f"[DEBUG] First row - ENT-ID: {features_df.iloc[0].get('ENT-ID', 'N/A')}, N_term: {features_df.iloc[0].get('N_term_thread', 'N/A')}, C_term: {features_df.iloc[0].get('C_term_thread', 'N/A')}, crossingsN: {features_df.iloc[0].get('crossingsN', 'N/A')}, crossingsC: {features_df.iloc[0].get('crossingsC', 'N/A')}")
        
        session = self.get_session()
        try:
            for idx, (_, row) in enumerate(features_df.iterrows()):
                # Helper function to safely convert values, handling NaN
                def safe_float(val):
                    if pd.isna(val):
                        return None
                    try:
                        return float(val) if val != '' else None
                    except (ValueError, TypeError):
                        return None
                
                def safe_int(val):
                    if pd.isna(val):
                        return None
                    try:
                        return int(float(val)) if val != '' else None
                    except (ValueError, TypeError):
                        return None
                
                def safe_str(val):
                    """Convert values to string, handling NaN and numeric values"""
                    if pd.isna(val):
                        return None
                    if isinstance(val, float) and np.isnan(val):
                        return None
                    s = str(val).strip()
                    if not s or s.lower() == 'nan':
                        return None
                    # Remove trailing .0 for numeric strings that are actually integers
                    if s.endswith('.0') and s[:-2].replace('-', '').isdigit():
                        s = s[:-2]
                    return s if s else None
                
                def safe_bool(val):
                    if pd.isna(val):
                        return False
                    if isinstance(val, bool):
                        return val
                    s = str(val).lower().strip()
                    return s in ['true', '1', 'yes']
                
                # Handle both old and new column name formats
                # Old format (EntDetect 1.0): crossings, crossings_wbuff, crossings_region (single column for both terminals)
                # New format (EntDetect 1.1+): crossingsN, crossingsC, crossingsN_wbuff, crossingsC_wbuff, crossingsN_region, crossingsC_region
                # For old format, map to appropriate terminal based on which thread exists
                n_term_thread = safe_int(row.get('N_term_thread', 0))
                c_term_thread = safe_int(row.get('C_term_thread', 0))
                old_crossings = row.get('crossings')
                old_crossings_wbuff = row.get('crossings_wbuff')
                old_crossings_region = row.get('crossings_region')
                
                crossingsN = row.get('crossingsN')
                if pd.isna(crossingsN) or crossingsN == '':
                    # For old format, only use 'crossings' if N-terminal thread exists
                    if n_term_thread and 'crossings' in row and not pd.isna(old_crossings):
                        crossingsN = old_crossings
                    else:
                        crossingsN = None
                
                crossingsC = row.get('crossingsC')
                if pd.isna(crossingsC) or crossingsC == '':
                    # For old format, only use 'crossings' if C-terminal thread exists
                    if c_term_thread and 'crossings' in row and not pd.isna(old_crossings):
                        crossingsC = old_crossings
                    else:
                        crossingsC = None
                
                crossingsN_wbuff = row.get('crossingsN_wbuff')
                if pd.isna(crossingsN_wbuff) or crossingsN_wbuff == '':
                    if n_term_thread and 'crossings_wbuff' in row and not pd.isna(old_crossings_wbuff):
                        crossingsN_wbuff = old_crossings_wbuff
                    else:
                        crossingsN_wbuff = None
                
                crossingsC_wbuff = row.get('crossingsC_wbuff')
                if pd.isna(crossingsC_wbuff) or crossingsC_wbuff == '':
                    if c_term_thread and 'crossings_wbuff' in row and not pd.isna(old_crossings_wbuff):
                        crossingsC_wbuff = old_crossings_wbuff
                    else:
                        crossingsC_wbuff = None
                
                crossingsN_region = row.get('crossingsN_region')
                if pd.isna(crossingsN_region) or crossingsN_region == '':
                    if n_term_thread and 'crossings_region' in row and not pd.isna(old_crossings_region):
                        crossingsN_region = old_crossings_region
                    else:
                        crossingsN_region = None
                
                crossingsC_region = row.get('crossingsC_region')
                if pd.isna(crossingsC_region) or crossingsC_region == '':
                    if c_term_thread and 'crossings_region' in row and not pd.isna(old_crossings_region):
                        crossingsC_region = old_crossings_region
                    else:
                        crossingsC_region = None
                
                # NOTE: Crossing swap logic disabled - EntDetect from ncle_prod should produce correct format
                # If this needs to be re-enabled later, check that EntDetect version is correct first

                feature = EntanglementFeature(
                    job_id=job_id,
                    gene=safe_str(row.get('gene', '')),
                    PDB=safe_str(row.get('PDB', '')),
                    chain=safe_str(row.get('chain', '')),
                    ENT_ID=safe_int(row.get('ENT-ID', 0)),
                    gn=safe_float(row.get('gn')),
                    N_term_thread=safe_int(row.get('N_term_thread')),
                    gc=safe_float(row.get('gc')),
                    C_term_thread=safe_int(row.get('C_term_thread')),
                    i=safe_int(row.get('i')),
                    j=safe_int(row.get('j')),
                    NC=safe_str(row.get('NC')),
                    NC_wbuff=safe_str(row.get('NC_wbuff')),
                    NC_region=safe_str(row.get('NC_region')),
                    crossingsN=safe_str(crossingsN),
                    crossingsC=safe_str(crossingsC),
                    crossingsN_wbuff=safe_str(crossingsN_wbuff),
                    crossingsC_wbuff=safe_str(crossingsC_wbuff),
                    crossingsN_region=safe_str(crossingsN_region),
                    crossingsC_region=safe_str(crossingsC_region),
                    ent_region=safe_str(row.get('ent_region')),
                    loopsize=safe_int(row.get('loopsize')),
                    num_zipper_nc=safe_int(row.get('num_zipper_nc')),
                    perc_bb_loop=safe_float(row.get('perc_bb_loop')),
                    num_loop_contacting_res=safe_int(row.get('num_loop_contacting_res')),
                    num_cross_nearest_neighbors=safe_int(row.get('num_cross_nearest_neighbors')),
                    ent_coverage=safe_float(row.get('ent_coverage')),
                    min_N_prot_depth_left=safe_float(row.get('min_N_prot_depth_left')),
                    min_N_thread_depth_left=safe_float(row.get('min_N_thread_depth_left')),
                    min_N_thread_slippage_left=safe_float(row.get('min_N_thread_slippage_left')),
                    min_C_prot_depth_right=safe_float(row.get('min_C_prot_depth_right')),
                    min_C_thread_depth_right=safe_float(row.get('min_C_thread_depth_right')),
                    min_C_thread_slippage_right=safe_float(row.get('min_C_thread_slippage_right')),
                    prot_size=safe_int(row.get('prot_size')),
                    ACO=safe_float(row.get('ACO')),
                    RCO=safe_float(row.get('RCO')),
                    CCBond=safe_bool(row.get('CCBond'))
                )
                session.add(feature)
            
            session.commit()
        finally:
            session.close()
    
    def get_entanglement_features(self, job_id):
        """Get entanglement features for a job"""
        session = self.get_session()
        try:
            features = session.query(EntanglementFeature).filter_by(job_id=job_id).all()
            return [f.to_dict() for f in features]
        finally:
            session.close()
    
    def get_all_jobs(self, limit=100, offset=0, order_by='upload_timestamp', descending=True):
        """Get all jobs with pagination"""
        session = self.get_session()
        try:
            query = session.query(Job)
            if descending:
                query = query.order_by(getattr(Job, order_by).desc())
            else:
                query = query.order_by(getattr(Job, order_by))
            return query.limit(limit).offset(offset).all()
        finally:
            session.close()
    
    def get_job_with_results(self, job_id):
        """Get job with all its results (Native_GE, Native_HQ_GE, and Native_clustered_HQ_GE)"""
        session = self.get_session()
        try:
            job = session.query(Job).filter_by(job_id=job_id).first()
            if not job:
                return None
            
            results = session.query(Result).filter_by(job_id=job_id).all()
            hq_results = session.query(HQResult).filter_by(job_id=job_id).all()
            clustered_results = session.query(ClusteredResult).filter_by(job_id=job_id).all()
            
            return {
                'job': job.to_dict(include_email=False),
                'results': [r.to_dict() for r in results],
                'hq_results': [r.to_dict() for r in hq_results],
                'clustered_results': [r.to_dict() for r in clustered_results]
            }
        finally:
            session.close()
    
    def backup_to_json(self):
        """Backup database to JSON for debugging"""
        session = self.get_session()
        try:
            jobs = session.query(Job).all()
            backup_data = []
            
            for job in jobs:
                job_data = job.to_dict(include_email=True)
                results = session.query(Result).filter_by(job_id=job.job_id).all()
                hq_results = session.query(HQResult).filter_by(job_id=job.job_id).all()
                clustered_results = session.query(ClusteredResult).filter_by(job_id=job.job_id).all()
                job_data['results'] = [r.to_dict() for r in results]
                job_data['hq_results'] = [r.to_dict() for r in hq_results]
                job_data['clustered_results'] = [r.to_dict() for r in clustered_results]
                backup_data.append(job_data)
            
            with open(self.json_backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
        finally:
            session.close()
    
    def count_jobs(self):
        """Count total number of jobs"""
        session = self.get_session()
        try:
            return session.query(Job).count()
        finally:
            session.close()


# Initialize database instance
db = Database()
