#!/home/ianms/miniconda3/bin/ python3
"""
API Wrapper for Gaussian Entanglement Analysis
Simplified interface to accept PDB files and return raw Native GE results
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path


from NCLEdetector.gaussian_entanglement import GaussianEntanglement
import pandas as pd
import MDAnalysis as mda

# Import PDB preprocessor
from pdb_preprocessor import preprocess_pdb

# Try to import clustering and feature generation - they may not be available in all environments
try:
    from NCLEdetector.clustering import ClusterNativeEntanglements
    CLUSTERING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Clustering not available: {e}")
    CLUSTERING_AVAILABLE = False

# Don't import FeatureGen at module level - import it where needed inside functions
FEATURE_GEN_AVAILABLE = True  # Assume it's available, check at runtime if needed



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


def calculate_native_ge(pdb_path, cleanup=True, structure_type="EXP", organism="Ecoli", coarse_grained=False, ca_contact=False, cluster_cutoff=None, ent_detection_method=3, uniprot_id=None, generate_features=False, skip_preprocessing=False):
    """
    Calculate native Gaussian entanglement for a PDB file.
    Runs Native_GE, Native_HQ_GE, and Native_clustered_HQ_GE analyses.
    Optionally generates entanglement features.
    
    Parameters
    ----------
    pdb_path : str
        Path to the input PDB file
    cleanup : bool, optional
        Whether to clean up temporary files after analysis, by default True
    structure_type : str, optional
        Structure type: "EXP" for experimental or "AF" for AlphaFold, by default "EXP"
    organism : str, optional
        Organism for clustering: "Ecoli", "Human", "Yeast", or custom name, by default "Ecoli"
    coarse_grained : bool, optional
        Whether the structure is coarse-grained (C-alpha only) - sets CG parameter, by default False
    ca_contact : bool, optional
        Whether to use C-alpha contacts (vs heavy atom contacts) - sets Calpha parameter, by default False
    cluster_cutoff : int, optional
        Custom clustering cutoff (only for non-standard organisms), by default None
    ent_detection_method : int, optional
        Entanglement detection method: 1=GLN-based, 2=TLN-based, 3=Consensus (default), by default 3
    uniprot_id : str, optional
        UniProt accession ID for feature generation, by default None
    generate_features : bool, optional
        Whether to generate entanglement features, by default False
    skip_preprocessing : bool, optional
        Whether to skip PDB preprocessing/filtering, by default False
        Use True to match behavior of run_nativeNCLE.py exactly
        
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
        - 'features_data': pandas DataFrame with features (if generate_features=True and success=True)
        - 'error': str with error message (if success=False)
        - 'pdb_id': str identifier from filename
        - 'warnings': list of preprocessing warnings
    """
    result = {
        'success': False,
        'data': None,
        'csv': None,
        'hq_data': None,
        'hq_csv': None,
        'clustered_data': None,
        'clustered_csv': None,
        'features_data': None,
        'error': None,
        'pdb_id': None,
        'warnings': []
    }
    
    # Extract PDB ID from filename
    pdb_id = Path(pdb_path).stem
    result['pdb_id'] = pdb_id
    
    # DEBUG: Log parameters and NCLEdetector source
    with open('/tmp/api_wrapper_ncledetector_debug.log', 'a') as f:
        import datetime
        f.write(f"\ncalculate_native_ge called at {datetime.datetime.now()}\n")
        f.write(f"  pdb_id: {pdb_id}\n")
        f.write(f"  ent_detection_method: {ent_detection_method}\n")
        f.write(f"  coarse_grained: {coarse_grained}\n")
        f.write(f"  ca_contact: {ca_contact}\n")
        f.write(f"  GaussianEntanglement module: {GaussianEntanglement.__module__}\n")
        f.write(f"  GaussianEntanglement file: {GaussianEntanglement.__module__.split('.')[0]}\n")
        # Try to get the actual file
        try:
            import inspect
            f.write(f"  GaussianEntanglement source file: {inspect.getfile(GaussianEntanglement)}\n")
        except:
            f.write(f"  Could not get GaussianEntanglement source file\n")
        f.write("---\n")
    
    # Verify input file exists
    if not os.path.exists(pdb_path):
        result['error'] = f"PDB file not found: {pdb_path}"
        return result
    
    # Preprocess PDB: Filter chains with < 10 residues
    print(f"\n{'='*60}")
    print(f"Preprocessing PDB file: {pdb_path}")
    print(f"{'='*60}")
    
    if skip_preprocessing:
        print("⚠ PDB preprocessing skipped - using original file directly")
        analysis_pdb = pdb_path
        filtered_pdb_path = None
        result['skipped_chains'] = []
        result['valid_chains'] = ['A']  # Assume chain A if not specified
        result['warnings'] = []
    else:
        # Create a filtered PDB for analysis (keeps original for visualization)
        filtered_pdb_path = pdb_path.replace('.pdb', '_filtered.pdb')
        
        preprocess_result = preprocess_pdb(
            pdb_path=pdb_path,
            is_coarse_grained=coarse_grained,
            output_path=filtered_pdb_path,  # Write to separate file
            min_residues=10
        )
        
        if not preprocess_result['success']:
            result['error'] = preprocess_result['error']
            result['warnings'] = preprocess_result.get('warnings', [])
            return result
        
        # Store preprocessing warnings and chain info
        result['warnings'] = preprocess_result.get('warnings', [])
        result['skipped_chains'] = preprocess_result.get('skipped_chains', [])
        result['valid_chains'] = preprocess_result.get('valid_chains', [])
        
        if preprocess_result.get('skipped_chains'):
            print(f"\n⚠ Skipped chains with < 10 residues: {', '.join(preprocess_result['skipped_chains'])}")
            print(f"   These chains will be visible in structure viewer but not analyzed.")
        
        print(f"✓ Valid chains for analysis: {', '.join(preprocess_result['valid_chains'])}")
        print(f"✓ Total residues to analyze: {preprocess_result['total_residues_kept']}")
        
        # Use filtered PDB for analysis
        analysis_pdb = filtered_pdb_path
    
    # Detect chains in the filtered structure
    chains = get_chains(analysis_pdb)
    print(f"Detected {len(chains)} chain(s) in filtered PDB: {chains}")
    
    # Create temporary directory for output
    temp_dir = tempfile.mkdtemp(prefix=f'ge_analysis_{pdb_id}_')
    
    # Store results from all chains
    all_native_dfs = []
    all_hq_dfs = []
    all_clustered_dfs = []
    chain_clustered_files = {}  # Store per-chain clustered files for feature generation
    
    try:
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
            # ent_detection_method: 1=GLN-based, 2=TLN-based, 3=Consensus
            ge = GaussianEntanglement(
                g_threshold=0.6, 
                density=0.0, 
                Calpha=ca_contact, 
                CG=coarse_grained,
                ent_detection_method=ent_detection_method
            )
            
            # Calculate native entanglements (Step 1: Native_GE)
            print(f"Analyzing {chain_id}...")
            native_ent = ge.calculate_native_entanglements(
                pdb_file=analysis_pdb,  # Use filtered PDB for analysis
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
                    rawNCLE_file=native_ent['outfile'],
                    pdb_file=pdb_path,
                    outdir=hq_temp_dir,
                    ID=chain_id,
                    model=structure_type,  # Use user-selected structure type (EXP or AF)
                    mapping='None'  # No mapping file
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
                        # Use cluster_cutoff if provided, otherwise use organism default
                        if cluster_cutoff is not None:
                            clustering = ClusterNativeEntanglements(organism=organism, cut_off=cluster_cutoff)
                        else:
                            clustering = ClusterNativeEntanglements(organism=organism)
                        clustered_temp_dir = os.path.join(chain_temp_dir, 'Clustered')
                        os.makedirs(clustered_temp_dir, exist_ok=True)
                        
                        clustered_ent = clustering.Cluster_NativeEntanglements(
                            HQ_NCLE_file=hq_ent['outfile'],
                            outdir=clustered_temp_dir,
                            ID=chain_id,
                            chain=chain if chain else None
                        )
                        
                        # Extract clustered results
                        clustered_df = clustered_ent['ent_result']
                        if len(clustered_df) > 0:
                            # The updated EntDetect clustering module now outputs the complete schema:
                            # ID|chain|i|j|crossingsN|crossingsC|gn|gc|GLNn|GLNc|TLNn|TLNc|num_contacts|contacts|CCBond
                            # Just add ENT column which is always True for clustered results
                            clustered_df['ENT'] = True
                            
                            all_clustered_dfs.append(clustered_df)
                            # Save the per-chain clustered file path for later feature generation
                            chain_clustered_files[chain if chain else 'default'] = clustered_ent['outfile']
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
        
        # Generate entanglement features if requested
        import sys

        if generate_features and uniprot_id and result.get('clustered_data') is not None and FEATURE_GEN_AVAILABLE:
            try:
                # Import FeatureGen locally to avoid module context issues
                from NCLEdetector.entanglement_features import FeatureGen

                print(f"\n>>> STARTING FEATURE GENERATION <<<", file=sys.stderr)
                print(f"Generating entanglement features for {uniprot_id}", file=sys.stderr)
                
                # Generate features for each chain
                all_features_dfs = []
                print(f"  Chains detected: {chains}\n")
         
                print(f"DEBUG: About to iterate over chains: {chains}", file=sys.stderr)
                for chain in chains:
                    # Use the per-chain clustered file that was created during clustering
                    chain_key = chain if chain else 'default'
                    if chain_key not in chain_clustered_files:
                        print(f"DEBUG: Skipping chain {chain} - no clustered file found", file=sys.stderr)
                        continue
                    
                    clustered_file_path = chain_clustered_files[chain_key]
                    print(f"DEBUG: Processing chain: {chain}", file=sys.stderr)
                    try:
                        chain_id = f"{pdb_id}_{chain}" if chain else pdb_id
                        print(f"  Processing chain: {chain if chain else 'empty'}\n")
                        

  
                        # Use positional argument for PDBfile to match run_nativeNCLE.py exactly
                        print(f'analysis_pdb: {analysis_pdb}', file=sys.stderr)
                        print(f'clustered_file_path: {clustered_file_path}', file=sys.stderr)
                        print(f'outdir: {os.path.join(temp_dir, f"features_chain_{chain}")}', file=sys.stderr)
                        
                        # DEBUG: Check if FeatureGen is available before calling
                        print(f'DEBUG: FeatureGen available: {FEATURE_GEN_AVAILABLE}', file=sys.stderr)
                        print(f'DEBUG: FeatureGen class: {FeatureGen}', file=sys.stderr)
                        try:
                            print(f'DEBUG: FeatureGen module: {FeatureGen.__module__}', file=sys.stderr)
                        except Exception as debug_e:
                            print(f'DEBUG: Could not get FeatureGen module: {debug_e}', file=sys.stderr)
                        
                        fgen = FeatureGen()
            
                        features_result = fgen.get_uent_features(
                            pdb_file=analysis_pdb,
                            outdir=os.path.join(temp_dir, f'features_chain_{chain}'),
                            cluster_file=clustered_file_path,
                            gene=uniprot_id,
                            pdbid=pdb_id,
                            chain=chain if chain else 'A'
                        )
                        # print(f'features_result: {features_result}', file=sys.stderr)
                        print(features_result['results'], type(features_result['results']), features_result['results'].iloc[0])
        
                        
                        print(f"    features_result type: {type(features_result)}, has outfile: {'outfile' in features_result if isinstance(features_result, dict) else False}\n")
                        
                        if features_result and isinstance(features_result, dict) and 'outfile' in features_result:
                            features_file = features_result['outfile']
                            print(f"    Found outfile: {features_file}\n")
                            if os.path.exists(features_file):
                                # Read features CSV
                                features_df = pd.read_csv(features_file, sep='|')
                                all_features_dfs.append(features_df)
                                # DEBUG: Copy CSV to keep it for inspection and log details
                                debug_csv_path = f"/tmp/debug_features_{chain if chain else 'default'}.csv"
                                shutil.copy(features_file, debug_csv_path)
                                print(f"    ✓ Loaded {len(features_df)} features from CSV (copied to {debug_csv_path})\n")
                                print(f"    CSV separator appears to be: pipe (|)\n")
                                print(f"    Columns in CSV: {list(features_df.columns)}\n")
                                print(f"    DataFrame dtypes:\n")
                                for col in ['crossingsN', 'crossingsC', 'N_term_thread', 'C_term_thread']:
                                    if col in features_df.columns:
                                        print(f"      {col}: {features_df[col].dtype}\n")
                                if len(features_df) > 0:
                                    print(f"    First row values:\n")
                                    for col in ['ENT-ID', 'N_term_thread', 'C_term_thread', 'crossingsN', 'crossingsC']:
                                        val = features_df.iloc[0].get(col, 'MISSING')
                                        print(f"      {col}: {val} (type: {type(val).__name__})\n")
                       
                                print(f"Generated features for chain {chain if chain else 'default'}: {len(features_df)} features")
                            else:
                                print(f"    ✗ Outfile does not exist: {features_file}\n")
                       
                        else:
                            print(f"    ✗ No outfile in result or result is empty\n")
                   
                    except AttributeError as ae:
                        print(f"    ✗ AttributeError: {ae}\n", file=sys.stderr)
                        print(f"    This usually means FeatureGen import failed silently.")
                        print(f"    FeatureGen class should be: {FeatureGen}", file=sys.stderr)
                        print(f"Warning: Could not generate features for chain {chain}: {ae}")
                    except Exception as e:
                        print(f"    ✗ Exception: {e}\n")
            
                        print(f"Warning: Could not generate features for chain {chain}: {e}")

                
                if all_features_dfs:
                    combined_features_df = pd.concat(all_features_dfs, ignore_index=True)
                    result['features_data'] = combined_features_df
                    print(f"SUCCESS: Combined {len(combined_features_df)} features from {len(all_features_dfs)} chain(s)\n")
                    print(f"  Combined DF shape: {combined_features_df.shape}\n")
                    print(f"  Combined DF columns: {list(combined_features_df.columns)}\n")
                    print(f"  First row of combined DF:\n")
                    if len(combined_features_df) > 0:
                        for col in ['ENT-ID', 'N_term_thread', 'C_term_thread', 'crossingsN', 'crossingsC']:
                            val = combined_features_df.iloc[0].get(col, 'MISSING')
                            print(f"    {col}: {val} (type: {type(val).__name__})\n")
                 
                    print(f"Combined features: {len(combined_features_df)} total features from {len(all_features_dfs)} chain(s)")
                else:
                    print("FAILED: No features generated for any chain\n")
              
                    print("No features generated for any chain")
            except Exception as e:
                import traceback
                print(f"EXCEPTION during feature generation: {e}\n", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
            
                print(f"Warning: Feature generation failed: {e}")
                result['features_data'] = None
        elif generate_features and not FEATURE_GEN_AVAILABLE:
            print("WARNING: Feature generation requested but FeatureGen module not available\n")
      
            print("Warning: Feature generation requested but FeatureGen module not available")
   
        
    except Exception as e:
        # Log to file as well
        try:
            with open('logs/feature_generation.log', 'a') as lf:
                lf.write(f"OUTER EXCEPTION: {e}\n")
                lf.flush()
        except:
            pass
        result['error'] = str(e)
        print(f"Error during analysis: {e}")
        
    finally:
        # Clean up temporary directory if requested
        if cleanup and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Cleaned up temporary directory: {temp_dir}")
        
        # Clean up filtered PDB file if it was created
        if cleanup and filtered_pdb_path and os.path.exists(filtered_pdb_path):
            os.remove(filtered_pdb_path)
            print(f"Cleaned up filtered PDB: {filtered_pdb_path}")
    
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
