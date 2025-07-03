"""
RecruitAI Pro Scheduler API
RESTful endpoints for intelligent interview scheduling and calendar management
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import uuid
import logging

from core.database import get_db
from agents.scheduler import scheduler_agent, SchedulingRequest, SchedulingPriority, SchedulingStrategy, InterviewType
from models.interviews import Interview, AvailabilitySlot, CalendarIntegration, SchedulingLog, InterviewStatus
from models.candidates import Candidate
from models.jobs import JobPosition

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/scheduler", tags=["scheduler"])

# Pydantic models for request/response

class ScheduleInterviewRequest(BaseModel):
    """Request model for scheduling interviews"""
    candidate_id: str = Field(..., description="ID of the candidate")
    job_position_id: str = Field(..., description="ID of the job position")
    interview_type: str = Field(..., description="Type of interview")
    interviewer_emails: List[str] = Field(..., description="List of interviewer emails")
    duration_minutes: int = Field(60, ge=15, le=480, description="Interview duration in minutes")
    earliest_start: Optional[datetime] = Field(None, description="Earliest possible start time")
    latest_end: Optional[datetime] = Field(None, description="Latest possible end time")
    timezone: str = Field("UTC", description="Timezone for the interview")
    priority: str = Field("medium", description="Scheduling priority")
    strategy: str = Field("balanced", description="Scheduling strategy")
    preferred_times: List[Dict] = Field([], description="Preferred time slots")
    requirements: Dict = Field({}, description="Additional requirements")
    
    @validator('interview_type')
    def validate_interview_type(cls, v):
        valid_types = [t.value for t in InterviewType]
        if v not in valid_types:
            raise ValueError(f"Invalid interview type. Must be one of: {valid_types}")
        return v
    
    @validator('priority')
    def validate_priority(cls, v):
        valid_priorities = [p.value for p in SchedulingPriority]
        if v not in valid_priorities:
            raise ValueError(f"Invalid priority. Must be one of: {valid_priorities}")
        return v
    
    @validator('strategy')
    def validate_strategy(cls, v):
        valid_strategies = [s.value for s in SchedulingStrategy]
        if v not in valid_strategies:
            raise ValueError(f"Invalid strategy. Must be one of: {valid_strategies}")
        return v

class RescheduleInterviewRequest(BaseModel):
    """Request model for rescheduling interviews"""
    reason: str = Field(..., description="Reason for rescheduling")
    new_earliest_start: Optional[datetime] = Field(None, description="New earliest start time")
    new_latest_end: Optional[datetime] = Field(None, description="New latest end time")
    new_interviewer_emails: Optional[List[str]] = Field(None, description="Updated interviewer emails")
    new_duration_minutes: Optional[int] = Field(None, ge=15, le=480, description="Updated duration")
    priority: str = Field("high", description="Rescheduling priority")

class AvailabilitySlotRequest(BaseModel):
    """Request model for availability slots"""
    email: str = Field(..., description="User email")
    user_type: str = Field(..., description="Type of user (interviewer, candidate)")
    start_time: datetime = Field(..., description="Start time of availability slot")
    end_time: datetime = Field(..., description="End time of availability slot")
    availability_type: str = Field(..., description="Type of availability (available, busy)")
    timezone: str = Field("UTC", description="Timezone")
    recurring: bool = Field(False, description="Is this a recurring slot")
    recurrence_pattern: Optional[Dict] = Field(None, description="Recurrence pattern")
    notes: Optional[str] = Field(None, description="Additional notes")
    priority: int = Field(0, description="Priority level")

class CalendarIntegrationRequest(BaseModel):
    """Request model for calendar integration setup"""
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User name")
    user_type: str = Field(..., description="Type of user")
    provider: str = Field(..., description="Calendar provider")
    working_hours_start: str = Field("09:00", description="Working hours start time")
    working_hours_end: str = Field("17:00", description="Working hours end time")
    working_days: List[str] = Field(["monday", "tuesday", "wednesday", "thursday", "friday"], description="Working days")
    timezone: str = Field("UTC", description="User timezone")
    sync_enabled: bool = Field(True, description="Enable calendar sync")

class ConflictCheckRequest(BaseModel):
    """Request model for conflict checking"""
    start_time: datetime = Field(..., description="Start time to check")
    end_time: datetime = Field(..., description="End time to check")
    participant_emails: List[str] = Field(..., description="List of participant emails")

# API Endpoints

@router.post("/schedule", response_model=Dict[str, Any])
async def schedule_interview(
    request: ScheduleInterviewRequest,
    db: Session = Depends(get_db)
):
    """
    🗓️ Schedule a new interview using AI-powered optimization
    
    This endpoint finds the optimal time slot for an interview based on:
    - Participant availability
    - Scheduling preferences
    - Conflict detection
    - Multi-criteria optimization
    """
    try:
        logger.info(f"📅 Scheduling interview for candidate {request.candidate_id}")
        
        # Convert request to internal format
        scheduling_request = SchedulingRequest(
            candidate_id=request.candidate_id,
            job_position_id=request.job_position_id,
            interview_type=InterviewType(request.interview_type),
            interviewer_emails=request.interviewer_emails,
            duration_minutes=request.duration_minutes,
            earliest_start=request.earliest_start or (datetime.utcnow() + timedelta(hours=24)),
            latest_end=request.latest_end or (datetime.utcnow() + timedelta(days=30)),
            timezone=request.timezone,
            priority=SchedulingPriority(request.priority),
            strategy=SchedulingStrategy(request.strategy),
            preferred_times=request.preferred_times,
            requirements=request.requirements
        )
        
        # Schedule the interview
        result = await scheduler_agent.schedule_interview(scheduling_request, db)
        
        if result['success']:
            logger.info(f"✅ Successfully scheduled interview {result['interview']['id']}")
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": "Interview scheduled successfully",
                    "data": result
                }
            )
        else:
            logger.warning(f"⚠️ Scheduling failed: {result['errors']}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Failed to schedule interview",
                    "errors": result['errors']
                }
            )
            
    except Exception as e:
        logger.error(f"❌ Error scheduling interview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/interviews/{interview_id}/reschedule", response_model=Dict[str, Any])
async def reschedule_interview(
    interview_id: str,
    request: RescheduleInterviewRequest,
    db: Session = Depends(get_db)
):
    """
    🔄 Reschedule an existing interview
    
    Finds a new optimal time slot for an existing interview while:
    - Maintaining interview context
    - Updating participants if needed
    - Logging reschedule reasons
    - Sending notifications
    """
    try:
        logger.info(f"🔄 Rescheduling interview {interview_id}")
        
        # Get existing interview
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        # Create new scheduling request if parameters are provided
        new_request = None
        if any([request.new_earliest_start, request.new_latest_end, 
                request.new_interviewer_emails, request.new_duration_minutes]):
            new_request = SchedulingRequest(
                candidate_id=str(interview.candidate_id),
                job_position_id=str(interview.job_position_id),
                interview_type=InterviewType(interview.interview_type),
                interviewer_emails=request.new_interviewer_emails or interview.interviewer_emails,
                duration_minutes=request.new_duration_minutes or interview.duration_minutes,
                earliest_start=request.new_earliest_start or (datetime.utcnow() + timedelta(hours=24)),
                latest_end=request.new_latest_end or (datetime.utcnow() + timedelta(days=30)),
                timezone=interview.timezone,
                priority=SchedulingPriority(request.priority)
            )
        
        # Reschedule the interview
        result = await scheduler_agent.reschedule_interview(
            interview_id, 
            request.reason, 
            new_request, 
            db
        )
        
        if result['success']:
            logger.info(f"✅ Successfully rescheduled interview {interview_id}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Interview rescheduled successfully",
                    "data": result
                }
            )
        else:
            logger.warning(f"⚠️ Rescheduling failed: {result['errors']}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Failed to reschedule interview",
                    "errors": result['errors']
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error rescheduling interview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/interviews", response_model=Dict[str, Any])
async def get_interviews(
    status: Optional[str] = Query(None, description="Filter by interview status"),
    interviewer_email: Optional[str] = Query(None, description="Filter by interviewer email"),
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    start_date: Optional[datetime] = Query(None, description="Filter from start date"),
    end_date: Optional[datetime] = Query(None, description="Filter to end date"),
    limit: int = Query(50, ge=1, le=100, description="Number of interviews to return"),
    offset: int = Query(0, ge=0, description="Number of interviews to skip"),
    db: Session = Depends(get_db)
):
    """
    📋 Get interviews with filtering and pagination
    
    Retrieve interviews based on various filters:
    - Status (scheduled, confirmed, completed, etc.)
    - Interviewer email
    - Candidate ID
    - Date range
    """
    try:
        query = db.query(Interview)
        
        # Apply filters
        if status:
            query = query.filter(Interview.status == status)
        
        if interviewer_email:
            query = query.filter(Interview.interviewer_emails.contains([interviewer_email]))
        
        if candidate_id:
            query = query.filter(Interview.candidate_id == candidate_id)
        
        if start_date:
            query = query.filter(Interview.scheduled_start >= start_date)
        
        if end_date:
            query = query.filter(Interview.scheduled_start <= end_date)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and ordering
        interviews = query.order_by(Interview.scheduled_start.desc()).offset(offset).limit(limit).all()
        
        # Convert to dictionaries
        interview_data = [interview.to_dict() for interview in interviews]
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "interviews": interview_data,
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total_count
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error fetching interviews: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/interviews/{interview_id}", response_model=Dict[str, Any])
async def get_interview(
    interview_id: str,
    db: Session = Depends(get_db)
):
    """
    📄 Get detailed information about a specific interview
    """
    try:
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        # Get related candidate and job information
        candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
        job = db.query(JobPosition).filter(JobPosition.id == interview.job_position_id).first()
        
        # Get scheduling logs for this interview
        logs = db.query(SchedulingLog).filter(
            SchedulingLog.interview_id == interview_id
        ).order_by(SchedulingLog.created_at.desc()).limit(10).all()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "interview": interview.to_dict(),
                    "candidate": candidate.to_dict() if candidate else None,
                    "job": job.to_dict() if job else None,
                    "scheduling_logs": [
                        {
                            "action_type": log.action_type,
                            "action_status": log.action_status,
                            "created_at": log.created_at.isoformat(),
                            "processing_time_ms": log.processing_time_ms,
                            "slots_evaluated": log.slots_evaluated
                        } for log in logs
                    ]
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching interview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/conflicts/check", response_model=Dict[str, Any])
async def check_conflicts(
    request: ConflictCheckRequest,
    db: Session = Depends(get_db)
):
    """
    ⚠️ Check for scheduling conflicts at a specific time
    
    Analyze potential conflicts for a given time slot and participants:
    - Existing interviews
    - Busy calendar slots
    - Availability preferences
    """
    try:
        conflicts = await scheduler_agent.detect_conflicts(
            request.start_time,
            request.end_time,
            request.participant_emails,
            db
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "has_conflicts": bool(conflicts),
                    "conflicts": conflicts,
                    "conflict_summary": {
                        "total_conflicts": sum(len(emails) for emails in conflicts.values()),
                        "affected_participants": len(conflicts),
                        "available_participants": [
                            email for email in request.participant_emails 
                            if email not in conflicts
                        ]
                    }
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error checking conflicts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/availability", response_model=Dict[str, Any])
async def create_availability_slot(
    request: AvailabilitySlotRequest,
    db: Session = Depends(get_db)
):
    """
    ✅ Create an availability slot for a user
    
    Define when someone is available or busy for scheduling:
    - Available time slots
    - Busy/blocked time slots
    - Recurring patterns
    - Priority levels
    """
    try:
        # Create availability slot
        availability_slot = AvailabilitySlot(
            email=request.email,
            user_type=request.user_type,
            start_time=request.start_time,
            end_time=request.end_time,
            timezone=request.timezone,
            availability_type=request.availability_type,
            recurring=request.recurring,
            recurrence_pattern=request.recurrence_pattern,
            notes=request.notes,
            priority=request.priority,
            source="manual"
        )
        
        db.add(availability_slot)
        db.commit()
        db.refresh(availability_slot)
        
        logger.info(f"✅ Created availability slot for {request.email}")
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Availability slot created successfully",
                "data": {
                    "availability_slot": availability_slot.to_dict()
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error creating availability slot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/availability/{email}", response_model=Dict[str, Any])
async def get_availability(
    email: str,
    start_date: Optional[datetime] = Query(None, description="Start date for availability"),
    end_date: Optional[datetime] = Query(None, description="End date for availability"),
    db: Session = Depends(get_db)
):
    """
    📅 Get availability information for a user
    
    Retrieve availability slots and calendar integration status:
    - Available time slots
    - Busy time slots
    - Calendar sync status
    - Working hours preferences
    """
    try:
        # Set default date range if not provided
        if not start_date:
            start_date = datetime.utcnow()
        if not end_date:
            end_date = start_date + timedelta(days=30)
        
        # Get availability slots
        query = db.query(AvailabilitySlot).filter(AvailabilitySlot.email == email)
        
        if start_date:
            query = query.filter(AvailabilitySlot.start_time >= start_date)
        if end_date:
            query = query.filter(AvailabilitySlot.start_time <= end_date)
        
        availability_slots = query.order_by(AvailabilitySlot.start_time).all()
        
        # Get calendar integration
        calendar_integration = db.query(CalendarIntegration).filter(
            CalendarIntegration.email == email
        ).first()
        
        # Get availability summary
        availability_summary = await scheduler_agent.get_availability_summary(
            [email], start_date, end_date, db
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "email": email,
                    "availability_slots": [slot.to_dict() for slot in availability_slots],
                    "calendar_integration": calendar_integration.to_dict() if calendar_integration else None,
                    "summary": availability_summary.get(email, {}),
                    "date_range": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    }
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error fetching availability: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/calendar-integration", response_model=Dict[str, Any])
async def setup_calendar_integration(
    request: CalendarIntegrationRequest,
    db: Session = Depends(get_db)
):
    """
    🔗 Set up calendar integration for a user
    
    Configure calendar integration settings:
    - Calendar provider (Google, Outlook, etc.)
    - Working hours and days
    - Sync preferences
    - Timezone settings
    """
    try:
        # Check if integration already exists
        existing_integration = db.query(CalendarIntegration).filter(
            CalendarIntegration.email == request.email
        ).first()
        
        if existing_integration:
            # Update existing integration
            existing_integration.name = request.name
            existing_integration.user_type = request.user_type
            existing_integration.provider = request.provider
            existing_integration.working_hours_start = request.working_hours_start
            existing_integration.working_hours_end = request.working_hours_end
            existing_integration.working_days = request.working_days
            existing_integration.timezone = request.timezone
            existing_integration.sync_enabled = request.sync_enabled
            
            db.commit()
            db.refresh(existing_integration)
            
            calendar_integration = existing_integration
            action = "updated"
        else:
            # Create new integration
            calendar_integration = CalendarIntegration(
                email=request.email,
                name=request.name,
                user_type=request.user_type,
                provider=request.provider,
                working_hours_start=request.working_hours_start,
                working_hours_end=request.working_hours_end,
                working_days=request.working_days,
                timezone=request.timezone,
                sync_enabled=request.sync_enabled,
                connected_at=datetime.utcnow()
            )
            
            db.add(calendar_integration)
            db.commit()
            db.refresh(calendar_integration)
            
            action = "created"
        
        logger.info(f"✅ Calendar integration {action} for {request.email}")
        
        return JSONResponse(
            status_code=201 if action == "created" else 200,
            content={
                "success": True,
                "message": f"Calendar integration {action} successfully",
                "data": {
                    "calendar_integration": calendar_integration.to_dict()
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error setting up calendar integration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/optimal-slots", response_model=Dict[str, Any])
async def find_optimal_slots(
    candidate_id: str = Query(..., description="Candidate ID"),
    job_position_id: str = Query(..., description="Job position ID"),
    interview_type: str = Query(..., description="Interview type"),
    interviewer_emails: List[str] = Query(..., description="Interviewer emails"),
    duration_minutes: int = Query(60, ge=15, le=480, description="Duration in minutes"),
    max_slots: int = Query(10, ge=1, le=20, description="Maximum slots to return"),
    earliest_start: Optional[datetime] = Query(None, description="Earliest start time"),
    latest_end: Optional[datetime] = Query(None, description="Latest end time"),
    db: Session = Depends(get_db)
):
    """
    🎯 Find optimal time slots for an interview without scheduling
    
    Analyze and return the best possible time slots based on:
    - Participant availability
    - Optimization criteria
    - Conflict analysis
    - Scoring algorithms
    """
    try:
        # Create scheduling request
        scheduling_request = SchedulingRequest(
            candidate_id=candidate_id,
            job_position_id=job_position_id,
            interview_type=InterviewType(interview_type),
            interviewer_emails=interviewer_emails,
            duration_minutes=duration_minutes,
            earliest_start=earliest_start or (datetime.utcnow() + timedelta(hours=24)),
            latest_end=latest_end or (datetime.utcnow() + timedelta(days=30))
        )
        
        # Find optimal slots
        optimal_slots = await scheduler_agent.find_optimal_slots(
            scheduling_request, max_slots, db
        )
        
        # Convert to response format
        slots_data = []
        for slot in optimal_slots:
            slots_data.append({
                "start_time": slot.start_time.isoformat(),
                "end_time": slot.end_time.isoformat(),
                "score": round(slot.score, 3),
                "conflicts": slot.conflicts,
                "participants_available": slot.participants_available,
                "participants_unavailable": slot.participants_unavailable,
                "reasons": slot.reasons
            })
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "optimal_slots": slots_data,
                    "request_parameters": {
                        "candidate_id": candidate_id,
                        "job_position_id": job_position_id,
                        "interview_type": interview_type,
                        "interviewer_emails": interviewer_emails,
                        "duration_minutes": duration_minutes,
                        "earliest_start": scheduling_request.earliest_start.isoformat(),
                        "latest_end": scheduling_request.latest_end.isoformat()
                    },
                    "analysis": {
                        "total_slots_found": len(optimal_slots),
                        "best_score": optimal_slots[0].score if optimal_slots else 0,
                        "has_conflict_free_slots": any(not slot.conflicts for slot in optimal_slots)
                    }
                }
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error finding optimal slots: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/analytics/scheduling", response_model=Dict[str, Any])
async def get_scheduling_analytics(
    start_date: Optional[datetime] = Query(None, description="Analytics start date"),
    end_date: Optional[datetime] = Query(None, description="Analytics end date"),
    db: Session = Depends(get_db)
):
    """
    📊 Get scheduling analytics and performance metrics
    
    Retrieve insights about scheduling performance:
    - Success rates
    - Average processing times
    - Conflict patterns
    - Optimization effectiveness
    """
    try:
        # Set default date range
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Get scheduling logs
        logs = db.query(SchedulingLog).filter(
            SchedulingLog.created_at >= start_date,
            SchedulingLog.created_at <= end_date
        ).all()
        
        # Calculate analytics
        total_requests = len(logs)
        successful_schedules = len([log for log in logs if log.action_status == "success" and log.action_type == "schedule"])
        failed_schedules = len([log for log in logs if log.action_status == "failed" and log.action_type == "schedule"])
        reschedules = len([log for log in logs if log.action_type == "reschedule"])
        
        # Processing time statistics
        processing_times = [log.processing_time_ms for log in logs if log.processing_time_ms]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        # Slots evaluation statistics
        slots_evaluated = [log.slots_evaluated for log in logs if log.slots_evaluated]
        avg_slots_evaluated = sum(slots_evaluated) / len(slots_evaluated) if slots_evaluated else 0
        
        # Success scores
        success_scores = [log.success_score for log in logs if log.success_score]
        avg_success_score = sum(success_scores) / len(success_scores) if success_scores else 0
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "date_range": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    },
                    "summary": {
                        "total_requests": total_requests,
                        "successful_schedules": successful_schedules,
                        "failed_schedules": failed_schedules,
                        "reschedules": reschedules,
                        "success_rate": round(successful_schedules / max(1, successful_schedules + failed_schedules) * 100, 2)
                    },
                    "performance": {
                        "avg_processing_time_ms": round(avg_processing_time, 2),
                        "avg_slots_evaluated": round(avg_slots_evaluated, 2),
                        "avg_success_score": round(avg_success_score, 3)
                    },
                    "trends": {
                        "daily_schedules": {},  # Could be implemented for daily trends
                        "common_algorithms": {},  # Could be implemented for algorithm usage
                        "peak_hours": {}  # Could be implemented for peak scheduling times
                    }
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error fetching scheduling analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Health check endpoint
@router.get("/health")
async def health_check():
    """🏥 Health check for scheduler service"""
    return {
        "status": "healthy",
        "service": "scheduler",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    } 