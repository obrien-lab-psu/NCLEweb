#!/usr/bin/env python3
"""
Email notification system for NCLE Web Application
Sends job completion notifications to users
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime

class EmailNotifier:
    """Email notification handler"""
    
    def __init__(self, smtp_host=None, smtp_port=587, smtp_user=None, smtp_pass=None, from_email=None):
        """
        Initialize email notifier with SMTP settings
        
        Settings can be provided via parameters or environment variables:
        - SMTP_HOST
        - SMTP_PORT
        - SMTP_USER
        - SMTP_PASS
        - FROM_EMAIL
        """
        self.smtp_host = smtp_host or os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(smtp_port or os.getenv('SMTP_PORT', 587))
        self.smtp_user = smtp_user or os.getenv('SMTP_USER')
        self.smtp_pass = smtp_pass or os.getenv('SMTP_PASS')
        self.from_email = from_email or os.getenv('FROM_EMAIL', self.smtp_user)
        self.enabled = bool(self.smtp_user and self.smtp_pass)
        
        if not self.enabled:
            print("WARNING: Email notifications disabled - SMTP credentials not configured")
    
    def send_completion_email(self, to_email, job_name, job_id, num_entanglements, results_url):
        """Send job completion notification"""
        if not self.enabled:
            print(f"Email notification skipped (not configured) for job {job_id}")
            return False
        
        try:
            subject = f"NCLE Analysis Complete: {job_name}"
            
            # Create HTML email body
            html_body = f"""
            <html>
            <head></head>
            <body>
                <h2>Your NCLE Analysis is Complete!</h2>
                <p>Hello,</p>
                <p>Your Gaussian entanglement analysis has finished processing.</p>
                
                <h3>Job Details:</h3>
                <ul>
                    <li><strong>Job Name:</strong> {job_name}</li>
                    <li><strong>Job ID:</strong> {job_id}</li>
                    <li><strong>Results Found:</strong> {num_entanglements} entanglements</li>
                    <li><strong>Completed:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</li>
                </ul>
                
                <p>
                    <a href="{results_url}" style="display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">
                        View Results
                    </a>
                </p>
                
                <p>Or copy this link: <a href="{results_url}">{results_url}</a></p>
                
                <hr>
                <p style="color: #666; font-size: 12px;">
                    This is an automated message from the NCLE Gaussian Entanglement Analysis Server.
                    <br>Your results will be available indefinitely at the link above.
                </p>
            </body>
            </html>
            """
            
            # Create plain text alternative
            text_body = f"""
Your NCLE Analysis is Complete!

Job Details:
- Job Name: {job_name}
- Job ID: {job_id}
- Results Found: {num_entanglements} entanglements
- Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

View your results at: {results_url}

---
This is an automated message from the NCLE Gaussian Entanglement Analysis Server.
Your results will be available indefinitely at the link above.
            """
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Attach both plain text and HTML versions
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            
            print(f"Email notification sent to {to_email} for job {job_id}")
            return True
            
        except Exception as e:
            print(f"Failed to send email notification: {e}")
            return False
    
    def send_error_email(self, to_email, job_name, job_id, error_message):
        """Send job failure notification"""
        if not self.enabled:
            print(f"Email notification skipped (not configured) for failed job {job_id}")
            return False
        
        try:
            subject = f"NCLE Analysis Failed: {job_name}"
            
            html_body = f"""
            <html>
            <head></head>
            <body>
                <h2>NCLE Analysis Failed</h2>
                <p>Hello,</p>
                <p>Unfortunately, your Gaussian entanglement analysis encountered an error.</p>
                
                <h3>Job Details:</h3>
                <ul>
                    <li><strong>Job Name:</strong> {job_name}</li>
                    <li><strong>Job ID:</strong> {job_id}</li>
                    <li><strong>Error:</strong> {error_message}</li>
                </ul>
                
                <p>Please check your PDB file and try again. If the problem persists, contact support.</p>
                
                <hr>
                <p style="color: #666; font-size: 12px;">
                    This is an automated message from the NCLE Gaussian Entanglement Analysis Server.
                </p>
            </body>
            </html>
            """
            
            text_body = f"""
NCLE Analysis Failed

Job Details:
- Job Name: {job_name}
- Job ID: {job_id}
- Error: {error_message}

Please check your PDB file and try again. If the problem persists, contact support.

---
This is an automated message from the NCLE Gaussian Entanglement Analysis Server.
            """
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            
            print(f"Error email notification sent to {to_email} for job {job_id}")
            return True
            
        except Exception as e:
            print(f"Failed to send error email notification: {e}")
            return False


# Initialize email notifier (will use environment variables)
email_notifier = EmailNotifier()
