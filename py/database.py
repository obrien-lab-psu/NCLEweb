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
    pdb_id = Column(String, nullable=True)  # Extracted from file or analysis
    upload_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    completion_timestamp = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default='pending')  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    num_entanglements = Column(Integer, nullable=True)
    num_chains = Column(Integer, nullable=True)
    
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
            'pdb_id': self.pdb_id,
            'upload_timestamp': self.upload_timestamp.isoformat() if self.upload_timestamp else None,
            'completion_timestamp': self.completion_timestamp.isoformat() if self.completion_timestamp else None,
            'status': self.status,
            'error_message': self.error_message,
            'num_entanglements': self.num_entanglements,
            'num_chains': self.num_chains
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
    """Entanglement results table"""
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
    
    def create_job(self, email, job_name, pdb_filename, uniprot_id=None, description=None):
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
                status='pending'
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
    
    def save_results(self, job_id, results_df, pdb_id=None):
        """Save analysis results for a job"""
        session = self.get_session()
        try:
            # Update job with metadata
            job = session.query(Job).filter_by(job_id=job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            job.pdb_id = pdb_id
            job.num_entanglements = len(results_df)
            job.num_chains = results_df['chain'].nunique() if 'chain' in results_df.columns else 1
            
            # Save results
            for _, row in results_df.iterrows():
                result = Result(
                    job_id=job_id,
                    chain=row.get('chain', ''),
                    i=int(row['i']),
                    j=int(row['j']),
                    crossingsN=str(row.get('crossingsN', '')) if row.get('crossingsN') else '',
                    crossingsC=str(row.get('crossingsC', '')) if row.get('crossingsC') else '',
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
            
            session.commit()
            self.backup_to_json()
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
        """Get job with all its results"""
        session = self.get_session()
        try:
            job = session.query(Job).filter_by(job_id=job_id).first()
            if not job:
                return None
            
            results = session.query(Result).filter_by(job_id=job_id).all()
            return {
                'job': job.to_dict(include_email=False),
                'results': [r.to_dict() for r in results]
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
                job_data['results'] = [r.to_dict() for r in results]
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
