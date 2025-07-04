"""
Webhook Integrations for RecruitAI Pro
Receive real-time data from external systems via webhooks
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import hmac
import hashlib
from pydantic import BaseModel

from core.database import get_db
from models.candidates import Candidate
from models.jobs import JobPosition
from models.interviews import Interview
from agents.resume_analyzer import resume_analyzer
from agents.scheduler import scheduler_agent

logger = logging.getLogger(__name__)

# Create webhook router
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Security keys for webhook verification
WEBHOOK_SECRETS = {
    'indeed': 'your_indeed_webhook_secret',
    'linkedin': 'your_linkedin_webhook_secret',
    'workday': 'your_workday_webhook_secret',
    'greenhouse': 'your_greenhouse_webhook_secret',
    'career_site': 'your_career_site_webhook_secret'
}

class WebhookProcessor:
    """Handles processing of webhook events from various sources"""
    
    def __init__(self):
        self.event_handlers = {
            'job_application': self._handle_job_application,
            'job_posted': self._handle_job_posted,
            'job_updated': self._handle_job_updated,
            'interview_scheduled': self._handle_interview_scheduled,
            'candidate_status_change': self._handle_candidate_status_change,
            'form_submission': self._handle_form_submission
        }
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify webhook signature for security"""
        try:
            # Create expected signature
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Signature verification error: {str(e)}")
            return False
    
    async def process_webhook(self, source: str, event_type: str, data: Dict[str, Any], 
                            db: Session) -> Dict[str, Any]:
        """Process incoming webhook event"""
        try:
            logger.info(f"🔗 Processing webhook: {source} - {event_type}")
            
            handler = self.event_handlers.get(event_type)
            if not handler:
                logger.warning(f"No handler for event type: {event_type}")
                return {'success': False, 'error': f'Unknown event type: {event_type}'}
            
            result = await handler(data, db, source)
            
            logger.info(f"✅ Webhook processed successfully: {source} - {event_type}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Webhook processing error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _handle_job_application(self, data: Dict[str, Any], db: Session, source: str) -> Dict[str, Any]:
        """Handle new job application webhook"""
        try:
            # Extract candidate information
            candidate_info = data.get('candidate', {})
            job_info = data.get('job', {})
            
            # Check if candidate already exists
            candidate_email = candidate_info.get('email')
            if not candidate_email:
                return {'success': False, 'error': 'No candidate email provided'}
            
            existing_candidate = db.query(Candidate).filter(
                Candidate.email == candidate_email
            ).first()
            
            if existing_candidate:
                logger.info(f"Candidate {candidate_email} already exists")
                return {
                    'success': True,
                    'candidate_id': str(existing_candidate.id),
                    'message': 'Candidate already exists'
                }
            
            # Create new candidate
            candidate = Candidate(
                name=candidate_info.get('name', 'Unknown'),
                email=candidate_email,
                phone=candidate_info.get('phone'),
                status='new',
                human_review_notes=f'Applied via {source} webhook'
            )
            
            # Handle resume if provided
            resume_data = data.get('resume', {})
            if resume_data:
                candidate.resume_text = resume_data.get('text')
                candidate.resume_filename = resume_data.get('filename')
            
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            
            # Trigger AI analysis if resume text is available
            if candidate.resume_text:
                try:
                    job_position = None
                    if job_info.get('id'):
                        job_position = db.query(JobPosition).filter(
                            JobPosition.id == job_info['id']
                        ).first()
                    
                    await resume_analyzer.analyze_resume(candidate, job_position)
                    
                except Exception as e:
                    logger.warning(f"Resume analysis failed: {str(e)}")
            
            return {
                'success': True,
                'candidate_id': str(candidate.id),
                'message': 'Job application processed successfully'
            }
            
        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_job_posted(self, data: Dict[str, Any], db: Session, source: str) -> Dict[str, Any]:
        """Handle new job posting webhook"""
        try:
            # Extract job information
            job_data = data.get('job', {})
            
            # Check if job already exists
            job_title = job_data.get('title')
            job_external_id = job_data.get('external_id')
            
            existing_job = None
            if job_external_id:
                # Check by external ID if provided
                existing_job = db.query(JobPosition).filter(
                    JobPosition.hiring_manager.contains(job_external_id)
                ).first()
            
            if existing_job:
                logger.info(f"Job {job_title} already exists")
                return {
                    'success': True,
                    'job_id': str(existing_job.id),
                    'message': 'Job already exists'
                }
            
            # Create new job position
            job_position = JobPosition(
                title=job_title,
                department=job_data.get('department'),
                location=job_data.get('location'),
                employment_type=job_data.get('employment_type', 'full_time'),
                description=job_data.get('description'),
                required_skills=job_data.get('required_skills', []),
                preferred_skills=job_data.get('preferred_skills', []),
                salary_min=job_data.get('salary_min'),
                salary_max=job_data.get('salary_max'),
                status='open',
                hiring_manager=f'{source}:{job_external_id}' if job_external_id else f'Webhook from {source}'
            )
            
            db.add(job_position)
            db.commit()
            db.refresh(job_position)
            
            logger.info(f"New job created: {job_title}")
            
            return {
                'success': True,
                'job_id': str(job_position.id),
                'message': 'Job posted successfully'
            }
            
        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_job_updated(self, data: Dict[str, Any], db: Session, source: str) -> Dict[str, Any]:
        """Handle job update webhook"""
        try:
            job_data = data.get('job', {})
            job_external_id = job_data.get('external_id')
            
            if not job_external_id:
                return {'success': False, 'error': 'No external job ID provided'}
            
            # Find existing job
            job = db.query(JobPosition).filter(
                JobPosition.hiring_manager.contains(job_external_id)
            ).first()
            
            if not job:
                return {'success': False, 'error': 'Job not found'}
            
            # Update job fields
            if 'title' in job_data:
                job.title = job_data['title']
            if 'description' in job_data:
                job.description = job_data['description']
            if 'status' in job_data:
                job.status = job_data['status']
            if 'required_skills' in job_data:
                job.required_skills = job_data['required_skills']
            
            db.commit()
            
            return {
                'success': True,
                'job_id': str(job.id),
                'message': 'Job updated successfully'
            }
            
        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_interview_scheduled(self, data: Dict[str, Any], db: Session, source: str) -> Dict[str, Any]:
        """Handle interview scheduled webhook"""
        try:
            # This would handle external interview scheduling notifications
            interview_data = data.get('interview', {})
            
            # Find candidate and job
            candidate_id = interview_data.get('candidate_id')
            job_id = interview_data.get('job_id')
            
            if not candidate_id or not job_id:
                return {'success': False, 'error': 'Missing candidate or job ID'}
            
            # Process interview scheduling
            # This would typically sync with our internal scheduling system
            
            return {
                'success': True,
                'message': 'Interview webhook processed'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _handle_candidate_status_change(self, data: Dict[str, Any], db: Session, source: str) -> Dict[str, Any]:
        """Handle candidate status change webhook"""
        try:
            candidate_email = data.get('candidate_email')
            new_status = data.get('status')
            
            if not candidate_email or not new_status:
                return {'success': False, 'error': 'Missing candidate email or status'}
            
            # Find and update candidate
            candidate = db.query(Candidate).filter(
                Candidate.email == candidate_email
            ).first()
            
            if not candidate:
                return {'success': False, 'error': 'Candidate not found'}
            
            candidate.status = new_status
            candidate.human_review_notes = f'Status updated via {source} webhook'
            
            db.commit()
            
            return {
                'success': True,
                'candidate_id': str(candidate.id),
                'message': 'Candidate status updated'
            }
            
        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_form_submission(self, data: Dict[str, Any], db: Session, source: str) -> Dict[str, Any]:
        """Handle career website form submission"""
        try:
            # Extract form data
            form_data = data.get('form_data', {})
            
            # Create candidate from form submission
            candidate = Candidate(
                name=form_data.get('name'),
                email=form_data.get('email'),
                phone=form_data.get('phone'),
                status='new',
                human_review_notes=f'Applied via {source} career form'
            )
            
            # Handle additional form fields
            if 'cover_letter' in form_data:
                candidate.resume_text = form_data['cover_letter']
            
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            
            return {
                'success': True,
                'candidate_id': str(candidate.id),
                'message': 'Form submission processed'
            }
            
        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}

# Initialize webhook processor
webhook_processor = WebhookProcessor()

# Webhook endpoints
@webhook_router.post("/indeed")
async def indeed_webhook(
    request: Request,
    x_indeed_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """Handle Indeed webhook events"""
    try:
        body = await request.body()
        
        # Verify signature
        if x_indeed_signature:
            if not webhook_processor.verify_webhook_signature(
                body, x_indeed_signature, WEBHOOK_SECRETS['indeed']
            ):
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse event data
        event_data = json.loads(body)
        event_type = event_data.get('event_type')
        
        result = await webhook_processor.process_webhook(
            'indeed', event_type, event_data, db
        )
        
        return JSONResponse(content=result, status_code=200)
        
    except Exception as e:
        logger.error(f"Indeed webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@webhook_router.post("/linkedin")
async def linkedin_webhook(
    request: Request,
    x_linkedin_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """Handle LinkedIn webhook events"""
    try:
        body = await request.body()
        
        # Verify signature
        if x_linkedin_signature:
            if not webhook_processor.verify_webhook_signature(
                body, x_linkedin_signature, WEBHOOK_SECRETS['linkedin']
            ):
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse event data
        event_data = json.loads(body)
        event_type = event_data.get('event_type')
        
        result = await webhook_processor.process_webhook(
            'linkedin', event_type, event_data, db
        )
        
        return JSONResponse(content=result, status_code=200)
        
    except Exception as e:
        logger.error(f"LinkedIn webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@webhook_router.post("/workday")
async def workday_webhook(
    request: Request,
    x_workday_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """Handle Workday ATS webhook events"""
    try:
        body = await request.body()
        
        # Verify signature
        if x_workday_signature:
            if not webhook_processor.verify_webhook_signature(
                body, x_workday_signature, WEBHOOK_SECRETS['workday']
            ):
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse event data
        event_data = json.loads(body)
        event_type = event_data.get('event_type')
        
        result = await webhook_processor.process_webhook(
            'workday', event_type, event_data, db
        )
        
        return JSONResponse(content=result, status_code=200)
        
    except Exception as e:
        logger.error(f"Workday webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@webhook_router.post("/career-site")
async def career_site_webhook(
    request: Request,
    x_career_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """Handle career website form submissions"""
    try:
        body = await request.body()
        
        # Verify signature
        if x_career_signature:
            if not webhook_processor.verify_webhook_signature(
                body, x_career_signature, WEBHOOK_SECRETS['career_site']
            ):
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse form data
        form_data = json.loads(body)
        
        result = await webhook_processor.process_webhook(
            'career_site', 'form_submission', form_data, db
        )
        
        return JSONResponse(content=result, status_code=200)
        
    except Exception as e:
        logger.error(f"Career site webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@webhook_router.post("/generic")
async def generic_webhook(
    request: Request,
    source: str = Header(..., alias="X-Source"),
    event_type: str = Header(..., alias="X-Event-Type"),
    signature: str = Header(None, alias="X-Signature"),
    db: Session = Depends(get_db)
):
    """Handle generic webhook events from any source"""
    try:
        body = await request.body()
        
        # Verify signature if provided
        if signature and source in WEBHOOK_SECRETS:
            if not webhook_processor.verify_webhook_signature(
                body, signature, WEBHOOK_SECRETS[source]
            ):
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse event data
        event_data = json.loads(body)
        
        result = await webhook_processor.process_webhook(
            source, event_type, event_data, db
        )
        
        return JSONResponse(content=result, status_code=200)
        
    except Exception as e:
        logger.error(f"Generic webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check for webhooks
@webhook_router.get("/health")
async def webhook_health():
    """Health check endpoint for webhook service"""
    return {
        "status": "healthy",
        "service": "webhooks",
        "timestamp": datetime.utcnow().isoformat(),
        "supported_sources": list(WEBHOOK_SECRETS.keys())
    } 