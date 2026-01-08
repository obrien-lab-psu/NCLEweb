#!/usr/bin/env python3
"""
API Wrapper for Gaussian Entanglement Analysis
Simplified interface to accept PDB files and return raw Native GE results
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from gaussian_entanglement import GaussianEntanglement
import pandas as pd


def calculate_native_ge(pdb_path, cleanup=True):
    """
    Calculate native Gaussian entanglement for a PDB file.
    
    Parameters
    ----------
    pdb_path : str
        Path to the input PDB file
    cleanup : bool, optional
        Whether to clean up temporary files after analysis, by default True
        
    Returns
    -------
    dict
        Dictionary containing:
        - 'success': bool indicating if analysis succeeded
        - 'data': pandas DataFrame with raw GE results (if success=True)
        - 'csv': str with CSV-formatted results (if success=True)
        - 'error': str with error message (if success=False)
        - 'pdb_id': str identifier from filename
    """
    
    result = {
        'success': False,
        'data': None,
        'csv': None,
        'error': None,
        'pdb_id': None
    }
    
    # Extract PDB ID from filename
    pdb_id = Path(pdb_path).stem
    result['pdb_id'] = pdb_id
    
    # Create temporary directory for output
    temp_dir = tempfile.mkdtemp(prefix=f'ge_analysis_{pdb_id}_')
    
    try:
        # Verify input file exists
        if not os.path.exists(pdb_path):
            result['error'] = f"PDB file not found: {pdb_path}"
            return result
        
        # Initialize GaussianEntanglement with default parameters
        # g_threshold=0.6, density=0.0, Calpha=False (use heavy atoms)
        ge = GaussianEntanglement(
            g_threshold=0.6, 
            density=0.0, 
            Calpha=False, 
            CG=False
        )
        
        # Calculate native entanglements
        print(f"Analyzing {pdb_id}...")
        native_ent = ge.calculate_native_entanglements(
            pdb_file=pdb_path,
            outdir=temp_dir,
            ID=pdb_id
        )
        
        # Extract results
        df = native_ent['ent_result']
        
        # Convert to CSV string (using pipe delimiter as in original)
        csv_output = df.to_csv(sep='|', index=False)
        
        result['success'] = True
        result['data'] = df
        result['csv'] = csv_output
        
        print(f"Analysis complete. Found {len(df)} results.")
        
    except Exception as e:
        result['error'] = str(e)
        print(f"Error during analysis: {e}")
        
    finally:
        # Clean up temporary directory if requested
        if cleanup and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Cleaned up temporary directory: {temp_dir}")
    
    return result


def analyze_pdb_file(pdb_path, output_format='csv'):
    """
    Higher-level function that analyzes a PDB and returns results in requested format.
    
    Parameters
    ----------
    pdb_path : str
        Path to PDB file
    output_format : str, optional
        'csv' (default), 'json', or 'dataframe'
        
    Returns
    -------
    str or pandas.DataFrame or dict
        Results in requested format
    """
    
    result = calculate_native_ge(pdb_path, cleanup=True)
    
    if not result['success']:
        raise RuntimeError(f"Analysis failed: {result['error']}")
    
    if output_format == 'csv':
        return result['csv']
    elif output_format == 'json':
        return result['data'].to_json(orient='records')
    elif output_format == 'dataframe':
        return result['data']
    else:
        raise ValueError(f"Unknown output format: {output_format}")


if __name__ == "__main__":
    """
    Command-line interface for testing
    Usage: python api_wrapper.py <pdb_file> [output_file]
    """
    
    if len(sys.argv) < 2:
        print("Usage: python api_wrapper.py <pdb_file> [output_file]")
        sys.exit(1)
    
    pdb_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Run analysis
    result = calculate_native_ge(pdb_file, cleanup=True)
    
    if result['success']:
        print(f"\n{'='*80}")
        print(f"SUCCESS: Analysis complete for {result['pdb_id']}")
        print(f"{'='*80}")
        print("\nResults:")
        print(result['csv'])
        
        # Save to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(result['csv'])
            print(f"\nResults saved to: {output_file}")
    else:
        print(f"\n{'='*80}")
        print(f"ERROR: Analysis failed")
        print(f"{'='*80}")
        print(f"Error message: {result['error']}")
        sys.exit(1)
