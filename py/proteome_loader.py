#!/usr/bin/env python3
"""
Proteome-wide NCLE Data Loader
Loads and aggregates NCLE results from filesystem for gold standard databases
"""

import os
import csv
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

# Base paths for proteome data
PROTEOME_DATA_BASE = Path("/home/ianms/NCLE_DB/NCLE_results")
PROTEIN_STRUCTURES_BASE = Path("/home/ianms/DataStore/Protein_structures/AlphaFoldv4")

# Configuration for organisms
ORGANISMS = {
    "Yeast": {
        "display_name": "Yeast (S. cerevisiae)",
        "base_path": "Yeast/AlphaFoldv4"
    },
    "Human": {
        "display_name": "Human",
        "base_path": "Human/AlphaFoldv4"
    },
    "Ecoli": {
        "display_name": "E. coli",
        "base_path": "Ecoli/AlphaFoldv4"
    }
}

# Entanglement result types
RESULT_TYPES = {
    "Native_GE": "Native_GE",
    "Native_HQ_GE": "Native_HQ_GE",
    "Native_clustered_HQ_GE": "Native_clustered_HQ_GE"
}


class ProteomeLoader:
    """Handles loading and caching of proteome-wide NCLE data"""
    
    def __init__(self):
        self.cache = {}
        self.cache_loaded = False
    
    def load_proteome_data(self, organism: str = "Yeast") -> List[Dict]:
        """
        Load all NCLE results for a given organism
        
        Parameters
        ----------
        organism : str
            Organism name (Yeast, Human, Ecoli)
            
        Returns
        -------
        List[Dict]
            List of protein records with aggregated entanglement info
            Example: {
                'protein_id': 'A0A023PYF4',
                'organism': 'Yeast',
                'num_entanglements': 2,
                'num_hq_entanglements': 1,
                'num_clustered_entanglements': 1,
                'chains': ['A'],
                'has_data': True
            }
        """
        if organism not in ORGANISMS:
            raise ValueError(f"Unknown organism: {organism}. Available: {list(ORGANISMS.keys())}")
        
        # Check cache
        cache_key = f"proteome_{organism}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        base_path = PROTEOME_DATA_BASE / ORGANISMS[organism]["base_path"]
        results_dir = base_path / "Native_GE"
        
        if not results_dir.exists():
            return []
        
        proteome_data = []
        
        # Iterate through all CSV files in Native_GE
        for csv_file in sorted(results_dir.glob("*.csv")):
            # Extract protein ID from filename like "A0A023PYF4_GE.csv" -> "A0A023PYF4"
            filename = csv_file.stem  # e.g., "A0A023PYF4_GE"
            protein_id = filename.replace("_GE", "")  # Remove "_GE" suffix
            record = self._parse_protein_file(csv_file, protein_id, organism, base_path)
            if record:
                proteome_data.append(record)
        
        # Cache the data
        self.cache[cache_key] = proteome_data
        return proteome_data
    
    def _parse_protein_file(self, csv_path: Path, protein_id: str, organism: str, base_path: Path) -> Optional[Dict]:
        """
        Parse a single protein CSV file to extract entanglement info
        
        Returns
        -------
        Dict or None
            Protein record or None if file is empty/header only
        """
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f, delimiter='|')
                rows = list(reader)
            
            if not rows:
                # File has only header
                return {
                    'protein_id': protein_id,
                    'organism': organism,
                    'num_entanglements': 0,
                    'num_hq_entanglements': 0,
                    'num_clustered_entanglements': 0,
                    'chains': [],
                    'has_data': False
                }
            
            # Count entanglements where ENT=True and collect chains
            chains = set()
            num_entanglements = 0
            for row in rows:
                if row:
                    if 'chain' in row:
                        chains.add(row['chain'])
                    # Count rows where ENT column is 'True'
                    if row.get('ENT', '').lower() == 'true':
                        num_entanglements += 1
            
            # Count HQ entanglements
            num_hq = self._count_hq_entanglements(protein_id, organism, base_path)
            
            # Count Clustered entanglements
            num_clustered = self._count_clustered_entanglements(protein_id, organism, base_path)
            
            return {
                'protein_id': protein_id,
                'organism': organism,
                'num_entanglements': num_entanglements,
                'num_hq_entanglements': num_hq,
                'num_clustered_entanglements': num_clustered,
                'chains': sorted(list(chains)),
                'has_data': num_entanglements > 0,
                'structure_path': f"{protein_id}.pdb"
            }
        
        except Exception as e:
            print(f"Error parsing {csv_path}: {e}")
            return None
    
    def _count_hq_entanglements(self, protein_id: str, organism: str, base_path: Path) -> int:
        """Count HQ entanglements where ENT=True for a protein"""
        hq_dir = base_path / "Native_HQ_GE"
        hq_file = hq_dir / f"{protein_id}.csv"
        
        if not hq_file.exists():
            return 0
        
        try:
            with open(hq_file, 'r') as f:
                reader = csv.DictReader(f, delimiter='|')
                count = sum(1 for row in reader if row and row.get('ENT', '').lower() == 'true')
            return count
        except:
            return 0
    
    def _count_clustered_entanglements(self, protein_id: str, organism: str, base_path: Path) -> int:
        """Count Clustered entanglements - all rows in the clustered file (no ENT column)"""
        clustered_dir = base_path / "Native_clustered_HQ_GE"
        clustered_file = clustered_dir / f"{protein_id}.csv"
        
        if not clustered_file.exists():
            return 0
        
        try:
            with open(clustered_file, 'r') as f:
                reader = csv.DictReader(f, delimiter='|')
                count = sum(1 for row in reader if row)
            return count
        except:
            return 0
    
    def get_protein_entanglements(self, protein_id: str, organism: str) -> List[Dict]:
        """Get Native_GE entanglement data for a protein"""
        if organism not in ORGANISMS:
            raise ValueError(f"Unknown organism: {organism}")
        
        csv_path = PROTEOME_DATA_BASE / ORGANISMS[organism]["base_path"] / "Native_GE" / f"{protein_id}_GE.csv"
        
        if not csv_path.exists():
            return []
        
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f, delimiter='|')
                rows = list(reader)
            
            # Filter out header-only entries
            return [row for row in rows if row and 'ID' in row]
        except Exception as e:
            print(f"Error reading {csv_path}: {e}")
            return []
    
    def get_hq_entanglements(self, protein_id: str, organism: str) -> List[Dict]:
        """Get Native_HQ_GE entanglement data for a protein"""
        if organism not in ORGANISMS:
            raise ValueError(f"Unknown organism: {organism}")
        
        csv_path = PROTEOME_DATA_BASE / ORGANISMS[organism]["base_path"] / "Native_HQ_GE" / f"{protein_id}.csv"
        
        if not csv_path.exists():
            return []
        
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f, delimiter='|')
                rows = list(reader)
            
            return [row for row in rows if row and 'ID' in row]
        except Exception as e:
            print(f"Error reading {csv_path}: {e}")
            return []
    
    def get_clustered_entanglements(self, protein_id: str, organism: str) -> List[Dict]:
        """Get Native_clustered_HQ_GE entanglement data for a protein"""
        if organism not in ORGANISMS:
            raise ValueError(f"Unknown organism: {organism}")
        
        csv_path = PROTEOME_DATA_BASE / ORGANISMS[organism]["base_path"] / "Native_clustered_HQ_GE" / f"{protein_id}.csv"
        
        if not csv_path.exists():
            return []
        
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f, delimiter='|')
                rows = list(reader)
            
            return [row for row in rows if row and 'ID' in row]
        except Exception as e:
            print(f"Error reading {csv_path}: {e}")
            return []
    
    def get_entanglement_features(self, protein_id: str, organism: str) -> List[Dict]:
        """Get Entanglement Features data for a protein"""
        if organism not in ORGANISMS:
            raise ValueError(f"Unknown organism: {organism}")
        
        # Features are stored with pattern: {protein_id}_*_uent_features.csv
        features_dir = PROTEOME_DATA_BASE / ORGANISMS[organism]["base_path"] / "Native_clustered_HQ_GE_features"
        
        if not features_dir.exists():
            return []
        
        features = []
        try:
            # Find all feature files for this protein
            for csv_file in features_dir.glob(f"{protein_id}_*_uent_features.csv"):
                with open(csv_file, 'r') as f:
                    reader = csv.DictReader(f, delimiter='|')
                    rows = list(reader)
                    features.extend([row for row in rows if row and 'ID' in row])
        except Exception as e:
            print(f"Error reading features for {protein_id}: {e}")
        
        return features
    
    def get_structure_path(self, protein_id: str) -> Optional[str]:
        """
        Get the full file path to a protein's PDB structure
        
        Parameters
        ----------
        protein_id : str
            UniProt ID
            
        Returns
        -------
        str or None
            Full path to PDB file or None if not found
        """
        pdb_path = PROTEIN_STRUCTURES_BASE / f"{protein_id}.pdb"
        
        if pdb_path.exists():
            return str(pdb_path)
        return None
    
    def get_available_organisms(self) -> List[Dict]:
        """
        Get list of available organisms with counts
        
        Returns
        -------
        List[Dict]
            {
                'organism': 'Yeast',
                'display_name': 'Yeast (S. cerevisiae)',
                'protein_count': 4239,
                'available': True
            }
        """
        organisms = []
        for org_key, org_config in ORGANISMS.items():
            org_path = PROTEOME_DATA_BASE / org_config["base_path"]
            available = org_path.exists()
            
            protein_count = 0
            if available:
                protein_count = len(list(org_path.glob("*.csv")))
            
            organisms.append({
                'organism': org_key,
                'display_name': org_config['display_name'],
                'protein_count': protein_count,
                'available': available
            })
        
        return organisms
    
    def search_proteins(self, query: str, organism: str = None) -> List[Dict]:
        """
        Search for proteins by ID
        
        Parameters
        ----------
        query : str
            Search query (protein ID or partial match)
        organism : str, optional
            Filter by organism
            
        Returns
        -------
        List[Dict]
            Matching protein records
        """
        query_lower = query.lower()
        results = []
        
        organisms_to_search = [organism] if organism else list(ORGANISMS.keys())
        
        for org in organisms_to_search:
            if org not in ORGANISMS:
                continue
            
            proteome_data = self.load_proteome_data(org)
            for record in proteome_data:
                if query_lower in record['protein_id'].lower():
                    results.append(record)
        
        return results[:100]  # Limit results


# Global loader instance
proteome_loader = ProteomeLoader()
