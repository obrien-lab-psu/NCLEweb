#!/usr/bin/env python3
"""
PDB Preprocessor for NCLE Web Application

This module preprocesses PDB files to:
1. Filter out chains with fewer than MIN_RESIDUES residues (default: 10)
2. Validate C-alpha coarse-grained PDB format (atom name "A", residue names "G1", "G2", etc.)
3. Provide warnings about skipped chains
4. Generate a cleaned PDB file ready for EntDetect analysis

Supports both:
- All-atom PDB files
- C-alpha coarse-grained PDB files
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
import re

# Minimum number of residues required for a chain to be analyzed
MIN_RESIDUES = 10


class PDBPreprocessor:
    """Preprocess PDB files for Gaussian Entanglement analysis"""
    
    def __init__(self, pdb_path, is_coarse_grained=False, min_residues=MIN_RESIDUES):
        """
        Initialize PDB preprocessor
        
        Parameters
        ----------
        pdb_path : str
            Path to input PDB file
        is_coarse_grained : bool
            Whether the PDB is C-alpha coarse-grained format
        min_residues : int
            Minimum number of residues required per chain (default: 10)
        """
        self.pdb_path = pdb_path
        self.is_coarse_grained = is_coarse_grained
        self.min_residues = min_residues
        self.warnings = []
        self.chain_residue_counts = defaultdict(int)
        self.valid_chains = set()
        self.skipped_chains = set()
        
    def count_residues_per_chain(self):
        """
        Count the number of residues in each chain
        
        For all-atom: Count unique CA atoms
        For C-alpha CG: Count all ATOM records
        Note: Chains with only HETATM records (ligands, waters, ions) are excluded
        
        Returns
        -------
        dict
            Dictionary mapping chain ID to residue count
        """
        chain_residues = defaultdict(set)
        chain_has_protein = set()  # Track which chains have ATOM records (protein)
        
        with open(self.pdb_path, 'r') as f:
            for line in f:
                if line.startswith('ATOM'):
                    # Parse ATOM line (protein atoms)
                    atom_name = line[12:16].strip()
                    chain_id = line[21:22].strip()
                    residue_num = line[22:26].strip()
                    
                    # Mark this chain as having protein
                    chain_has_protein.add(chain_id)
                    
                    # For all-atom PDBs, only count CA atoms
                    if not self.is_coarse_grained:
                        if atom_name == 'CA':
                            chain_residues[chain_id].add(residue_num)
                    else:
                        # For C-alpha CG, count all atoms (which should be one per residue)
                        chain_residues[chain_id].add(residue_num)
        
        # Convert sets to counts, but only for chains with ATOM records
        for chain_id, residues in chain_residues.items():
            if chain_id in chain_has_protein:
                self.chain_residue_counts[chain_id] = len(residues)
        
        return self.chain_residue_counts
    
    def validate_coarse_grained_format(self):
        """
        Validate C-alpha coarse-grained PDB format
        
        Requirements:
        - All ATOM records must have atom name "A"
        - Residue names must follow pattern "G1", "G2", "G3", etc.
        
        Returns
        -------
        bool
            True if format is valid, False otherwise
        """
        if not self.is_coarse_grained:
            return True
        
        invalid_atoms = []
        invalid_residues = []
        line_num = 0
        
        with open(self.pdb_path, 'r') as f:
            for line in f:
                line_num += 1
                if not line.startswith('ATOM'):
                    continue
                
                atom_name = line[12:16].strip()
                residue_name = line[17:20].strip()
                
                # Check atom name
                if atom_name != 'A':
                    invalid_atoms.append(f"Line {line_num}: atom name '{atom_name}' (expected 'A')")
                
                # Check residue name pattern (should be G followed by number)
                if not re.match(r'^G\d+$', residue_name):
                    invalid_residues.append(f"Line {line_num}: residue name '{residue_name}' (expected 'G#' pattern)")
        
        if invalid_atoms:
            self.warnings.append(f"Invalid atom names in C-alpha CG PDB (first 5): {invalid_atoms[:5]}")
        
        if invalid_residues:
            self.warnings.append(f"Invalid residue names in C-alpha CG PDB (first 5): {invalid_residues[:5]}")
        
        return len(invalid_atoms) == 0 and len(invalid_residues) == 0
    
    def filter_valid_chains(self):
        """
        Determine which chains have enough residues for analysis
        
        Returns
        -------
        tuple
            (valid_chains, skipped_chains) - sets of chain IDs
        """
        self.count_residues_per_chain()
        
        for chain_id, count in self.chain_residue_counts.items():
            if count >= self.min_residues:
                self.valid_chains.add(chain_id)
            else:
                self.skipped_chains.add(chain_id)
                warning = f"Chain {chain_id}: Only {count} residue(s) found (minimum {self.min_residues} required) - SKIPPED"
                self.warnings.append(warning)
        
        return self.valid_chains, self.skipped_chains
    
    def write_filtered_pdb(self, output_path):
        """
        Write a new PDB file containing only valid protein chains
        Excludes HETATM records (ligands, waters, ions)
        
        Parameters
        ----------
        output_path : str
            Path to output filtered PDB file
            
        Returns
        -------
        bool
            True if file was written successfully
        """
        if not self.valid_chains:
            self.warnings.append("No valid chains found - cannot create filtered PDB")
            return False
        
        atoms_written = 0
        
        with open(self.pdb_path, 'r') as infile, open(output_path, 'w') as outfile:
            for line in infile:
                # Skip HETATM records (ligands, waters, ions - not protein)
                if line.startswith('HETATM'):
                    continue
                    
                # Keep all non-ATOM, non-HETATM records (HEADER, CRYST, etc.)
                if not line.startswith('ATOM'):
                    outfile.write(line)
                    continue
                
                # Check if this ATOM belongs to a valid protein chain
                chain_id = line[21:22].strip()
                
                if chain_id in self.valid_chains:
                    outfile.write(line)
                    atoms_written += 1
        
        return atoms_written > 0
    
    def preprocess(self, output_path=None):
        """
        Main preprocessing pipeline
        
        Parameters
        ----------
        output_path : str, optional
            Path to write filtered PDB. If None, overwrites input file.
            
        Returns
        -------
        dict
            Results dictionary with:
            - success: bool
            - valid_chains: list
            - skipped_chains: list
            - warnings: list
            - output_file: str
            - total_residues_kept: int
        """
        # Validate file exists
        if not os.path.exists(self.pdb_path):
            return {
                'success': False,
                'error': f"PDB file not found: {self.pdb_path}",
                'warnings': []
            }
        
        # Validate C-alpha CG format if needed
        if self.is_coarse_grained:
            if not self.validate_coarse_grained_format():
                return {
                    'success': False,
                    'error': 'Invalid C-alpha coarse-grained PDB format',
                    'warnings': self.warnings
                }
        
        # Filter chains
        valid_chains, skipped_chains = self.filter_valid_chains()
        
        # If no valid chains, fail
        if not valid_chains:
            return {
                'success': False,
                'error': f'No chains have at least {self.min_residues} residues',
                'warnings': self.warnings,
                'skipped_chains': list(skipped_chains),
                'chain_counts': dict(self.chain_residue_counts)
            }
        
        # Determine output path
        if output_path is None:
            output_path = self.pdb_path
        
        # Write filtered PDB
        write_success = self.write_filtered_pdb(output_path)
        
        if not write_success:
            return {
                'success': False,
                'error': 'Failed to write filtered PDB file',
                'warnings': self.warnings
            }
        
        # Calculate total residues kept
        total_residues_kept = sum(self.chain_residue_counts[c] for c in valid_chains)
        
        return {
            'success': True,
            'valid_chains': sorted(list(valid_chains)),
            'skipped_chains': sorted(list(skipped_chains)),
            'warnings': self.warnings,
            'output_file': output_path,
            'total_residues_kept': total_residues_kept,
            'chain_counts': dict(self.chain_residue_counts)
        }


def preprocess_pdb(pdb_path, is_coarse_grained=False, output_path=None, min_residues=MIN_RESIDUES):
    """
    Convenience function to preprocess a PDB file
    
    Parameters
    ----------
    pdb_path : str
        Path to input PDB file
    is_coarse_grained : bool
        Whether the PDB is C-alpha coarse-grained format
    output_path : str, optional
        Path to write filtered PDB. If None, overwrites input file.
    min_residues : int
        Minimum number of residues required per chain
        
    Returns
    -------
    dict
        Results dictionary from PDBPreprocessor.preprocess()
    """
    preprocessor = PDBPreprocessor(pdb_path, is_coarse_grained, min_residues)
    return preprocessor.preprocess(output_path)


if __name__ == "__main__":
    # Command-line interface
    if len(sys.argv) < 2:
        print("Usage: python pdb_preprocessor.py <pdb_file> [--cg] [--output <output_file>] [--min-residues <n>]")
        print("\nOptions:")
        print("  --cg                  Treat as C-alpha coarse-grained PDB")
        print("  --output <file>       Output file path (default: overwrite input)")
        print("  --min-residues <n>    Minimum residues per chain (default: 10)")
        sys.exit(1)
    
    pdb_file = sys.argv[1]
    is_cg = '--cg' in sys.argv
    output_file = None
    min_res = MIN_RESIDUES
    
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
    
    if '--min-residues' in sys.argv:
        idx = sys.argv.index('--min-residues')
        if idx + 1 < len(sys.argv):
            min_res = int(sys.argv[idx + 1])
    
    result = preprocess_pdb(pdb_file, is_cg, output_file, min_res)
    
    print("\n" + "="*60)
    print("PDB Preprocessing Results")
    print("="*60)
    
    if result['success']:
        print(f"✓ Success!")
        print(f"\nValid chains ({len(result['valid_chains'])}): {', '.join(result['valid_chains'])}")
        if result['skipped_chains']:
            print(f"\nSkipped chains ({len(result['skipped_chains'])}): {', '.join(result['skipped_chains'])}")
        print(f"\nTotal residues retained: {result['total_residues_kept']}")
        print(f"Output file: {result['output_file']}")
        
        if result['warnings']:
            print(f"\n⚠ Warnings:")
            for warning in result['warnings']:
                print(f"  - {warning}")
    else:
        print(f"✗ Failed: {result['error']}")
        if result.get('warnings'):
            print(f"\n⚠ Warnings:")
            for warning in result['warnings']:
                print(f"  - {warning}")
        if result.get('chain_counts'):
            print(f"\nChain residue counts:")
            for chain, count in sorted(result['chain_counts'].items()):
                print(f"  Chain {chain}: {count} residues")
    
    print("="*60)
    
    sys.exit(0 if result['success'] else 1)
