# NCLEweb — Requirements for Hosting on Penn State ROAR

Reference doc for discussion with the HPC/ROAR support team about migrating
NCLEweb (https://ncleweb.org) from a home server to ROAR.

## What NCLEweb Is

A web application that lets users upload PDB protein structures and runs
Gaussian Entanglement analysis (via the `NCLEdetector`/`topoly` Python
packages) to detect non-covalent lasso entanglements. Users submit jobs
through a browser, the backend processes them asynchronously, and results
(JSON + structure files) are served back for visualization (NGL viewer) and
download. Jobs can take seconds to minutes depending on structure size and
batch size.

## Architecture Summary

- **Frontend**: static HTML/CSS/JS (no build step), served as static files.
- **Backend**: Python FastAPI app (`py/backend.py`), run with Gunicorn +
  Uvicorn workers (currently `-w 4`, `uvicorn.workers.UvicornWorker`).
- **Reverse proxy**: Nginx terminates TLS, serves static files, proxies
  `/api/` to the backend on `127.0.0.1:8000`, and serves `/data/` (results,
  uploaded/processed PDB files) directly from disk.
- **Database**: SQLite (file-based, `data/ncle.db`), no external DB server.
- **Job processing**: in-process priority queue (`py/job_queue.py`) with
  background worker threads — small jobs (<100 KB) run with high priority,
  large/batch jobs run with limited concurrency (1 large job at a time,
  up to 4 small jobs concurrently). This is **not** currently integrated
  with a cluster scheduler (e.g., Slurm) — jobs run as local
  threads/processes on the same host serving the web app.
- **Email**: outbound SMTP for job-completion notifications (currently
  Gmail SMTP, configured via `.env`).

## Core Software/Runtime Requirements

- **OS**: Linux (developed/tested on Ubuntu).
- **Python**: 3.10+ (currently running 3.12).
- **Python environment**: conda (currently uses a conda `base` environment)
  or venv — needs ability to install packages, including ones with
  compiled extensions.
- **Key Python packages** (see `requirements.txt`):
  - `fastapi`, `uvicorn`, `gunicorn`
  - `pandas`, `numpy`, `scipy`
  - `biopython`, `MDAnalysis`
  - `topoly` — has compiled (C/C++/Fortran) extensions; may need a
    build toolchain (gcc/g++/gfortran) available at install time.
  - `NCLEdetector` (custom package, installed via pip/PyPI or git)
  - `sqlalchemy`, `python-multipart`
- **Nginx** (or equivalent reverse proxy) for TLS termination, static file
  serving, and request routing — or ROAR's standard web-hosting/proxy
  solution if different.
- **Outbound network access** on port 587 (SMTP) for email notifications
  — needs to be confirmed/allowed, or notifications disabled.
- **Inbound network access** on 80/443 (or whatever ROAR's standard
  web-facing port scheme is) reachable from the public internet, since
  this is a public-facing lab tool (ncleweb.org), not just intra-cluster.

## Resource/Storage Requirements

- **Compute**: modest — current deployment runs fine on 1 CPU/1GB class VM
  for low traffic, but concurrent job processing benefits from multiple
  cores (currently 4 Gunicorn workers + a few background job threads).
  No GPU needed.
- **Storage**: currently ~190 MB of data (SQLite DB ~18 MB, uploaded/
  processed PDB structure files ~110 MB) and growing with usage — need
  persistent disk storage that survives restarts/redeploys (not ephemeral/
  scratch storage that gets purged), since results and the job database
  must remain available for users to browse/download later.
- **Long-running process**: the backend must run continuously (not just
  as a batch/Slurm job) since it needs to always be listening for incoming
  HTTP requests — this is the main point to clarify with ROAR, since
  traditional HPC is oriented around scheduled batch jobs rather than
  always-on web services.
- **File uploads**: max upload size currently capped at 60 MB (Nginx
  `client_max_body_size`) for PDB files.

## Key Questions/Topics for the HPC Rep

1. **Does ROAR support always-on web services**, or is everything run
   as scheduled batch jobs (Slurm)? If only batch-oriented, we'd need an
   alternative (e.g., a persistent VM, a dedicated "services" node, or a
   container platform) rather than standard ROAR compute queues.
2. **Public internet exposure**: can ROAR host a service reachable at a
   custom domain (ncleweb.org) over HTTPS, or does it sit behind PSU's
   network/VPN only? We need public access since this is a community-
   facing tool.
3. **Persistent storage**: availability of a persistent (non-scratch)
   storage allocation for the SQLite database and uploaded/result files,
   with normal backup policies.
4. **Process management**: can we run a long-lived Gunicorn/Uvicorn
   process (optionally under systemd or a container), and is there a
   reverse proxy (Nginx or ROAR-managed) available, or do we need to
   bring/manage our own?
5. **Outbound SMTP**: is outbound port 587 allowed for email notifications,
   or do we need to use a PSU-approved mail relay?
6. **Containers**: is Docker/Singularity/Apptainer supported? Containerizing
   the app (Python env + Nginx) may be the cleanest path to make this
   portable to ROAR's environment.
7. **Compiled dependency support**: ability to install Python packages
   with native extensions (`topoly`, `MDAnalysis`) — do we need a build
   toolchain, or should we pre-build/containerize to avoid compiling on
   the cluster?
8. **DNS/TLS**: process for pointing ncleweb.org at a ROAR-hosted
   address and obtaining/renewing a TLS certificate (currently Let's
   Encrypt via certbot).
9. **Resource quotas**: CPU/RAM/disk quota for this kind of long-running
   low-to-moderate-traffic web service, and whether it counts against the
   lab's regular HPC allocation or a separate "hosting" allocation.
10. **Monitoring/restart policy**: how service crashes/restarts are
    handled (e.g., is there a systemd-like mechanism, or do we need our
    own watchdog/cron).

## Suggested Migration Approach

Given it's a lab web app rather than a batch computation, containerizing
the whole stack (Python backend + Nginx, with a persistent volume for
`data/`) would likely be the most portable option, if ROAR supports
running containers as persistent services. This avoids rebuilding the
conda/pip environment (including `topoly`'s compiled extensions) on
ROAR's infrastructure directly.
