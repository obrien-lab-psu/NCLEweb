#!/usr/bin/env python3
"""
FastAPI Backend for NCLE Web Application
Provides REST API endpoints for Gaussian Entanglement analysis
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
import sys
from pathlib import Path

# Add py directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from api_wrapper import calculate_native_ge

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
