# NCLEdetector 2.0.0 Migration - API Compatibility Fixes

**Date**: 2025-07-21  
**Status**: ✅ COMPLETE - All API compatibility issues resolved and tested

## Summary

During the migration from legacy EntDetect to NCLEdetector 2.0.0 (PyPI), three API compatibility issues were discovered and fixed:

1. `select_high_quality_entanglements()` parameter renaming
2. `Cluster_NativeEntanglements()` parameter signature change  
3. `shutil` variable scoping bug in cleanup code

## Issue #1: select_high_quality_entanglements Parameter Change

### Error
```
GaussianEntanglement.select_high_quality_entanglements() got an unexpected keyword argument 'GE_filepath'
```

### Root Cause
NCLEdetector 2.0.0 renamed parameters for API consistency:
- `GE_filepath` → `rawNCLE_file`
- `pdb` → `pdb_file`

### Changes Made

**File: py/api_wrapper.py (Line 257-264)**
```python
# OLD (EntDetect)
hq_ent = ge.select_high_quality_entanglements(
    GE_filepath=native_ent['outfile'],
    pdb=pdb_path,
    ...
)

# NEW (NCLEdetector 2.0.0)
hq_ent = ge.select_high_quality_entanglements(
    rawNCLE_file=native_ent['outfile'],
    pdb_file=pdb_path,
    ...
)
```

**File: py/run_nativeNCLE.py (Line 89)**
- Updated to use named parameters for clarity

## Issue #2: Cluster_NativeEntanglements Parameter Change

### Error
```
ClusterNativeEntanglements.Cluster_NativeEntanglements() got an unexpected keyword argument 'GE_filepath'
```

### Root Cause
NCLEdetector 2.0.0 changed the clustering method signature:
- Old: Takes `GE_filepath` and `outfile` parameters
- New: Takes `HQ_NCLE_file`, `outdir`, `ID`, and `chain` parameters (auto-generates filename)

### Method Signature Comparison

**Old API (EntDetect)**
```python
Cluster_NativeEntanglements(
    GE_filepath="path/to/hq.csv",
    outfile="output_filename.csv"
)
```

**New API (NCLEdetector 2.0.0)**
```python
Cluster_NativeEntanglements(
    HQ_NCLE_file="path/to/hq.csv",
    outdir="output_directory",
    ID="cluster_id",
    chain="A"
)
```

### Changes Made

**File: py/api_wrapper.py (Lines 286-290)**
```python
# OLD
clustered_ent = clustering.Cluster_NativeEntanglements(
    GE_filepath=hq_ent['outfile'],
    outdir=clustered_temp_dir,
    outfile=f"{chain_id}_clustered.csv"
)

# NEW
clustered_ent = clustering.Cluster_NativeEntanglements(
    HQ_NCLE_file=hq_ent['outfile'],
    outdir=clustered_temp_dir,
    ID=chain_id,
    chain=chain if chain else None
)
```

**File: py/run_nativeNCLE.py (Line 93)**
- Updated to use new parameter names with named arguments

## Issue #3: shutil UnboundLocalError Bug

### Error
```
UnboundLocalError: cannot access local variable 'shutil' where it is not associated with a value
```

### Root Cause
Python has a scoping rule: if a variable is assigned anywhere in a function body (including nested scopes), Python treats it as a local variable throughout the ENTIRE function. When there were nested `import shutil` statements inside conditional blocks, this caused:

1. Module-level `import shutil` available at function scope
2. Nested `import shutil` inside conditional block treated shutil as local
3. Cleanup code tried to use `shutil.rmtree()` before the local import was reached
4. Python raised UnboundLocalError

### Affected Locations

**py/api_wrapper.py Line 421** (inside feature generation conditional):
```python
import shutil  # NESTED IMPORT - caused scoping issue
debug_csv_path = f"/tmp/debug_features_{chain if chain else 'default'}.csv"
shutil.copy(features_file, debug_csv_path)
```

**py/backend.py Line 474** (inside database storage function):
```python
import shutil  # NESTED IMPORT - caused scoping issue
shutil.copy2(temp_pdb_path, pdb_storage_path)
```

### Solution
Removed nested `import shutil` statements since `shutil` was already imported at module level:
- `py/api_wrapper.py` Line 8: `import shutil`
- `py/backend.py` Line 14: `import shutil`

The nested imports were redundant and caused Python to incorrectly treat `shutil` as a local variable throughout the entire function scope.

## Validation Results

### Test: Direct API Call
```bash
curl -X POST "http://127.0.0.1:8000/api/analyze" -F "file=@structure_files/1zmr.pdb"
```
✅ Result: 829 lines (1 header + 828 native GE results)

### Test: Job Submission
```bash
curl -X POST "http://127.0.0.1:8000/api/submit-job" \
  -F "file=@structure_files/1zmr.pdb" \
  -F "email=test@example.com" \
  -F "job_name=Test Job"
```
✅ Result: Job created with ID `92bf26b2-568a-4d4d-bad8-13cf0b0125c9`

### Test: Job Query
```bash
curl "http://127.0.0.1:8000/api/jobs/92bf26b2-568a-4d4d-bad8-13cf0b0125c9"
```
✅ Result:
- Status: completed
- Native GE: 828
- HQ GE: 50  
- Clustered GE: 4
- Database: ✅ Correctly stored and retrieved

### Test: Python Syntax
```bash
python3 -m py_compile py/api_wrapper.py py/backend.py py/run_nativeNCLE.py
```
✅ All files compile without errors

### Test: CLI Functionality
```bash
python py/run_nativeNCLE.py --struct structure_files/1zmr.pdb --outdir Testing/test_migration_v2 --ID 1zmr_test --organism Ecoli
```
✅ Result: Complete pipeline execution with all 4 stages:
- Native GE: 828 results
- Native HQ GE: 50 results
- Clustered Native HQ GE: 4 results
- Entanglement Features: 4 feature vectors generated

## API Compatibility Summary

| Component | Old (EntDetect) | New (NCLEdetector 2.0.0) | Status |
|-----------|-----------------|-------------------------|--------|
| GaussianEntanglement | ✓ | ✓ | ✅ Working |
| select_high_quality_entanglements | `GE_filepath`, `pdb` | `rawNCLE_file`, `pdb_file` | ✅ Fixed |
| ClusterNativeEntanglements | `GE_filepath`, `outfile` | `HQ_NCLE_file`, `outdir`, `ID` | ✅ Fixed |
| FeatureGen | Constructor params | Method params | ✅ Already fixed |
| Output format | Same | Same | ✅ Compatible |
| Database | No migration needed | No migration needed | ✅ Compatible |

## Next Steps

1. ✅ All API endpoints tested and working
2. ✅ Database persistence verified
3. ✅ CLI tool functional
4. Ready for: GitHub Pages deployment testing

## References

- [NCLEdetector 2.0.0 PyPI Package](https://pypi.org/project/NCLEdetector/)
- Migration Plan: [NCLEDETECTOR_MIGRATION_PLAN.md](NCLEDETECTOR_MIGRATION_PLAN.md)
- Implementation Report: [NCLEDETECTOR_MIGRATION_COMPLETE.md](NCLEDETECTOR_MIGRATION_COMPLETE.md)
