# Environment Debugging Summary - EntDetect Version Mismatch

## Problem Statement
Backend server was returning incorrect entanglement features despite ncle_prod conda environment containing the correct, fixed version of EntDetect. The raw GaussianEntanglement output was correct, but FeatureGen was corrupting the data.

**Symptoms:**
- Direct CLI execution: `python py/run_nativeNCLE.py` → **CORRECT** output (N_term=0, C_term=1, crossingsC=108)
- Backend API call: same file → **WRONG** output (N_term=1, C_term=0, crossingsC=8)

## Investigation Steps Completed

### 1. Environment Verification
- ✅ Confirmed ncle_prod has correct EntDetect (version 1.1.1 from PyPI)
- ✅ Verified source file contains "crossing_region_N" and "crossing_region_C"
- ✅ Confirmed gunicorn processes running from ncle_prod environment

### 2. File System Cleanup
- ✅ Removed duplicate EntDetect installations:
  - `/home/ianms/miniconda3/lib/python3.12/site-packages/EntDetect/` (old base Python)
  - `/home/ianms/envs/ncleweb/lib/python3.11/site-packages/EntDetect/` (old ncleweb env)
- ✅ Deleted entire venv directory
- ✅ Cleared all `__pycache__` directories
- ✅ Deleted all `.pyc` files from ncle_prod
- ✅ Cleared Python bytecode cache

### 3. Import Path Analysis
- ✅ Verified sys.path configuration
- ✅ Checked PYTHONPATH environment variables (none found)
- ✅ Looked for .pth files (only distutils-precedence.pth found - harmless)
- ✅ Verified backend.py and api_wrapper.py don't manipulate sys.path dangerously

### 4. Runtime Debugging
- ✅ Added logging to backend.py showing:
  - Correct Python executable: `/home/ianms/miniconda3/envs/ncle_prod/bin/python3.12`
  - Correct EntDetect path: `/home/ianms/miniconda3/envs/ncle_prod/lib/python3.12/site-packages/EntDetect/__init__.py`
- ✅ Added logging to api_wrapper.py showing:
  - FeatureGen class: `EntDetect.entanglement_features.FeatureGen`
  - FeatureGen source file: `/home/ianms/miniconda3/envs/ncle_prod/lib/python3.12/site-packages/EntDetect/entanglement_features.py`

### 5. Code Pattern Mismatch Found
- Found discrepancy in how FeatureGen is instantiated:
  - **run_nativeNCLE.py:** `FeatureGen(struct, outdir=..., cluster_file=...)`  (positional arg)
  - **api_wrapper.py:** `FeatureGen(PDBfile=analysis_pdb, outdir=..., cluster_file=...)` (keyword arg)
- Fixed to use positional argument matching the working CLI version

## Root Cause

**UNRESOLVED**: Despite all evidence pointing to the backend using the correct EntDetect source code and the correct Python environment, the backend continues to produce wrong output while the CLI produces correct output.

Possible remaining causes (speculative):
1. **Memory corruption or state persistence** - something in the process state from previous runs
2. **Dynamic code loading or monkey-patching** - some other module modifying EntDetect behavior at runtime
3. **Fork/spawn issue** - gunicorn workers inheriting corrupted state from master process
4. **Compiled extension issue** - native C extensions built from old code cached somewhere
5. **Module import order** - some dependency importing old EntDetect version indirectly

## Attempted Solutions

| Solution | Status | Result |
|----------|--------|--------|
| Recreate ncle_prod environment | ✅ | No change in behavior |
| Remove old venv directory | ✅ | No change |
| Delete all .pyc cache files | ✅ | No change |
| Delete base Python EntDetect copies | ✅ | No change |
| Clear Python bytecode | ✅ | No change |
| Verify sys.path | ✅ | No suspicious paths |
| Add runtime logging | ✅ | Shows correct imports |
| Fix FeatureGen call pattern | ✅ | No change (fix still valid) |

## Recommendation

**Deploy on completely fresh machine** with:
1. Fresh OS installation
2. Fresh Miniconda installation  
3. Fresh clone of repository
4. Fresh conda environment with descriptive name: `ncleweb_prod` (avoid reusing old names)
5. Pin all dependency versions explicitly

This will eliminate any possibility of leftover cached files, environment pollution, or system state issues.

## Notes for Fresh Deployment

When deploying on a new machine:
- Use the deployment guide in `DEPLOYMENT_FRESH_MACHINE.md`
- Name the environment `ncleweb_prod` (use a different name than existing deployments)
- Verify NO old EntDetect copies exist before starting
- Test CLI execution first (`run_nativeNCLE.py`)
- Only start backend after CLI test succeeds
- Check logs: `logs/feature_generation.log` to verify FeatureGen source file path

## Files Modified

- `py/backend.py` - Added debug logging for EntDetect import
- `py/api_wrapper.py` - Fixed FeatureGen instantiation, added debug logging
- `start_server.sh` - Updated to use ncle_prod environment explicitly
- `DEPLOYMENT_FRESH_MACHINE.md` - New deployment guide (created)

## Commits

- `107432c` - Remove venv completely, production now uses ncle_prod conda environment only
- `ceebe7f` - Fix FeatureGen call to use positional argument matching run_nativeNCLE.py, add debug logging
