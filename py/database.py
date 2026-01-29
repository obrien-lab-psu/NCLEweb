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
    """Entanglement features table (Native_clustered_HQ_GE_features)"""
    __tablename__ = 'entanglement_features'
    
    feature_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.job_id'), nullable=False, index=True)
    gene = Column(String, nullable=False)  # UniProt gene name
    pdb = Column(String, nullable=False)  # PDB/Structure ID
    chain = Column(String, nullable=False)
    ent_id = Column(Integer, nullable=False)  # Entanglement ID
    gn = Column(Float)  # Gaussian linking number N-terminal
    n_term_thread = Column(Integer)  # N-terminal threading
    gc = Column(Float)  # Gaussian linking number C-terminal
    c_term_thread = Column(Integer)  # C-terminal threading
    i = Column(Integer)  # Residue index i
    j = Column(Integer)  # Residue index j
    nc = Column(String)  # Native contacts (i,j)
    nc_wbuff = Column(String)  # Native contacts with buffer
    nc_region = Column(String)  # NC region
    crossings = Column(String)  # Crossing number
    crossings_wbuff = Column(String)  # Crossings with buffer
    crossings_region = Column(String)  # Crossings region
    ent_region = Column(String)  # Entanglement region
    loopsize = Column(Integer)  # Loop size
    num_zipper_nc = Column(Integer)  # Number of zipper contacts
    perc_bb_loop = Column(Float)  # Percentage backbone loop
    num_loop_contacting_res = Column(Integer)  # Number of loop contacting residues
    num_cross_nearest_neighbors = Column(Integer)  # Number of crossing nearest neighbors
    ent_coverage = Column(Float)  # Entanglement coverage
    min_n_prot_depth_left = Column(Float)  # Min N protein depth left
    min_n_thread_depth_left = Column(Float)  # Min N thread depth left
    min_n_thread_slippage_left = Column(Float)  # Min N thread slippage left
    min_c_prot_depth_right = Column(Float)  # Min C protein depth right
    min_c_thread_depth_right = Column(Float)  # Min C thread depth right
    min_c_thread_slippage_right = Column(Float)  # Min C thread slippage right
    prot_size = Column(Integer)  # Protein size
    aco = Column(Float)  # ACO metric
    rco = Column(Float)  # RCO metric
    cc_bond = Column(Boolean)  # Cysteine-cysteine bond
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'feature_id': self.feature_id,
            'job_id': self.job_id,
            'gene': self.gene,
            'pdb': self.pdb,
            'chain': self.chain,
            'ent_id': self.ent_id,
            'gn': self.gn,
            'n_term_thread': self.n_term_thread,
            'gc': self.gc,
            'c_term_thread': self.c_term_thread,
            'i': self.i,
            'j': self.j,
            'nc': self.nc,
            'nc_wbuff': self.nc_wbuff,
            'nc_region': self.nc_region,
            'crossings': self.crossings,
            'crossings_wbuff': self.crossings_wbuff,
            'crossings_region': self.crossings_region,
            'ent_region': self.ent_region,
            'loopsize': self.loopsize,
            'num_zipper_nc': self.num_zipper_nc,
            'perc_bb_loop': self.perc_bb_loop,
            'num_loop_contacting_res': self.num_loop_contacting_res,
            'num_cross_nearest_neighbors': self.num_cross_nearest_neighbors,
            'ent_coverage': self.ent_coverage,
            'min_n_prot_depth_left': self.min_n_prot_depth_left,
            'min_n_thread_depth_left': self.min_n_thread_depth_left,
            'min_n_thread_slippage_left': self.min_n_thread_slippage_left,
            'min_c_prot_depth_right': self.min_c_prot_depth_right,
            'min_c_thread_depth_right': self.min_c_thread_depth_right,
            'min_c_thread_slippage_right': self.min_c_thread_slippage_right,
            'prot_size': self.prot_size,
            'aco': self.aco,
            'rco': self.rco,
            'cc_bond': self.cc_bond
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
        """Save entanglement features for a job (Native_clustered_HQ_GE_features)"""
        session = self.get_session()
        try:
            for idx, (_, row) in enumerate(features_df.iterrows()):
                if idx == 0:
                    print(f"DEBUG: First row raw data: {dict(row)}")
                    print(f"DEBUG: gn={row.get('gn')}, gc={row.get('gc')}, n_term_thread={row.get('N_term_thread')}")
                
                feature = EntanglementFeature(
                    job_id=job_id,
                    gene=str(row.get('gene', '')),
                    pdb=str(row.get('PDB', '')),
                    chain=str(row.get('chain', '')),
                    ent_id=int(row.get('ENT-ID', 0)),
                    gn=float(row.get('gn', 0)) if row.get('gn') else None,
                    n_term_thread=int(row.get('N_term_thread', 0)) if row.get('N_term_thread') else None,
                    gc=float(row.get('gc', 0)) if row.get('gc') else None,
                    c_term_thread=int(row.get('C_term_thread', 0)) if row.get('C_term_thread') else None,
                    i=int(row.get('i', 0)) if row.get('i') else None,
                    j=int(row.get('j', 0)) if row.get('j') else None,
                    nc=str(row.get('NC', '')) if row.get('NC') else None,
                    nc_wbuff=str(row.get('NC_wbuff', '')) if row.get('NC_wbuff') else None,
                    nc_region=str(row.get('NC_region', '')) if row.get('NC_region') else None,
                    crossings=str(row.get('crossings', '')) if row.get('crossings') else None,
                    crossings_wbuff=str(row.get('crossings_wbuff', '')) if row.get('crossings_wbuff') else None,
                    crossings_region=str(row.get('crossings_region', '')) if row.get('crossings_region') else None,
                    ent_region=str(row.get('ent_region', '')) if row.get('ent_region') else None,
                    loopsize=int(row.get('loopsize', 0)) if row.get('loopsize') else None,
                    num_zipper_nc=int(row.get('num_zipper_nc', 0)) if row.get('num_zipper_nc') else None,
                    perc_bb_loop=float(row.get('perc_bb_loop', 0)) if row.get('perc_bb_loop') else None,
                    num_loop_contacting_res=int(row.get('num_loop_contacting_res', 0)) if row.get('num_loop_contacting_res') else None,
                    num_cross_nearest_neighbors=int(row.get('num_cross_nearest_neighbors', 0)) if row.get('num_cross_nearest_neighbors') else None,
                    ent_coverage=float(row.get('ent_coverage', 0)) if row.get('ent_coverage') else None,
                    min_n_prot_depth_left=float(row.get('min_N_prot_depth_left', 0)) if row.get('min_N_prot_depth_left') else None,
                    min_n_thread_depth_left=float(row.get('min_N_thread_depth_left', 0)) if row.get('min_N_thread_depth_left') else None,
                    min_n_thread_slippage_left=float(row.get('min_N_thread_slippage_left', 0)) if row.get('min_N_thread_slippage_left') else None,
                    min_c_prot_depth_right=float(row.get('min_C_prot_depth_right', 0)) if row.get('min_C_prot_depth_right') else None,
                    min_c_thread_depth_right=float(row.get('min_C_thread_depth_right', 0)) if row.get('min_C_thread_depth_right') else None,
                    min_c_thread_slippage_right=float(row.get('min_C_thread_slippage_right', 0)) if row.get('min_C_thread_slippage_right') else None,
                    prot_size=int(row.get('prot_size', 0)) if row.get('prot_size') else None,
                    aco=float(row.get('ACO', 0)) if row.get('ACO') else None,
                    rco=float(row.get('RCO', 0)) if row.get('RCO') else None,
                    cc_bond=bool(row.get('CCBond', False)) if row.get('CCBond') else False
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
