# NCLEweb Deployment on Fresh Machine

This guide is for deploying NCLEweb on a completely fresh machine to avoid environment conflicts.

## Prerequisites

- Linux system (tested on Ubuntu/Debian)
- Miniconda or Anaconda installed
- Git installed
- At least 10GB free disk space

## Step 1: Clone Repository

```bash
cd /home/user
git clone <repository-url>
cd NCLEweb
```

## Step 2: Create Fresh Conda Environment

**CRITICAL:** Do NOT use any existing conda environments. Create a completely fresh one named `ncleweb_prod`:

```bash
# Remove any old environments first (if they exist)
conda env remove -n ncleweb_prod

# Create fresh environment with Python 3.12
conda create -n ncleweb_prod python=3.12 -y

# Activate the environment
conda activate ncleweb_prod
```

## Step 3: Install Dependencies

Install all requirements in the EXACT order specified:

```bash
# Core scientific packages
conda install -c conda-forge numpy scipy pandas -y

# Bioinformatics
conda install -c conda-forge biopython mdanalysis -y

# Web framework
pip install fastapi uvicorn gunicorn
pip install python-multipart

# Database
# SQLite is built-in, no installation needed

# CRITICAL: Install NCLEdetector fresh from PyPI
pip install NCLEdetector

# Verify NCLEdetector installation
python -c "from NCLEdetector.entanglement_features import FeatureGen; print('✓ NCLEdetector ready')"
```

## Step 4: Verify No Old EntDetect Copies

```bash
# Check ONLY one copy of EntDetect exists
find $CONDA_PREFIX -name "entanglement_features.py" | wc -l
# Should output: 1

# Verify it's in the correct location
find $CONDA_PREFIX -name "entanglement_features.py"
# Should be: $CONDA_PREFIX/lib/python3.12/site-packages/EntDetect/entanglement_features.py
```

## Step 5: Update start_server.sh

Edit `start_server.sh` and update the gunicorn path to use the new environment name:

```bash
# OLD (don't use):
# /home/user/miniconda3/envs/ncle_prod/bin/gunicorn

# NEW (use this):
/home/user/miniconda3/envs/ncleweb_prod/bin/gunicorn
```

Or use:
```bash
conda activate ncleweb_prod
which gunicorn  # This will give you the full path to use
```

## Step 6: Test Directly with ncleweb_prod

```bash
conda activate ncleweb_prod
python py/run_nativeNCLE.py \
  --struct structure_files/1zmr_model_clean_ca.pdb \
  --outdir Testing/direct_ncleweb_prod_test/ \
  --ID 1zmr_model_clean_ca \
  --organism Ecoli \
  --cg --Calpha \
  --model EXP \
  --ent_detection_method 3
```

Check the output file:
```bash
head -2 Testing/direct_ncleweb_prod_test/Native_clustered_HQ_GE_features/P00558_1zmr_model_clean_ca_A_uent_features.csv
# Should show: N_term_thread=0, C_term_thread=1, crossingsC=108 for row 0
```

## Step 7: Start Backend Server

```bash
cd /home/user/NCLEweb
bash start_server.sh
```

Verify it's running:
```bash
ps aux | grep gunicorn
# Should show 5 processes (1 master + 4 workers) from ncleweb_prod
```

## Step 8: Test Backend API

```bash
curl -X POST http://localhost:8000/api/submit-job \
  -F "file=@structure_files/1zmr_model_clean_ca.pdb" \
  -F "identifier=test_1zmr" \
  -F "organism=Ecoli" \
  -F "email=test@example.com" \
  -F "coarse_grained=true" \
  -F "ca_contact=true" \
  -F "structure_type=EXP" \
  -F "ent_detection_method=3"
```

Wait for job to complete (~30-60 seconds), then check the output in the database or results files.

## Troubleshooting

### If you see "No module named 'EntDetect'"
- Make sure you're in the ncleweb_prod environment: `conda activate ncleweb_prod`
- Reinstall: `pip install entdetect`

### If output is still wrong
- Verify no other EntDetect copies exist: `find / -name "entanglement_features.py" 2>/dev/null`
- Delete any found except the one in ncleweb_prod site-packages
- Clear Python cache: `find $CONDA_PREFIX -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null`
- Restart server: `pkill -f gunicorn; bash start_server.sh`

### If you still see old behavior
- Check which Python the gunicorn is using: `ps aux | grep gunicorn | grep -v grep`
- The path must show ncleweb_prod, NOT ncle_prod or any other environment

## Production Notes

- Use a proper WSGI server (gunicorn as configured)
- Set up reverse proxy with nginx or Apache
- Use systemd service for automatic startup
- Configure proper logging and monitoring
- Set up SSL/TLS certificates
- Use environment variables for sensitive config (SMTP password, etc.)

See `deploy/` directory for production deployment scripts.
