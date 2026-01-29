#!/usr/bin/env python3
from EntDetect.gaussian_entanglement import GaussianEntanglement
from EntDetect.clustering import ClusterNativeEntanglements
from EntDetect.entanglement_features import FeatureGen

"""
python scripts/run_nativeNCLE.py 
--struct /path/to/structure.pdb 
--outdir TestingGrounds/NativeNCLE/ 
--ID 1ZMR 
--organism Ecoli

Script to calculate native Gaussian entanglements in a given structure (PDB or COR file), cluster them, and generate entanglement features.
"""

if __name__ == "__main__":

    import multiprocessing as mp
    import sys, os
    import argparse
    import time

    start_time = time.time()

    parser = argparse.ArgumentParser(description="Process user specified arguments")
    parser.add_argument("--struct", type=str, required=True, help="Path to PDB structure file")
    parser.add_argument("--outdir", type=str, required=True, help="output directory for results")
    parser.add_argument("--ID", type=str, required=False, help="An id for the analysis (defaults to structure basename)")
    parser.add_argument("--chain", type=str, required=False, help="Chain identifier (optional, processes all chains if not specified)", default=None)
    parser.add_argument("--organism", type=str, required=False, help="Organism name for clustering: {Ecoli, Human, Yeast}", default='Ecoli')
    parser.add_argument("--Accession", type=str, required=False, help="UniProt Accession for the protein", default='P00558')
    parser.add_argument("--cg", action='store_true', help="Indicate structure is coarse-grained (C-alpha only) model")
    parser.add_argument("--Calpha", action='store_true', help="Indicate structure is coarse-grained (C-alpha only) model")
    parser.add_argument("--cluster_cutoff", type=float, required=False, help="Clustering cutoff distance (default: 5.0)", default=52.0)
    parser.add_argument("--model", type=str, required=False, help="Model type for high-quality selection: {EXP, AF}", default='EXP')
    parser.add_argument("--ent_detection_method", type=int, required=False, help="ENT detection method: 1=any GLN, 2=any TLN (default), 3=both GLN and TLN same termini", default=3)
    args = parser.parse_args()
    print(args)
    
    struct = args.struct
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    ID = args.ID if args.ID is not None else os.path.splitext(os.path.basename(struct))[0]
    chain = args.chain
    organism = args.organism
    cluster_cutoff = args.cluster_cutoff
    model = args.model

    # Default to C-alpha representation for AF models to avoid the large all-atom contact map
    # that can exhaust memory on big structures. Users can still override with --Calpha/--cg.
    if model.upper() == 'AF' and not args.Calpha and not args.cg:
        args.Calpha = True
        print("Auto-enabling --Calpha for AF model to reduce memory usage (override with --Calpha/--cg as needed)")
    # Set up Gaussian Entanglement and Clustering objects
    ge = GaussianEntanglement(g_threshold=0.6, density=0.0, Calpha=args.Calpha, CG=args.cg, ent_detection_method=args.ent_detection_method)
    clustering = ClusterNativeEntanglements(organism=organism, cut_off=cluster_cutoff)

    # Determine which chains to process
    if chain is not None:
        chains_to_process = [chain]
    else:
        # Get all chains from the structure
        import MDAnalysis as mda
        u = mda.Universe(struct)
        chains_to_process = sorted(set([atom.segid if atom.segid else 'A' for atom in u.atoms if atom.segid or atom.chainID]))
        if not chains_to_process or chains_to_process == ['']:
            # Fallback: use mdtraj to get chains
            import mdtraj as md
            traj = md.load(struct)
            chains_to_process = sorted(set([c.chain_id for c in traj.topology.chains]))
        print(f"Processing chains: {chains_to_process}")

    # Process each chain separately for all steps
    for chain_id in chains_to_process:
        print(f"\n{'='*80}")
        print(f"Processing chain {chain_id}")
        print(f"{'='*80}\n")
        
        # Use chain suffix for file naming when processing multiple chains
        if len(chains_to_process) > 1:
            hq_id = f"{ID}_{chain_id}"
        else:
            hq_id = ID
        
        # All chains use the same Native_GE directory
        ge_outdir = os.path.join(outdir, 'Native_GE')
        os.makedirs(ge_outdir, exist_ok=True)
        
        # Calculate native entanglements for this chain
        NativeEnt = ge.calculate_native_entanglements(struct, outdir=ge_outdir, ID=hq_id, chain=chain_id)
        print(f'Native entanglements saved to {NativeEnt["outfile"]}')
        
        # Optional steps: select high-quality entanglements 
        HQNativeEnt = ge.select_high_quality_entanglements(NativeEnt['outfile'], struct, outdir=os.path.join(outdir, "Native_HQ_GE"), ID=hq_id, model=model, chain=chain_id)
        print(f'High-quality native entanglements saved to {HQNativeEnt["outfile"]}')

        # Cluster the native entanglements to remove degeneracies
        nativeClusteredEnt = clustering.Cluster_NativeEntanglements(HQNativeEnt['outfile'], outdir=os.path.join(outdir, "Native_clustered_HQ_GE"), outfile=f"{hq_id}.csv", chain=chain_id)
        print(f'Clustered native entanglements saved to {nativeClusteredEnt["outfile"]}')

        # Generate entanglement features for clustered native entanglements
        FGen = FeatureGen(struct, outdir=os.path.join(outdir, "Native_clustered_HQ_GE_features"), cluster_file=nativeClusteredEnt['outfile'])
        EntFeatures = FGen.get_uent_features(gene=args.Accession, chain=chain_id, pdbid=ID)
        print(f'Entanglement features saved to {EntFeatures["outfile"]}')


    print(f'NORMAL TERMINATION - {time.time() - start_time} seconds')
