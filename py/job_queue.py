#!/usr/bin/env python3
"""
Job Queue Manager for NCLE Web Application

Implements a priority-based queuing system that allows small jobs to run
alongside large jobs, preventing small submissions from being starved.

Queue Strategy:
- Priority Levels: 0 (high) to 2 (low)
- Max concurrent: 1 large job OR up to 4 small jobs
- Job size: < 100 KB = small, >= 100 KB = large
"""

import threading
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import IntEnum
import logging

logger = logging.getLogger(__name__)


class JobPriority(IntEnum):
    """Priority levels for job queuing"""
    SINGLE_SMALL = 0   # Single small file (< 100 KB) - highest priority
    SINGLE_LARGE = 1   # Single large file (>= 100 KB) - medium priority
    BATCH = 2          # Batch submission (multiple files) - lowest priority


class JobSize(IntEnum):
    """Job size classification"""
    SMALL = 0      # < 100 KB
    LARGE = 1      # >= 100 KB


@dataclass
class QueuedJob:
    """Represents a job in the queue"""
    job_id: str
    batch_id: Optional[str]  # None for single jobs, UUID for batch jobs
    estimated_size: int  # File size in bytes
    priority: JobPriority
    
    def __lt__(self, other):
        """Compare jobs for priority queue ordering"""
        # Lower priority value = higher priority (processed first)
        # Within same priority, smaller files first
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.estimated_size < other.estimated_size


class JobQueueManager:
    """
    Manages job queue with priority-based scheduling.
    
    Ensures that:
    - Small jobs don't starve while large jobs process
    - Resources are allocated efficiently
    - Batch jobs are queued appropriately
    """
    
    # Configuration
    MAX_TOTAL_SLOTS = 4           # Total worker slots
    SIZE_THRESHOLD_BYTES = 100 * 1024  # 100 KB threshold for small/large
    MAX_SMALL_CONCURRENT = 4      # Max small jobs running simultaneously
    MAX_LARGE_CONCURRENT = 1      # Max large jobs running simultaneously
    
    def __init__(self):
        """Initialize the queue manager"""
        self.queue: List[QueuedJob] = []  # Sorted by priority
        self.running_jobs: Dict[str, QueuedJob] = {}  # Currently running jobs
        self.lock = threading.RLock()
    
    def enqueue_job(self, job_id: str, file_size: int, batch_id: Optional[str] = None) -> Tuple[JobPriority, int]:
        """
        Add a job to the queue.
        
        Parameters
        ----------
        job_id : str
            Unique job identifier
        file_size : int
            Estimated file size in bytes
        batch_id : str, optional
            Batch ID if part of a batch submission
            
        Returns
        -------
        tuple
            (priority_level, queue_position)
        """
        with self.lock:
            # Determine priority and size
            is_small = file_size < self.SIZE_THRESHOLD_BYTES
            is_batch = batch_id is not None
            
            if is_batch:
                priority = JobPriority.BATCH
            elif is_small:
                priority = JobPriority.SINGLE_SMALL
            else:
                priority = JobPriority.SINGLE_LARGE
            
            # Create queued job
            queued_job = QueuedJob(
                job_id=job_id,
                batch_id=batch_id,
                estimated_size=file_size,
                priority=priority
            )
            
            # Insert into queue maintaining sorted order
            self.queue.append(queued_job)
            self.queue.sort()
            
            # Find position in queue
            position = next(i for i, job in enumerate(self.queue) if job.job_id == job_id)
            
            logger.info(f"Job {job_id} enqueued with priority {priority.name} at position {position}")
            return (priority, position)
    
    def dequeue_job(self, job_id: str) -> Optional[QueuedJob]:
        """
        Remove a job from the queue and add to running.
        Only call this when a worker is ready to process the job.
        
        Parameters
        ----------
        job_id : str
            Job ID to dequeue
            
        Returns
        -------
        QueuedJob or None
            The dequeued job, or None if not found
        """
        with self.lock:
            # Find and remove from queue
            job = None
            for i, q_job in enumerate(self.queue):
                if q_job.job_id == job_id:
                    job = self.queue.pop(i)
                    break
            
            if job:
                self.running_jobs[job_id] = job
                logger.info(f"Job {job_id} started processing")
            
            return job
    
    def finish_job(self, job_id: str) -> Optional[QueuedJob]:
        """
        Mark a job as finished and remove from running.
        
        Parameters
        ----------
        job_id : str
            Job ID that finished
            
        Returns
        -------
        QueuedJob or None
            The finished job, or None if not found
        """
        with self.lock:
            job = self.running_jobs.pop(job_id, None)
            if job:
                logger.info(f"Job {job_id} finished processing")
            return job
    
    def get_next_runnable_job(self) -> Optional[str]:
        """
        Get the next job that can run based on current resource constraints.
        
        Returns the job_id of the next job to process, or None if no resources
        are available or queue is empty.
        
        Returns
        -------
        str or None
            Job ID of next runnable job, or None
        """
        with self.lock:
            if not self.queue:
                return None
            
            # Count running jobs by size
            small_running = sum(
                1 for job in self.running_jobs.values()
                if job.estimated_size < self.SIZE_THRESHOLD_BYTES
            )
            large_running = sum(
                1 for job in self.running_jobs.values()
                if job.estimated_size >= self.SIZE_THRESHOLD_BYTES
            )
            
            total_slots_used = small_running + large_running
            
            # Find first runnable job
            for job in self.queue:
                is_small = job.estimated_size < self.SIZE_THRESHOLD_BYTES
                
                if is_small:
                    # Can run small jobs if slots available and no large jobs running
                    if small_running < self.MAX_SMALL_CONCURRENT and large_running == 0:
                        return job.job_id
                else:
                    # Can run large jobs if no other jobs running
                    if total_slots_used == 0:
                        return job.job_id
            
            return None
    
    def get_queue_status(self) -> Dict:
        """
        Get current queue status.
        
        Returns
        -------
        dict
            Queue statistics including pending, running, and resource usage
        """
        with self.lock:
            small_running = sum(
                1 for job in self.running_jobs.values()
                if job.estimated_size < self.SIZE_THRESHOLD_BYTES
            )
            large_running = sum(
                1 for job in self.running_jobs.values()
                if job.estimated_size >= self.SIZE_THRESHOLD_BYTES
            )
            
            return {
                'queue_length': len(self.queue),
                'running_jobs': len(self.running_jobs),
                'small_jobs_running': small_running,
                'large_jobs_running': large_running,
                'total_slots_used': small_running + large_running,
                'total_slots': self.MAX_TOTAL_SLOTS
            }
    
    def get_job_queue_position(self, job_id: str) -> Optional[int]:
        """
        Get the position of a job in the queue (0 = first to run).
        
        Parameters
        ----------
        job_id : str
            Job ID to find
            
        Returns
        -------
        int or None
            Position in queue, or None if not in queue
        """
        with self.lock:
            for i, job in enumerate(self.queue):
                if job.job_id == job_id:
                    return i
            return None
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Remove a job from the queue without processing.
        
        Parameters
        ----------
        job_id : str
            Job ID to cancel
            
        Returns
        -------
        bool
            True if job was cancelled, False if not found
        """
        with self.lock:
            for i, job in enumerate(self.queue):
                if job.job_id == job_id:
                    self.queue.pop(i)
                    logger.info(f"Job {job_id} cancelled")
                    return True
            return False
    
    def get_batch_status(self, batch_id: str) -> Dict:
        """
        Get status of all jobs in a batch.
        
        Parameters
        ----------
        batch_id : str
            Batch ID to query
            
        Returns
        -------
        dict
            Job IDs grouped by status (pending, running)
        """
        with self.lock:
            pending = [job.job_id for job in self.queue if job.batch_id == batch_id]
            running = [job.job_id for job in self.running_jobs.values() if job.batch_id == batch_id]
            
            return {
                'batch_id': batch_id,
                'pending_jobs': pending,
                'running_jobs': running,
                'total_pending': len(pending),
                'total_running': len(running)
            }


# Global queue manager instance
_queue_manager: Optional[JobQueueManager] = None


def get_queue_manager() -> JobQueueManager:
    """Get or create the global queue manager"""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = JobQueueManager()
    return _queue_manager
