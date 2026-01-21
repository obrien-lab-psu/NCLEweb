# EntDetect Update - NCLEweb Integration Test Results

**Date:** January 20, 2026  
**Test Structure:** AF-Q9U2G8-F1-model_v6.pdb (AlphaFold model)  
**EntDetect Version:** Commit 65f3c02 (latest with AF bug fix)

## Test Summary

✅ **PASSED** - All tests successful

### EntDetect Reinstallation
- Successfully uninstalled old version
- Installed latest version from GitHub with AF model bug fixes
- Commit: 65f3c02030c06b237341efdd820a621037b56d9f

### Standalone Script Test (run_nativeNCLE.py)
**Command:**
```bash
python py/run_nativeNCLE.py \
  --struct structure_files/AF-Q9U2G8-F1-model_v6.pdb \
  --outdir TestingGrounds/AF_test/ \
  --ID AF-Q9U2G8 \
  --organism Ecoli \
  --model AF
```

**Results:**
- Native_GE: **984 entanglements**
- Native_HQ_GE: **134 high-quality entanglements** (with Quality/Reason columns)
- Native_clustered_HQ_GE: **6 clustered entanglements**
- Processing time: ~10.4 seconds
- Status: ✅ SUCCESS - All intermediate files created with harmonized pipe-delimited format

**Key Observation:** AF-specific filtering now working correctly, showing:
- "High" quality: NC and Crossings pLDDT >= 70
- "Low" quality: NC pLDDT < 70

### Web Application Test (Backend API)
**Test Job:**
- Job ID: bd6213a4-ffce-4fee-a4e0-a6da64fec417
- Structure Type: AF (AlphaFold)
- Organism: E. coli
- Clustering: Default (cutoff=57)

**API Submission:**
```bash
curl -X POST http://127.0.0.1:8001/api/submit-job \
  -F "file=@structure_files/AF-Q9U2G8-F1-model_v6.pdb" \
  -F "email=test@example.com" \
  -F "job_name=AF Test - Q9U2G8" \
  -F "structure_type=AF" \
  -F "organism=Ecoli"
```

**Results:**
- Job submission: ✅ SUCCESS
- Background processing: ✅ COMPLETED
- Database storage: ✅ VERIFIED
- PDB file saved: ✅ /data/pdb_files/{job_id}/structure.pdb
- Email notification: ✅ SENT

**Analysis Results (from API):**
- Native_GE: **984 entanglements** ✓
- Native_HQ_GE: **134 high-quality entanglements** ✓
- Native_clustered_HQ_GE: **6 clustered results** ✓

**Clustered Results Schema:**
```json
{
  "ID": "tmp6apxgk8h",
  "chain": "A",
  "i": 27,
  "j": 99,
  "crossingsN": "",
  "crossingsC": "-106,+131,-140",
  "gn": -0.09164,
  "gc": -0.80653,
  "GLNn": 0,
  "GLNc": -1,
  "TLNn": 0,
  "TLNc": -1,
  "num_contacts": 3,
  "contacts": "24-99;27-99;73-94",
  "CCBond": false
}
```

## Verification Checklist

- [x] EntDetect updated to latest version with AF bug fix
- [x] Standalone script (run_nativeNCLE.py) works with --model AF
- [x] Native_GE generates complete results
- [x] Native_HQ_GE applies AF-specific pLDDT filtering correctly
- [x] Native_clustered_HQ_GE produces clustered results with full schema
- [x] Web backend accepts structure_type parameter
- [x] API passes model type to EntDetect correctly
- [x] Background job processing completes successfully
- [x] Results stored in database with correct counts
- [x] PDB file saved to job directory
- [x] Email notifications sent
- [x] Clustered results include num_contacts and contacts fields

## Conclusion

The NCLEweb application is **fully compatible** with the updated EntDetect library. The AF model bug fix is working correctly, and all three analysis stages (Native_GE, Native_HQ_GE, Native_clustered_HQ_GE) produce expected results with the proper schema.

### Next Steps
- Compare results with ground truth data
- Test with additional AlphaFold structures
- Deploy to production server
