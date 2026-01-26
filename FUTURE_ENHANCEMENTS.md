# Future Enhancements for NCLE Web

This document tracks planned features and improvements for the NCLE Web application.

## High Priority

### 1. Entanglement Feature Calculation
**Description**: Integrate EntDetect's feature generation capabilities to provide quantitative metrics for each entanglement.

**Implementation**:
- Use `from EntDetect.entanglement_features import FeatureGen` 
- Calculate features for Native_GE, Native_HQ_GE, and Native_clustered_HQ_GE results
- Add new database tables for storing features:
  - `entanglement_features` table with columns for all feature types
  - Link to parent entanglement via foreign key
- Update API endpoints to return features alongside entanglement data
- Add feature visualization in results page (charts, distributions)
- Enable feature-based filtering and sorting in results tables

**Benefits**:
- Provides deeper analysis of entanglement characteristics
- Enables comparative analysis across different structures
- Supports machine learning applications downstream

**References**:
- EntDetect FeatureGen documentation
- Example usage in EntDetect repository

---

### 2. AlphaFold Database Integration
**Description**: Add ability to directly query and analyze structures from the AlphaFold Protein Structure Database, similar to current RCSB PDB integration.

**Implementation**:
- Add "AlphaFold Database ID" input option in submission form
- Integrate with AlphaFold Database API: https://alphafold.ebi.ac.uk/api/
- Query endpoint: `https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-model_v{version}.pdb`
- Auto-detect UniProt IDs and fetch latest AlphaFold structure version
- Add AF database metadata to job records:
  - AlphaFold DB ID (e.g., AF-P34158-F1)
  - Model version (v1, v2, v3, v4, v6)
  - pLDDT scores (if available)
- Automatically set structure_type='AF' for AF database submissions
- Auto-enable C-alpha contacts for AF structures

**Benefits**:
- Seamless access to 200M+ AlphaFold predicted structures
- No need to manually download and upload files
- Consistent handling of AlphaFold models (auto C-alpha mode)
- Faster submission workflow for users

**Technical Notes**:
- Similar implementation to existing RCSB PDB ID handler
- Use `alphafold_db_id` field in jobs table
- Download PDB from AlphaFold API in backend
- Cache downloaded structures same as RCSB structures

**References**:
- AlphaFold Database API docs: https://alphafold.ebi.ac.uk/api-docs
- UniProt integration for ID validation

---

## Medium Priority

### 3. Batch Processing
**Description**: Allow users to submit multiple structures at once for analysis.

**Implementation Ideas**:
- Multi-file upload support
- CSV/text file with list of PDB IDs
- Batch job queue with progress tracking
- Results dashboard for batch jobs

---

### 4. Structure Comparison
**Description**: Enable side-by-side comparison of entanglements across different structures or conditions.

**Implementation Ideas**:
- Select 2+ jobs for comparison
- Visual diff of entanglement patterns
- Statistical comparison metrics
- Export comparison reports

---

### 5. Advanced Visualization
**Description**: Enhanced 3D visualization of entanglements in NGL viewer.

**Implementation Ideas**:
- Highlight entanglement loops in different colors
- Animate threading path
- Interactive selection of entanglements to visualize
- Export high-quality images/videos

---

### 6. User Accounts and History
**Description**: Allow users to create accounts and track their analysis history.

**Implementation Ideas**:
- Authentication system (OAuth, email/password)
- Personal dashboard with job history
- Save favorite analyses
- Share results via unique URLs
- Organize jobs into projects/folders

---

## Low Priority

### 7. API Rate Limiting Refinement
**Description**: More sophisticated rate limiting based on user type, resource usage, etc.

---

### 8. Result Caching and Deduplication
**Description**: Cache results for commonly analyzed structures to speed up duplicate submissions.

---

### 9. Email Digest Reports
**Description**: Send periodic summary emails with completed jobs and statistics.

---

### 10. Mobile-Responsive UI
**Description**: Optimize interface for mobile devices and tablets.

---

## Completed Enhancements

### ✅ Entanglement Detection Methods (v0.2.0)
- Implemented 3 detection methods (GLN, TLN, Consensus)
- Added UI for method selection
- Database schema updated

### ✅ AlphaFold Structure Auto-Detection
- Auto-enables C-alpha contacts for AF structures
- Reduces memory usage for large structures
- Matches command-line script behavior

### ✅ Background Job Processing
- ThreadPoolExecutor for compute offloading
- asyncio for non-blocking execution
- Prevents worker timeouts

### ✅ RCSB PDB ID Direct Query
- Submit jobs using PDB IDs without file upload
- Automatic download from RCSB database
- Structure validation and preprocessing

---

## Contributing

Have ideas for new features? Please submit them via:
- GitHub Issues
- Email: [your contact]
- Discussion forum: [if applicable]

---

Last Updated: January 26, 2026
