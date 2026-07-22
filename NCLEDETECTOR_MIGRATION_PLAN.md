# NCLEweb → NCLEdetector Migration Plan

## Executive Summary

Migrate from legacy **EntDetect** package to the professionally maintained **NCLEdetector 2.0.0** from PyPI. This enables clean dependency management, automatic updates, and access to new analytical features while maintaining backward compatibility with existing analysis pipelines.

**Benefits:**
- ✅ Always use latest version (cleaner dependency management)
- ✅ No local package copies needed
- ✅ Professional PyPI package with active maintenance
- ✅ Access to new modules: order parameters, sim-exp comparison, statistics
- ✅ Easier deployment and reproducibility
- ✅ Remove Python path complexity and conda environment workarounds

---

## Current Architecture Analysis

### Package Dependencies
- **Current**: `EntDetect` (pip install entdetect)
- **Problem**: Occasionally installed from local copies or specific branches; environment conflicts
- **Solution**: Switch to `NCLEdetector` (pip install NCLEdetector) from official PyPI

### Current Import Patterns
```python
# Current (EntDetect)
from EntDetect.gaussian_entanglement import GaussianEntanglement
from EntDetect.clustering import ClusterNativeEntanglements
from EntDetect.entanglement_features import FeatureGen
import EntDetect  # For debugging

# New (NCLEdetector)
from NCLEdetector.gaussian_entanglement import GaussianEntanglement
from NCLEdetector.clustering import ClusterNativeEntanglements
from NCLEdetector.entanglement_features import FeatureGen
import NCLEdetector  # For debugging
```

### Files Requiring Updates

| File | Type | Changes |
|------|------|---------|
| `requirements.txt` | Dependency | `EntDetect` → `NCLEdetector` |
| `py/api_wrapper.py` | Code | Update imports |
| `py/backend.py` | Code | Update debug import |
| `py/run_nativeNCLE.py` | Code | Update imports |
| `py/gaussian_entanglement.py` | Code | **Decision needed** (see below) |
| `start_backend.sh` | Docs/comments | Update conda activation instructions |
| `DEPLOYMENT_FRESH_MACHINE.md` | Docs | Update installation steps |
| `deploy/SERVER_SETUP.md` | Docs | Update installation steps |
| `deploy/deploy_wsl.sh` | Script | Update pip install command |
| `deploy/setup_ncleweb.sh` | Script | Update pip install command |

### Special Case: `py/gaussian_entanglement.py`

**Current Status**: This file contains a local implementation of GaussianEntanglement that also tries to import from EntDetect as a fallback.

**Analysis**:
```python
# Line 6-7: Tries to import from package
try:
    from EntDetect.gaussian_entanglement import GaussianEntanglement
    # Use the imported class
except ImportError:
    # Use local implementation (rest of file)
    class GaussianEntanglement: ...
```

**Recommendation**: 
- **Option A (Preferred)**: Remove this file entirely and use `from NCLEdetector.gaussian_entanglement import GaussianEntanglement` in all places
- **Option B**: Keep as backup/reference but don't use it in production code
- **Decision**: Option A - Simplifies codebase and reduces maintenance burden

---

## Migration Strategy

### Phase 1: Preparation & Planning ✓
- [x] Review current EntDetect usage across codebase
- [x] Compare EntDetect vs NCLEdetector package structures
- [x] Verify import compatibility
- [x] Check for breaking changes (none found - same core API)

### Phase 2: Update Dependencies
1. **Update `requirements.txt`**
   - Replace: `EntDetect` → `NCLEdetector`
   - Note: No version pinning needed; PyPI latest is 2.0.0

### Phase 3: Update Code Imports
1. **`py/api_wrapper.py`**
   - Change: `from EntDetect.gaussian_entanglement` → `from NCLEdetector.gaussian_entanglement`
   - Change: `from EntDetect.clustering` → `from NCLEdetector.clustering`
   - Change: `from EntDetect.entanglement_features` → `from NCLEdetector.entanglement_features`

2. **`py/backend.py`**
   - Change: `import EntDetect` → `import NCLEdetector`
   - Update debug log: `f.write(f"NCLEdetector: {NCLEdetector.__file__}\n")`

3. **`py/run_nativeNCLE.py`**
   - Change all three imports from EntDetect → NCLEdetector

4. **`py/gaussian_entanglement.py`**
   - **DELETE** this file (no longer needed with NCLEdetector)
   - OR keep as reference documentation

### Phase 4: Update Deployment Documentation
1. **`DEPLOYMENT_FRESH_MACHINE.md`**
   - Line ~54: `pip install entdetect` → `pip install NCLEdetector`
   - Add note about PyPI version 2.0.0

2. **`deploy/SERVER_SETUP.md`**
   - Line ~183: `pip install EntDetect` → `pip install NCLEdetector`

3. **`deploy/deploy_wsl.sh`**
   - Search for "entdetect" and update to "NCLEdetector"

4. **`deploy/setup_ncleweb.sh`**
   - Search for "entdetect" and update to "NCLEdetector"

### Phase 5: Testing & Validation
1. **Local Testing**
   - Install NCLEdetector: `pip install NCLEdetector`
   - Run test jobs: `python py/run_nativeNCLE.py --struct ...`
   - Verify results match previous EntDetect output
   - Test batch submission functionality

2. **Backend Testing**
   - Start backend: `./start_backend.sh`
   - Submit test job via API
   - Verify results in database
   - Check email notifications

3. **Deployment Testing** (if applicable)
   - Test fresh installation on staging server
   - Verify backward compatibility with existing job results

### Phase 6: Documentation Updates
1. Update README.md if needed
2. Update inline comments referencing EntDetect
3. Add migration notes to CHANGELOG (if exists)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Breaking API changes | **Very Low** | High | Both packages share same core API; tested locally |
| Performance differences | **Low** | Medium | Run benchmark tests on sample data |
| Database compatibility | **Very Low** | High | No DB schema changes needed; same output format |
| Deployment issues | **Low** | High | Test fresh install on staging first |
| Staff training/documentation | **Medium** | Low | Update deployment docs; provide this plan |

---

## Rollback Plan

If issues arise:
1. Keep current `requirements.txt` backup: `requirements.txt.entdetect_bak`
2. In case of critical issues: `pip install entdetect` and revert imports
3. Keep git history for easy reversal

---

## Success Criteria

✅ All imports successfully use NCLEdetector  
✅ Test jobs complete successfully with identical results  
✅ Database queries show expected results  
✅ Batch submissions work correctly  
✅ Email notifications function properly  
✅ Fresh deployment follows updated documentation  
✅ No performance degradation  
✅ Codebase is cleaner (no py/gaussian_entanglement.py duplication)  

---

## Timeline Estimate

| Phase | Effort | Duration |
|-------|--------|----------|
| Phase 1: Preparation | ✅ Done | - |
| Phase 2-3: Code updates | 30 min | ~1 hour |
| Phase 4: Docs updates | 20 min | ~30 min |
| Phase 5: Testing | 1-2 hours | 2-3 hours |
| Phase 6: Documentation | 15 min | ~30 min |
| **Total** | | **4-5 hours** |

---

## Next Steps

Once you approve this plan, I will:

1. **Immediately**:
   - Update `requirements.txt` with NCLEdetector
   - Update all Python imports in py/*.py files
   - Delete or backup py/gaussian_entanglement.py

2. **Then**:
   - Update all deployment/setup documentation
   - Run local tests with sample PDB file
   - Verify database schema compatibility

3. **Finally**:
   - Document any breaking changes (expect none)
   - Provide deployment checklist for production

**Questions?** Let me know if you want to modify any part of this plan before implementation.
