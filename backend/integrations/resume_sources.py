"""
Resume Source Integrations for RecruitAI Pro
Automatically process resumes from emails, cloud storage, and web forms
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass
import logging
import tempfile
from pathlib import Path

# Email processing
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Cloud storage
import boto3
from google.cloud import storage as gcs
from dropbox import Dropbox

# Web processing
import requests
from fastapi import UploadFile

from core.database import get_db
from models.candidates import Candidate
from services.file_processor import file_processor
from agents.resume_analyzer import resume_analyzer

logger = logging.getLogger(__name__)

@dataclass
class EmailConfig:
    """Configuration for email resume processing"""
    server: str
    port: int
    username: str
    password: str
    folder: str = "INBOX"
    use_ssl: bool = True
    mark_processed: bool = True

@dataclass
class CloudStorageConfig:
    """Configuration for cloud storage integration"""
    provider: str  # 'aws', 'gcs', 'dropbox'
    credentials: Dict[str, str]
    bucket_name: str
    folder_path: str = "resumes/"
    auto_process: bool = True

class ResumeSourceIntegrator:
    """Handles integration with multiple resume sources"""
    
    def __init__(self):
        self.supported_formats = ['.pdf', '.doc', '.docx', '.txt']
        self.processed_files = set()
    
    async def process_email_resumes(self, config: EmailConfig) -> Dict[str, Any]:
        """Process resumes from email attachments"""
        try:
            logger.info(f"📧 Processing resumes from {config.server}")
            
            # Connect to email server
            if config.use_ssl:
                mail = imaplib.IMAP4_SSL(config.server, config.port)
            else:
                mail = imaplib.IMAP4(config.server, config.port)
            
            mail.login(config.username, config.password)
            mail.select(config.folder)
            
            # Search for unread emails with attachments
            status, messages = mail.search(None, '(UNSEEN)')
            
            if status != 'OK':
                raise Exception("Failed to search emails")
            
            email_ids = messages[0].split()
            processed_count = 0
            errors = []
            
            for email_id in email_ids:
                try:
                    result = await self._process_email_message(mail, email_id, config)
                    if result['success']:
                        processed_count += 1
                        if config.mark_processed:
                            mail.store(email_id, '+FLAGS', '\\Seen')
                    else:
                        errors.append(result['error'])
                        
                except Exception as e:
                    errors.append(f"Email {email_id}: {str(e)}")
                    logger.error(f"Error processing email {email_id}: {str(e)}")
            
            mail.close()
            mail.logout()
            
            logger.info(f"✅ Email processing completed: {processed_count} resumes processed")
            
            return {
                'success': True,
                'processed_count': processed_count,
                'total_emails': len(email_ids),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Email processing error: {str(e)}")
            return {'success': False, 'error': str(e), 'processed_count': 0}
    
    async def _process_email_message(self, mail, email_id: bytes, config: EmailConfig) -> Dict[str, Any]:
        """Process individual email message"""
        try:
            # Fetch email message
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                return {'success': False, 'error': 'Failed to fetch email'}
            
            # Parse email
            email_body = msg_data[0][1]
            email_message = email.message_from_bytes(email_body)
            
            # Extract sender information
            sender_email = email_message.get('From', '')
            sender_name = email_message.get('Reply-To', sender_email)
            subject = email_message.get('Subject', '')
            
            # Process attachments
            attachments_processed = []
            
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_disposition() == 'attachment':
                        filename = part.get_filename()
                        
                        if filename and any(filename.lower().endswith(ext) for ext in self.supported_formats):
                            # Save attachment temporarily
                            file_data = part.get_payload(decode=True)
                            
                            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp_file:
                                tmp_file.write(file_data)
                                tmp_file_path = tmp_file.name
                            
                            try:
                                # Process resume
                                result = await self._process_resume_file(
                                    tmp_file_path,
                                    filename,
                                    sender_name,
                                    sender_email,
                                    f"Email application: {subject}"
                                )
                                
                                if result['success']:
                                    attachments_processed.append(result)
                                
                            finally:
                                # Clean up temp file
                                os.unlink(tmp_file_path)
            
            if attachments_processed:
                return {
                    'success': True,
                    'attachments_processed': len(attachments_processed),
                    'candidates_created': [r['candidate_id'] for r in attachments_processed]
                }
            else:
                return {'success': False, 'error': 'No valid resume attachments found'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def process_cloud_storage_resumes(self, config: CloudStorageConfig) -> Dict[str, Any]:
        """Process resumes from cloud storage"""
        try:
            logger.info(f"☁️ Processing resumes from {config.provider}")
            
            if config.provider == 'aws':
                return await self._process_aws_s3_resumes(config)
            elif config.provider == 'gcs':
                return await self._process_gcs_resumes(config)
            elif config.provider == 'dropbox':
                return await self._process_dropbox_resumes(config)
            else:
                raise ValueError(f"Unsupported provider: {config.provider}")
            
        except Exception as e:
            logger.error(f"Cloud storage processing error: {str(e)}")
            return {'success': False, 'error': str(e), 'processed_count': 0}
    
    async def _process_aws_s3_resumes(self, config: CloudStorageConfig) -> Dict[str, Any]:
        """Process resumes from AWS S3"""
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=config.credentials['access_key'],
                aws_secret_access_key=config.credentials['secret_key'],
                region_name=config.credentials.get('region', 'us-east-1')
            )
            
            # List objects in bucket
            response = s3_client.list_objects_v2(
                Bucket=config.bucket_name,
                Prefix=config.folder_path
            )
            
            processed_count = 0
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    
                    # Skip if already processed or not a resume file
                    if key in self.processed_files or not any(key.lower().endswith(ext) for ext in self.supported_formats):
                        continue
                    
                    try:
                        # Download file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(key).suffix) as tmp_file:
                            s3_client.download_file(config.bucket_name, key, tmp_file.name)
                            
                            # Process resume
                            result = await self._process_resume_file(
                                tmp_file.name,
                                Path(key).name,
                                "Unknown",  # Name will be extracted from resume
                                "unknown@example.com",  # Email will be extracted from resume
                                f"S3 Upload: {key}"
                            )
                            
                            if result['success']:
                                processed_count += 1
                                self.processed_files.add(key)
                            
                        # Clean up temp file
                        os.unlink(tmp_file.name)
                        
                    except Exception as e:
                        logger.error(f"Error processing S3 file {key}: {str(e)}")
                        continue
            
            return {
                'success': True,
                'processed_count': processed_count,
                'total_files': len(response.get('Contents', []))
            }
            
        except Exception as e:
            raise Exception(f"S3 processing error: {str(e)}")
    
    async def _process_gcs_resumes(self, config: CloudStorageConfig) -> Dict[str, Any]:
        """Process resumes from Google Cloud Storage"""
        try:
            # Initialize GCS client
            client = gcs.Client.from_service_account_info(config.credentials)
            bucket = client.bucket(config.bucket_name)
            
            processed_count = 0
            
            for blob in bucket.list_blobs(prefix=config.folder_path):
                if blob.name in self.processed_files or not any(blob.name.lower().endswith(ext) for ext in self.supported_formats):
                    continue
                
                try:
                    # Download file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(blob.name).suffix) as tmp_file:
                        blob.download_to_filename(tmp_file.name)
                        
                        # Process resume
                        result = await self._process_resume_file(
                            tmp_file.name,
                            Path(blob.name).name,
                            "Unknown",
                            "unknown@example.com",
                            f"GCS Upload: {blob.name}"
                        )
                        
                        if result['success']:
                            processed_count += 1
                            self.processed_files.add(blob.name)
                    
                    # Clean up temp file
                    os.unlink(tmp_file.name)
                    
                except Exception as e:
                    logger.error(f"Error processing GCS file {blob.name}: {str(e)}")
                    continue
            
            return {
                'success': True,
                'processed_count': processed_count
            }
            
        except Exception as e:
            raise Exception(f"GCS processing error: {str(e)}")
    
    async def _process_dropbox_resumes(self, config: CloudStorageConfig) -> Dict[str, Any]:
        """Process resumes from Dropbox"""
        try:
            dbx = Dropbox(config.credentials['access_token'])
            
            # List files in folder
            result = dbx.files_list_folder(config.folder_path)
            processed_count = 0
            
            for entry in result.entries:
                if entry.name in self.processed_files or not any(entry.name.lower().endswith(ext) for ext in self.supported_formats):
                    continue
                
                try:
                    # Download file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(entry.name).suffix) as tmp_file:
                        metadata, response = dbx.files_download(entry.path_lower)
                        tmp_file.write(response.content)
                        tmp_file.flush()
                        
                        # Process resume
                        result = await self._process_resume_file(
                            tmp_file.name,
                            entry.name,
                            "Unknown",
                            "unknown@example.com",
                            f"Dropbox Upload: {entry.name}"
                        )
                        
                        if result['success']:
                            processed_count += 1
                            self.processed_files.add(entry.name)
                    
                    # Clean up temp file
                    os.unlink(tmp_file.name)
                    
                except Exception as e:
                    logger.error(f"Error processing Dropbox file {entry.name}: {str(e)}")
                    continue
            
            return {
                'success': True,
                'processed_count': processed_count
            }
            
        except Exception as e:
            raise Exception(f"Dropbox processing error: {str(e)}")
    
    async def _process_resume_file(self, file_path: str, filename: str, candidate_name: str, 
                                  candidate_email: str, source: str) -> Dict[str, Any]:
        """Process a single resume file"""
        try:
            # Process file to extract text
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Create a mock UploadFile for processing
            class MockUploadFile:
                def __init__(self, filename: str, content: bytes):
                    self.filename = filename
                    self.content = content
                    
                async def read(self):
                    return self.content
            
            mock_file = MockUploadFile(filename, file_content)
            file_result = await file_processor.process_resume_file(mock_file)
            
            if not file_result["success"]:
                return {'success': False, 'error': 'Failed to process resume file'}
            
            # Extract candidate information from resume text if not provided
            if candidate_name == "Unknown" or candidate_email == "unknown@example.com":
                extracted_info = await self._extract_candidate_info(file_result["extracted_text"])
                if extracted_info:
                    candidate_name = extracted_info.get('name', candidate_name)
                    candidate_email = extracted_info.get('email', candidate_email)
            
            # Create candidate record
            async with get_db() as db:
                # Check if candidate already exists
                existing_candidate = db.query(Candidate).filter(
                    Candidate.email == candidate_email
                ).first()
                
                if existing_candidate:
                    return {
                        'success': False,
                        'error': f'Candidate with email {candidate_email} already exists'
                    }
                
                # Create new candidate
                candidate = Candidate(
                    name=candidate_name,
                    email=candidate_email,
                    resume_filename=filename,
                    resume_file_path=file_result["file_path"],
                    resume_text=file_result["extracted_text"],
                    status="new",
                    human_review_notes=f"Imported from {source}"
                )
                
                db.add(candidate)
                db.commit()
                db.refresh(candidate)
                
                # Trigger AI analysis
                try:
                    await resume_analyzer.analyze_resume(candidate)
                except Exception as e:
                    logger.warning(f"Resume analysis failed for {candidate.id}: {str(e)}")
                
                return {
                    'success': True,
                    'candidate_id': str(candidate.id),
                    'candidate_name': candidate.name,
                    'candidate_email': candidate.email,
                    'source': source
                }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _extract_candidate_info(self, resume_text: str) -> Optional[Dict[str, str]]:
        """Extract candidate name and email from resume text using AI"""
        try:
            # This would use AI to extract candidate information
            # For now, return None to use fallback values
            return None
            
        except Exception as e:
            logger.error(f"Error extracting candidate info: {str(e)}")
            return None

# Example configurations
EXAMPLE_EMAIL_CONFIG = EmailConfig(
    server="imap.gmail.com",
    port=993,
    username="hr@company.com",
    password="your_app_password",
    folder="INBOX",
    use_ssl=True,
    mark_processed=True
)

EXAMPLE_AWS_CONFIG = CloudStorageConfig(
    provider="aws",
    credentials={
        "access_key": "your_access_key",
        "secret_key": "your_secret_key",
        "region": "us-east-1"
    },
    bucket_name="company-resumes",
    folder_path="incoming/",
    auto_process=True
)

EXAMPLE_GCS_CONFIG = CloudStorageConfig(
    provider="gcs",
    credentials={
        # GCS service account credentials dict
    },
    bucket_name="company-resumes",
    folder_path="incoming/",
    auto_process=True
)

# Initialize integrator
resume_source_integrator = ResumeSourceIntegrator()

# Example scheduled processing function
async def scheduled_resume_processing():
    """Function to be called by scheduler for automatic resume processing"""
    logger.info("🔄 Starting scheduled resume processing")
    
    results = {}
    
    # Process email resumes
    try:
        email_result = await resume_source_integrator.process_email_resumes(EXAMPLE_EMAIL_CONFIG)
        results['email'] = email_result
        logger.info(f"📧 Email processing: {email_result['processed_count']} resumes processed")
    except Exception as e:
        logger.error(f"Email processing failed: {str(e)}")
        results['email'] = {'success': False, 'error': str(e)}
    
    # Process cloud storage resumes
    try:
        cloud_result = await resume_source_integrator.process_cloud_storage_resumes(EXAMPLE_AWS_CONFIG)
        results['cloud'] = cloud_result
        logger.info(f"☁️ Cloud processing: {cloud_result['processed_count']} resumes processed")
    except Exception as e:
        logger.error(f"Cloud processing failed: {str(e)}")
        results['cloud'] = {'success': False, 'error': str(e)}
    
    total_processed = sum(
        result.get('processed_count', 0) 
        for result in results.values() 
        if result.get('success', False)
    )
    
    logger.info(f"✅ Scheduled resume processing completed: {total_processed} resumes processed")
    
    return results 