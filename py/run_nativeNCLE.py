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
    parser.add_argument("--struct", type=str, required=True, help="Path to either .pdb or .cor file for structure")
    parser.add_argument("--outdir", type=str, required=True, help="output directory for results")
    parser.add_argument("--ID", type=str, required=False, help="An id for the analysis")
    parser.add_argument("--organism", type=str, required=False, help="Organism name for clustering: {Ecoli, Human, Yeast}", default='Ecoli')
    args = parser.parse_args()
    print(args)
    struct = args.struct
    outdir = args.outdir
    ID = args.ID
    organism = args.organism

    # Set up Gaussian Entanglement and Clustering objects
    ge = GaussianEntanglement(g_threshold=0.6, density=0.0, Calpha=False, CG=False)
    clustering = ClusterNativeEntanglements(organism=organism)


    # Calculate native entanglements in all-atom PDB of 1ZMR
    NativeEnt = ge.calculate_native_entanglements(struct, outdir=os.path.join(outdir, 'Native_GE'), ID=ID)
    print(f'Native entanglements saved to {NativeEnt["outfile"]}')
    

    # Optional steps: select high-quality entanglements 
    HQNativeEnt = ge.select_high_quality_entanglements(NativeEnt['outfile'], struct, outdir=os.path.join(outdir, "Native_HQ_GE"), ID=ID, model="EXP")
    print(f'High-quality native entanglements saved to {HQNativeEnt["outfile"]}')


    # Cluster the native entanglements to remove degeneracies
    nativeClusteredEnt = clustering.Cluster_NativeEntanglements(HQNativeEnt['outfile'], outdir=os.path.join(outdir, "Native_clustered_HQ_GE"), outfile=f"{ID}.csv")
    print(f'Clustered native entanglements saved to {nativeClusteredEnt["outfile"]}')


    # Generate entanglement features for clustered native entanglements
    FGen = FeatureGen(struct, outdir=os.path.join(outdir, "Native_clustered_HQ_GE_features"), cluster_file=nativeClusteredEnt['outfile'])
    EntFeatures = FGen.get_uent_features(gene='P00558', chain='A', pdbid='1ZMR')
    print(f'Entanglement features saved to {EntFeatures["outfile"]}')


    print(f'NORMAL TERMINATION - {time.time() - start_time} seconds')
