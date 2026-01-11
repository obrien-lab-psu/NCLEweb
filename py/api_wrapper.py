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
from EntDetect.gaussian_entanglement import GaussianEntanglement
import pandas as pd
import MDAnalysis as mda

# Try to import clustering - it may not be available in all environments
try:
    from EntDetect.clustering import ClusterNativeEntanglements
    CLUSTERING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Clustering not available: {e}")
    CLUSTERING_AVAILABLE = False


def get_chains(pdb_path):
    """
    Detect all chains in a PDB structure using MDAnalysis.
    
    Parameters
    ----------
    pdb_path : str
        Path to PDB file
        
    Returns
    -------
    list
        List of chain identifiers (e.g., ['A', 'B', 'C'])
    """
    try:
        u = mda.Universe(pdb_path)
        chains = sorted(set(u.atoms.chainIDs))
        # Filter out empty chain IDs
        chains = [c for c in chains if c and c.strip()]
        return chains if chains else ['']  # Return [''] if no chains found
    except Exception as e:
        print(f"Warning: Could not detect chains: {e}")
        return ['']  # Return single empty chain on error


def calculate_native_ge(pdb_path, cleanup=True, structure_type="EXP", organism="Ecoli", coarse_grained=False, ca_contact=False):
    """
    Calculate native Gaussian entanglement for a PDB file.
    Runs Native_GE, Native_HQ_GE, and Native_clustered_HQ_GE analyses.
    
    Parameters
    ----------
    pdb_path : str
        Path to the input PDB file
    cleanup : bool, optional
        Whether to clean up temporary files after analysis, by default True
    structure_type : str, optional
        Structure type: "EXP" for experimental or "AF" for AlphaFold, by default "EXP"
    organism : str, optional
        Organism for clustering: "Ecoli", "Human", or "Yeast", by default "Ecoli"
    coarse_grained : bool, optional
        Whether the structure is coarse-grained (C-alpha only) - sets CG parameter, by default False
    ca_contact : bool, optional
        Whether to use C-alpha contacts (vs heavy atom contacts) - sets Calpha parameter, by default False
        
    Returns
    -------
    dict
        Dictionary containing:
        - 'success': bool indicating if analysis succeeded
        - 'data': pandas DataFrame with raw GE results (if success=True)
        - 'csv': str with CSV-formatted Native_GE results (if success=True)
        - 'hq_data': pandas DataFrame with HQ filtered results (if success=True)
        - 'hq_csv': str with CSV-formatted Native_HQ_GE results (if success=True)
        - 'clustered_data': pandas DataFrame with clustered results (if success=True)
        - 'clustered_csv': str with CSV-formatted clustered results (if success=True)
        - 'error': str with error message (if success=False)
        - 'pdb_id': str identifier from filename
    """
    result = {
        'success': False,
        'data': None,
        'csv': None,
        'hq_data': None,
        'hq_csv': None,
        'clustered_data': None,
        'clustered_csv': None,
        'error': None,
        'pdb_id': None
    }
    
    # Extract PDB ID from filename
    pdb_id = Path(pdb_path).stem
    result['pdb_id'] = pdb_id
    
    # Detect chains in the structure
    chains = get_chains(pdb_path)
    print(f"Detected {len(chains)} chain(s): {chains}")
    
    # Create temporary directory for output
    temp_dir = tempfile.mkdtemp(prefix=f'ge_analysis_{pdb_id}_')
    
    # Store results from all chains
    all_native_dfs = []
    all_hq_dfs = []
    all_clustered_dfs = []
    
    # Store results from all chains
    all_native_dfs = []
    all_hq_dfs = []
    all_clustered_dfs = []
    
    try:
        # Verify input file exists
        if not os.path.exists(pdb_path):
            result['error'] = f"PDB file not found: {pdb_path}"
            return result
        
        # Process each chain
        for chain in chains:
            # Use chain-specific ID if multiple chains
            if len(chains) > 1:
                chain_id = f"{pdb_id}_{chain}" if chain else pdb_id
            else:
                chain_id = pdb_id
                
            print(f"\n{'='*60}")
            print(f"Processing chain: {chain if chain else '(no chain)'}")
            print(f"Chain ID: {chain_id}")
            print(f"{'='*60}")
            
            # Create chain-specific directories
            chain_temp_dir = os.path.join(temp_dir, f'chain_{chain}' if chain else 'chain_default')
            hq_temp_dir = os.path.join(chain_temp_dir, 'HQ')
            os.makedirs(hq_temp_dir, exist_ok=True)
            
            # Initialize GaussianEntanglement with parameters
            # g_threshold=0.6, density=0.0
            # CG=coarse_grained (True for C-alpha only models, False for all-atom)
            # Calpha=ca_contact (True for C-alpha contacts, False for heavy atom contacts)
            ge = GaussianEntanglement(
                g_threshold=0.6, 
                density=0.0, 
                Calpha=ca_contact, 
                CG=coarse_grained
            )
            
            # Calculate native entanglements (Step 1: Native_GE)
            print(f"Analyzing {chain_id}...")
            native_ent = ge.calculate_native_entanglements(
                pdb_file=pdb_path,
                outdir=chain_temp_dir,
                ID=chain_id,
                chain=chain if chain else None
            )
            
            # Extract Native_GE results
            df = native_ent['ent_result']
            if len(df) > 0:
                all_native_dfs.append(df)
                print(f"Native_GE complete for chain {chain}. Found {len(df)} results.")
            else:
                print(f"No entanglements found for chain {chain}. Skipping.")
                continue
            
            # Calculate high-quality entanglements (Step 2: Native_HQ_GE)
            print(f"Filtering for high-quality entanglements...")
            try:
                hq_ent = ge.select_high_quality_entanglements(
                    GE_filepath=native_ent['outfile'],
                    pdb=pdb_path,
                    outdir=hq_temp_dir,
                    ID=chain_id,
                    model=structure_type,  # Use user-selected structure type (EXP or AF)
                    mapping='None',  # No mapping file
                    chain=chain if chain else None
                )
                
                # Extract Native_HQ_GE results
                hq_df = hq_ent['GE_data']
                if len(hq_df) > 0:
                    all_hq_dfs.append(hq_df)
                    print(f"Native_HQ_GE complete for chain {chain}. Found {len(hq_df)} high-quality results.")
                else:
                    print(f"No high-quality entanglements found for chain {chain}.")
                
                # Calculate clustered entanglements (Step 3: Native_clustered_HQ_GE)
                if CLUSTERING_AVAILABLE and len(hq_df) > 0:
                    print(f"Clustering high-quality entanglements with organism={organism}...")
                    try:
                        clustering = ClusterNativeEntanglements(organism=organism)
                        clustered_temp_dir = os.path.join(chain_temp_dir, 'Clustered')
                        os.makedirs(clustered_temp_dir, exist_ok=True)
                        
                        clustered_ent = clustering.Cluster_NativeEntanglements(
                            GE_filepath=hq_ent['outfile'],
                            outdir=clustered_temp_dir,
                            outfile=f"{chain_id}_clustered.csv"
                        )
                        
                        # Extract clustered results
                        clustered_df = clustered_ent['ent_result']
                        if len(clustered_df) > 0:
                            all_clustered_dfs.append(clustered_df)
                            print(f"Native_clustered_HQ_GE complete for chain {chain}. Found {len(clustered_df)} clustered results.")
                        else:
                            print(f"No clustered entanglements found for chain {chain}.")
                    except Exception as e:
                        print(f"Warning: Clustering failed for chain {chain}: {e}")
                        # Continue even if clustering fails for this chain
                        
            except Exception as e:
                print(f"Warning: HQ filtering failed for chain {chain}: {e}")
                # Continue with next chain even if HQ fails
        
        # Combine results from all chains
        if all_native_dfs:
            combined_native_df = pd.concat(all_native_dfs, ignore_index=True)
            csv_output = combined_native_df.to_csv(sep='|', index=False)
            result['success'] = True
            result['data'] = combined_native_df
            result['csv'] = csv_output
            print(f"\nCombined Native_GE: {len(combined_native_df)} total results from {len(all_native_dfs)} chain(s)")
        else:
            result['error'] = "No entanglements found in any chain"
            return result
            
        if all_hq_dfs:
            combined_hq_df = pd.concat(all_hq_dfs, ignore_index=True)
            hq_csv_output = combined_hq_df.to_csv(sep='|', index=False)
            result['hq_data'] = combined_hq_df
            result['hq_csv'] = hq_csv_output
            print(f"Combined Native_HQ_GE: {len(combined_hq_df)} total results from {len(all_hq_dfs)} chain(s)")
        else:
            result['hq_data'] = None
            result['hq_csv'] = None
            print("No high-quality entanglements found in any chain")
            
        if all_clustered_dfs:
            combined_clustered_df = pd.concat(all_clustered_dfs, ignore_index=True)
            clustered_csv_output = combined_clustered_df.to_csv(sep='|', index=False)
            result['clustered_data'] = combined_clustered_df
            result['clustered_csv'] = clustered_csv_output
            print(f"Combined Native_clustered_HQ_GE: {len(combined_clustered_df)} total results from {len(all_clustered_dfs)} chain(s)")
        elif CLUSTERING_AVAILABLE:
            result['clustered_data'] = None
            result['clustered_csv'] = None
            print("No clustered entanglements found in any chain")
        else:
            result['clustered_data'] = None
            result['clustered_csv'] = None
            print("Clustering module not available (pyemma dependency missing)")
        
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
