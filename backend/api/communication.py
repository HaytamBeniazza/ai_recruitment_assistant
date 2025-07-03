"""
Communication API endpoints for RecruitAI Pro
Handles email, SMS, and automated messaging for recruitment communication
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
from pydantic import BaseModel, EmailStr, Field

from core.database import get_db
from models.communications import (
    MessageTemplate, CommunicationMessage, CommunicationChannel, 
    NotificationSchedule, CommunicationType, CommunicationStatus
)
from models.candidates import Candidate
from models.interviews import Interview
from models.jobs import JobPosition
from agents.communication_agent import get_communication_agent

# Create router
router = APIRouter(prefix="/communication", tags=["Communication"])

# Request/Response Models
class SendEmailRequest(BaseModel):
    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body (plain text)")
    html_body: Optional[str] = Field(None, description="Email body (HTML)")
    cc_emails: Optional[List[str]] = Field(None, description="CC email addresses")
    bcc_emails: Optional[List[str]] = Field(None, description="BCC email addresses")
    priority: str = Field("medium", description="Message priority")
    template_type: Optional[str] = Field(None, description="Template type if using template")
    template_variables: Optional[Dict[str, Any]] = Field(None, description="Template variables")
    candidate_id: Optional[str] = Field(None, description="Associated candidate ID")
    interview_id: Optional[str] = Field(None, description="Associated interview ID")
    job_position_id: Optional[str] = Field(None, description="Associated job position ID")

class SendSMSRequest(BaseModel):
    to_phone: str = Field(..., description="Recipient phone number")
    message: str = Field(..., description="SMS message text")
    priority: str = Field("medium", description="Message priority")
    template_type: Optional[str] = Field(None, description="Template type if using template")
    template_variables: Optional[Dict[str, Any]] = Field(None, description="Template variables")
    candidate_id: Optional[str] = Field(None, description="Associated candidate ID")
    interview_id: Optional[str] = Field(None, description="Associated interview ID")

class TemplatedMessageRequest(BaseModel):
    template_type: str = Field(..., description="Type of template to use")
    communication_type: str = Field(..., description="email or sms")
    recipient: str = Field(..., description="Email address or phone number")
    template_variables: Dict[str, Any] = Field(..., description="Variables for template rendering")
    priority: str = Field("medium", description="Message priority")
    tone: Optional[str] = Field("professional", description="AI tone for enhancement")
    use_ai_enhancement: bool = Field(False, description="Whether to use AI to enhance the message")
    custom_instructions: Optional[str] = Field(None, description="Custom AI instructions")
    candidate_id: Optional[str] = Field(None, description="Associated candidate ID")
    interview_id: Optional[str] = Field(None, description="Associated interview ID")
    job_position_id: Optional[str] = Field(None, description="Associated job position ID")

class ScheduleMessageRequest(BaseModel):
    communication_type: str = Field(..., description="email or sms")
    recipient: str = Field(..., description="Email address or phone number")
    template_type: str = Field(..., description="Type of template to use")
    template_variables: Dict[str, Any] = Field(..., description="Variables for template rendering")
    send_time: datetime = Field(..., description="When to send the message")
    priority: str = Field("medium", description="Message priority")
    candidate_id: Optional[str] = Field(None, description="Associated candidate ID")
    interview_id: Optional[str] = Field(None, description="Associated interview ID")

class MessageTemplateCreate(BaseModel):
    name: str = Field(..., description="Template name")
    category: str = Field(..., description="Template category")
    communication_type: str = Field(..., description="email or sms")
    subject_template: Optional[str] = Field(None, description="Subject template (for email)")
    body_template: str = Field(..., description="Body template")
    html_template: Optional[str] = Field(None, description="HTML template (for email)")
    required_variables: Optional[List[str]] = Field(None, description="Required template variables")
    optional_variables: Optional[List[str]] = Field(None, description="Optional template variables")
    default_values: Optional[Dict[str, Any]] = Field(None, description="Default variable values")
    description: Optional[str] = Field(None, description="Template description")
    language: str = Field("en", description="Template language")

class CommunicationChannelCreate(BaseModel):
    user_email: str = Field(..., description="User email address")
    user_name: Optional[str] = Field(None, description="User name")
    user_type: str = Field(..., description="candidate, interviewer, or admin")
    email_enabled: bool = Field(True, description="Email notifications enabled")
    sms_enabled: bool = Field(False, description="SMS notifications enabled")
    primary_email: Optional[str] = Field(None, description="Primary email address")
    phone_number: Optional[str] = Field(None, description="Phone number")
    interview_notifications: Optional[Dict[str, bool]] = Field({"email": True, "sms": False})
    reminder_notifications: Optional[Dict[str, bool]] = Field({"email": True, "sms": True})
    confirmation_notifications: Optional[Dict[str, bool]] = Field({"email": True, "sms": False})
    timezone: str = Field("UTC", description="User timezone")
    preferred_language: str = Field("en", description="Preferred language")

class MessageResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    external_id: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    delivery_time_ms: Optional[int] = None
    database_id: Optional[str] = None

# Communication Endpoints

@router.post("/send-email", response_model=MessageResponse)
async def send_email(
    request: SendEmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Send an email message
    
    Supports both direct email sending and template-based emails with AI enhancement.
    """
    try:
        agent = get_communication_agent()
        
        # If using template, render the template first
        if request.template_type and request.template_variables:
            # Validate template variables
            is_valid, missing_vars = agent.validate_template_variables(
                request.template_type, request.template_variables
            )
            
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required template variables: {missing_vars}"
                )
            
            # Render template
            subject, body = await agent._render_template(
                request.template_type, request.template_variables, "email"
            )
            
            # Use template-rendered content if not provided
            if not request.subject:
                request.subject = subject
            if not request.body:
                request.body = body
        
        # Create database record
        message = CommunicationMessage(
            template_id=None,  # TODO: Link to template if used
            interview_id=uuid.UUID(request.interview_id) if request.interview_id else None,
            candidate_id=uuid.UUID(request.candidate_id) if request.candidate_id else None,
            job_position_id=uuid.UUID(request.job_position_id) if request.job_position_id else None,
            communication_type=CommunicationType.EMAIL,
            priority=request.priority,
            status=CommunicationStatus.PENDING,
            to_email=request.to_email,
            to_name=None,  # TODO: Extract from candidate if available
            cc_emails=request.cc_emails,
            from_email=agent.email_config.sender_email if agent.email_config else None,
            from_name=agent.email_config.sender_name if agent.email_config else None,
            subject=request.subject,
            body=request.body,
            html_body=request.html_body,
            template_variables=request.template_variables,
            send_immediately=True,
            source="api"
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        # Send email via agent
        result = await agent.send_email(
            to_email=request.to_email,
            subject=request.subject,
            body=request.body,
            html_body=request.html_body,
            cc_emails=request.cc_emails,
            bcc_emails=request.bcc_emails,
            priority=request.priority
        )
        
        # Update database record with result
        message.status = CommunicationStatus.SENT if result.success else CommunicationStatus.FAILED
        message.external_message_id = result.external_id
        message.sent_at = datetime.utcnow() if result.success else None
        message.failed_at = datetime.utcnow() if not result.success else None
        message.error_message = result.error_message
        message.error_code = result.error_code
        
        db.commit()
        
        return MessageResponse(
            success=result.success,
            message_id=result.message_id,
            external_id=result.external_id,
            error_message=result.error_message,
            error_code=result.error_code,
            delivery_time_ms=result.delivery_time_ms,
            database_id=str(message.id)
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

@router.post("/send-sms", response_model=MessageResponse)
async def send_sms(
    request: SendSMSRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Send an SMS message
    
    Supports both direct SMS sending and template-based SMS.
    """
    try:
        agent = get_communication_agent()
        
        message_text = request.message
        
        # If using template, render the template first
        if request.template_type and request.template_variables:
            # Validate template variables
            is_valid, missing_vars = agent.validate_template_variables(
                request.template_type, request.template_variables
            )
            
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required template variables: {missing_vars}"
                )
            
            # Render template
            _, body = await agent._render_template(
                request.template_type, request.template_variables, "sms"
            )
            message_text = body
        
        # Create database record
        message = CommunicationMessage(
            interview_id=uuid.UUID(request.interview_id) if request.interview_id else None,
            candidate_id=uuid.UUID(request.candidate_id) if request.candidate_id else None,
            communication_type=CommunicationType.SMS,
            priority=request.priority,
            status=CommunicationStatus.PENDING,
            to_phone=request.to_phone,
            body=message_text,
            template_variables=request.template_variables,
            send_immediately=True,
            source="api"
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        # Send SMS via agent
        result = await agent.send_sms(
            to_phone=request.to_phone,
            message=message_text,
            priority=request.priority
        )
        
        # Update database record with result
        message.status = CommunicationStatus.SENT if result.success else CommunicationStatus.FAILED
        message.external_message_id = result.external_id
        message.sent_at = datetime.utcnow() if result.success else None
        message.failed_at = datetime.utcnow() if not result.success else None
        message.error_message = result.error_message
        message.error_code = result.error_code
        
        db.commit()
        
        return MessageResponse(
            success=result.success,
            message_id=result.message_id,
            external_id=result.external_id,
            error_message=result.error_message,
            error_code=result.error_code,
            delivery_time_ms=result.delivery_time_ms,
            database_id=str(message.id)
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")

@router.post("/send-templated", response_model=MessageResponse)
async def send_templated_message(
    request: TemplatedMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Send a message using a template with optional AI enhancement
    
    This endpoint provides intelligent template rendering with AI-powered personalization.
    """
    try:
        agent = get_communication_agent()
        
        # Validate template variables
        is_valid, missing_vars = agent.validate_template_variables(
            request.template_type, request.template_variables
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required template variables: {missing_vars}"
            )
        
        # Render template with optional AI enhancement
        if request.use_ai_enhancement and agent.openai_client:
            subject, body = await agent.compose_with_ai(
                template_type=request.template_type,
                variables=request.template_variables,
                tone=request.tone,
                custom_instructions=request.custom_instructions
            )
        else:
            subject, body = await agent._render_template(
                request.template_type, request.template_variables, request.communication_type
            )
        
        # Send based on communication type
        if request.communication_type == "email":
            # Create email request
            email_request = SendEmailRequest(
                to_email=request.recipient,
                subject=subject,
                body=body,
                priority=request.priority,
                template_type=request.template_type,
                template_variables=request.template_variables,
                candidate_id=request.candidate_id,
                interview_id=request.interview_id,
                job_position_id=request.job_position_id
            )
            
            return await send_email(email_request, background_tasks, db)
            
        elif request.communication_type == "sms":
            # Create SMS request
            sms_request = SendSMSRequest(
                to_phone=request.recipient,
                message=body,
                priority=request.priority,
                template_type=request.template_type,
                template_variables=request.template_variables,
                candidate_id=request.candidate_id,
                interview_id=request.interview_id
            )
            
            return await send_sms(sms_request, background_tasks, db)
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported communication type: {request.communication_type}"
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send templated message: {str(e)}")

@router.post("/schedule", response_model=Dict[str, Any])
async def schedule_message(
    request: ScheduleMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Schedule a message to be sent at a specific time
    
    Creates a notification schedule that will trigger message sending.
    """
    try:
        agent = get_communication_agent()
        
        # Validate template variables
        is_valid, missing_vars = agent.validate_template_variables(
            request.template_type, request.template_variables
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required template variables: {missing_vars}"
            )
        
        # Create notification schedule
        schedule = NotificationSchedule(
            interview_id=uuid.UUID(request.interview_id) if request.interview_id else None,
            name=f"{request.template_type}_{request.communication_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            description=f"Scheduled {request.communication_type} using {request.template_type} template",
            trigger_type="time_based",
            trigger_time=request.send_time,
            recipient_type="custom",
            custom_recipients=[request.recipient],
            template_variables=request.template_variables,
            is_active=True,
            status="pending",
            next_execution_at=request.send_time
        )
        
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        
        # Also schedule with the agent (for immediate background processing)
        schedule_id = await agent.schedule_message(
            communication_type=request.communication_type,
            recipient=request.recipient,
            template_type=request.template_type,
            variables=request.template_variables,
            send_time=request.send_time,
            priority=request.priority
        )
        
        return {
            "success": True,
            "schedule_id": str(schedule.id),
            "agent_schedule_id": schedule_id,
            "scheduled_time": request.send_time.isoformat(),
            "message": f"Message scheduled for {request.send_time}"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to schedule message: {str(e)}")

# Message Management Endpoints

@router.get("/messages")
async def get_messages(
    limit: int = Query(50, description="Number of messages to return"),
    offset: int = Query(0, description="Number of messages to skip"),
    status: Optional[str] = Query(None, description="Filter by message status"),
    communication_type: Optional[str] = Query(None, description="Filter by communication type"),
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    interview_id: Optional[str] = Query(None, description="Filter by interview ID"),
    start_date: Optional[datetime] = Query(None, description="Filter messages after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter messages before this date"),
    db: Session = Depends(get_db)
):
    """
    Get communication messages with filtering and pagination
    
    Returns a list of messages with optional filtering by various criteria.
    """
    try:
        # Build query
        query = db.query(CommunicationMessage)
        
        # Apply filters
        if status:
            query = query.filter(CommunicationMessage.status == status)
        
        if communication_type:
            query = query.filter(CommunicationMessage.communication_type == communication_type)
        
        if candidate_id:
            query = query.filter(CommunicationMessage.candidate_id == uuid.UUID(candidate_id))
        
        if interview_id:
            query = query.filter(CommunicationMessage.interview_id == uuid.UUID(interview_id))
        
        if start_date:
            query = query.filter(CommunicationMessage.created_at >= start_date)
        
        if end_date:
            query = query.filter(CommunicationMessage.created_at <= end_date)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        messages = query.order_by(desc(CommunicationMessage.created_at))\
                       .offset(offset)\
                       .limit(limit)\
                       .all()
        
        return {
            "messages": [message.to_dict() for message in messages],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get messages: {str(e)}")

@router.get("/messages/{message_id}")
async def get_message(message_id: str, db: Session = Depends(get_db)):
    """Get a specific message by ID"""
    try:
        message = db.query(CommunicationMessage)\
                   .filter(CommunicationMessage.id == uuid.UUID(message_id))\
                   .first()
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return message.to_dict()
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get message: {str(e)}")

@router.put("/messages/{message_id}/retry")
async def retry_message(message_id: str, db: Session = Depends(get_db)):
    """Retry sending a failed message"""
    try:
        message = db.query(CommunicationMessage)\
                   .filter(CommunicationMessage.id == uuid.UUID(message_id))\
                   .first()
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        if not message.can_retry:
            raise HTTPException(
                status_code=400, 
                detail="Message cannot be retried (not failed or max retries reached)"
            )
        
        agent = get_communication_agent()
        
        # Retry based on communication type
        if message.communication_type == CommunicationType.EMAIL:
            result = await agent.send_email(
                to_email=message.to_email,
                subject=message.subject,
                body=message.body,
                html_body=message.html_body,
                cc_emails=message.cc_emails,
                priority=message.priority
            )
        elif message.communication_type == CommunicationType.SMS:
            result = await agent.send_sms(
                to_phone=message.to_phone,
                message=message.body,
                priority=message.priority
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported communication type for retry: {message.communication_type}"
            )
        
        # Update message record
        message.retry_count += 1
        message.last_retry_at = datetime.utcnow()
        message.status = CommunicationStatus.SENT if result.success else CommunicationStatus.FAILED
        
        if result.success:
            message.sent_at = datetime.utcnow()
            message.external_message_id = result.external_id
            message.error_message = None
            message.error_code = None
        else:
            message.failed_at = datetime.utcnow()
            message.error_message = result.error_message
            message.error_code = result.error_code
        
        db.commit()
        
        return {
            "success": result.success,
            "message": "Message retry completed",
            "retry_count": message.retry_count,
            "status": message.status,
            "error_message": result.error_message if not result.success else None
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message ID format")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to retry message: {str(e)}")

# Template Management Endpoints

@router.get("/templates")
async def get_templates(
    category: Optional[str] = Query(None, description="Filter by template category"),
    communication_type: Optional[str] = Query(None, description="Filter by communication type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db)
):
    """Get message templates with optional filtering"""
    try:
        query = db.query(MessageTemplate)
        
        if category:
            query = query.filter(MessageTemplate.category == category)
        
        if communication_type:
            query = query.filter(MessageTemplate.communication_type == communication_type)
        
        if is_active is not None:
            query = query.filter(MessageTemplate.is_active == is_active)
        
        templates = query.order_by(MessageTemplate.name).all()
        
        return {
            "templates": [template.to_dict() for template in templates],
            "total": len(templates)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get templates: {str(e)}")

@router.post("/templates")
async def create_template(template: MessageTemplateCreate, db: Session = Depends(get_db)):
    """Create a new message template"""
    try:
        # Check if template name already exists
        existing = db.query(MessageTemplate)\
                    .filter(MessageTemplate.name == template.name)\
                    .first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Template with name '{template.name}' already exists"
            )
        
        # Create template
        db_template = MessageTemplate(
            name=template.name,
            category=template.category,
            communication_type=template.communication_type,
            subject_template=template.subject_template,
            body_template=template.body_template,
            html_template=template.html_template,
            required_variables=template.required_variables,
            optional_variables=template.optional_variables,
            default_values=template.default_values,
            description=template.description,
            language=template.language,
            created_by="api"
        )
        
        db.add(db_template)
        db.commit()
        db.refresh(db_template)
        
        return {
            "success": True,
            "template_id": str(db_template.id),
            "message": "Template created successfully",
            "template": db_template.to_dict()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")

# Agent Status Endpoint

@router.get("/agent/status")
async def get_agent_status():
    """Get Communication Agent status and configuration"""
    try:
        agent = get_communication_agent()
        return agent.get_agent_status()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {str(e)}")

@router.get("/health")
async def health_check():
    """Health check endpoint for Communication API"""
    try:
        agent = get_communication_agent()
        agent_status = agent.get_agent_status()
        
        return {
            "status": "healthy",
            "service": "Communication API",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_status": agent_status["status"],
            "email_configured": agent_status["email_configured"],
            "ai_enabled": agent_status["ai_enabled"]
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "Communication API",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        } 