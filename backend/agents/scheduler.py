"""
RecruitAI Pro Scheduler Agent
Intelligent interview scheduling with AI-powered optimization, conflict detection, and calendar integration
"""

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass
from enum import Enum
import json
import pytz
from operator import itemgetter

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc

from core.ai_clients import ai_client
from core.message_broker import message_broker
from core.database import get_db
from models.interviews import (
    Interview, AvailabilitySlot, CalendarIntegration, SchedulingLog,
    InterviewStatus, InterviewType
)
from models.candidates import Candidate
from models.jobs import JobPosition

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SchedulingPriority(str, Enum):
    """Priority levels for scheduling requests"""
    URGENT = "urgent"          # < 24 hours
    HIGH = "high"             # 1-3 days
    MEDIUM = "medium"         # 3-7 days
    LOW = "low"              # > 7 days

class SchedulingStrategy(str, Enum):
    """Different scheduling strategies"""
    OPTIMIZE_TIME = "optimize_time"           # Find earliest possible slot
    OPTIMIZE_QUALITY = "optimize_quality"     # Best interviewer availability
    OPTIMIZE_CANDIDATE = "optimize_candidate" # Candidate preference first
    BALANCED = "balanced"                     # Balance all factors

@dataclass
class TimeSlot:
    """Represents a potential time slot for an interview"""
    start_time: datetime
    end_time: datetime
    score: float = 0.0
    conflicts: List[str] = None
    participants_available: List[str] = None
    participants_unavailable: List[str] = None
    reasons: List[str] = None
    
    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []
        if self.participants_available is None:
            self.participants_available = []
        if self.participants_unavailable is None:
            self.participants_unavailable = []
        if self.reasons is None:
            self.reasons = []

@dataclass
class SchedulingRequest:
    """Request for scheduling an interview"""
    candidate_id: str
    job_position_id: str
    interview_type: InterviewType
    interviewer_emails: List[str]
    duration_minutes: int = 60
    preferred_times: List[Dict] = None
    earliest_start: datetime = None
    latest_end: datetime = None
    timezone: str = "UTC"
    priority: SchedulingPriority = SchedulingPriority.MEDIUM
    strategy: SchedulingStrategy = SchedulingStrategy.BALANCED
    requirements: Dict = None
    
    def __post_init__(self):
        if self.preferred_times is None:
            self.preferred_times = []
        if self.requirements is None:
            self.requirements = {}
        if self.earliest_start is None:
            self.earliest_start = datetime.utcnow() + timedelta(hours=24)
        if self.latest_end is None:
            self.latest_end = datetime.utcnow() + timedelta(days=30)

class SchedulerAgent:
    """
    Advanced AI-powered interview scheduling agent
    
    Features:
    - Smart conflict detection and resolution
    - Multi-criteria optimization (time, quality, preferences)
    - Calendar integration and sync
    - Automatic rescheduling with intelligent suggestions
    - Learning from scheduling patterns for continuous improvement
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("🗓️ Initializing Scheduler Agent...")
        
        # Scheduling parameters
        self.working_hours_start = time(9, 0)  # 9:00 AM
        self.working_hours_end = time(17, 0)   # 5:00 PM
        self.working_days = [0, 1, 2, 3, 4]    # Monday to Friday
        self.buffer_minutes = 15               # Buffer between meetings
        self.max_daily_interviews = 6          # Per interviewer
        self.min_prep_time_hours = 2           # Minimum prep time
        
        # Scoring weights for slot optimization
        self.scoring_weights = {
            'time_preference': 0.3,      # How well it matches preferred times
            'availability_quality': 0.25, # Quality of participant availability
            'interviewer_workload': 0.2,  # Interviewer's daily load
            'candidate_convenience': 0.15, # Convenience for candidate
            'urgency_factor': 0.1         # Priority/urgency bonus
        }
        
        # Calendar integration status
        self.calendar_providers = {}
        
        self.logger.info("✅ Scheduler Agent initialized successfully")
    
    async def schedule_interview(
        self, 
        request: SchedulingRequest, 
        db: Session
    ) -> Dict[str, Any]:
        """
        Main scheduling function - finds optimal time slot for interview
        
        Args:
            request: Scheduling request with all parameters
            db: Database session
            
        Returns:
            Dictionary with scheduling result and metadata
        """
        start_time = datetime.utcnow()
        self.logger.info(f"🔍 Processing scheduling request for candidate {request.candidate_id}")
        
        try:
            # Step 1: Validate request
            validation_result = await self._validate_request(request, db)
            if not validation_result['valid']:
                return self._create_error_response(
                    "validation_failed", 
                    validation_result['errors']
                )
            
            # Step 2: Get availability for all participants
            availability_data = await self._gather_availability(request, db)
            
            # Step 3: Generate candidate time slots
            candidate_slots = await self._generate_candidate_slots(
                request, 
                availability_data, 
                db
            )
            
            if not candidate_slots:
                return self._create_error_response(
                    "no_slots_available",
                    ["No suitable time slots found for the given constraints"]
                )
            
            # Step 4: Score and rank slots
            scored_slots = await self._score_and_rank_slots(
                candidate_slots, 
                request, 
                availability_data,
                db
            )
            
            # Step 5: Select best slot
            best_slot = scored_slots[0]
            
            # Step 6: Create interview record
            interview = await self._create_interview(best_slot, request, db)
            
            # Step 7: Log scheduling decision
            await self._log_scheduling_activity(
                interview.id,
                "schedule",
                "success",
                {
                    'slots_evaluated': len(candidate_slots),
                    'processing_time_ms': int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    'best_score': best_slot.score,
                    'algorithm': request.strategy,
                    'alternatives': [
                        {
                            'start': slot.start_time.isoformat(),
                            'score': slot.score,
                            'reasons': slot.reasons
                        } for slot in scored_slots[1:min(4, len(scored_slots))]
                    ]
                },
                db
            )
            
            # Step 8: Send notifications (if message broker available)
            await self._send_scheduling_notifications(interview, best_slot, db)
            
            self.logger.info(f"✅ Successfully scheduled interview {interview.id}")
            
            return {
                'success': True,
                'interview': interview.to_dict(),
                'slot_details': {
                    'score': best_slot.score,
                    'conflicts': best_slot.conflicts,
                    'reasons': best_slot.reasons,
                    'participants_available': best_slot.participants_available
                },
                'alternatives': [
                    {
                        'start_time': slot.start_time.isoformat(),
                        'end_time': slot.end_time.isoformat(),
                        'score': slot.score,
                        'reasons': slot.reasons[:3]  # Top 3 reasons
                    } for slot in scored_slots[1:4]  # Next 3 best alternatives
                ],
                'metadata': {
                    'slots_evaluated': len(candidate_slots),
                    'processing_time_ms': int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    'strategy_used': request.strategy
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ Scheduling failed: {str(e)}")
            
            # Log the error
            await self._log_scheduling_activity(
                None,
                "schedule",
                "failed",
                {'error': str(e)},
                db
            )
            
            return self._create_error_response("scheduling_error", [str(e)])
    
    async def reschedule_interview(
        self,
        interview_id: str,
        reason: str,
        new_request: Optional[SchedulingRequest] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Reschedule an existing interview
        
        Args:
            interview_id: ID of interview to reschedule
            reason: Reason for rescheduling
            new_request: New scheduling parameters (optional)
            db: Database session
            
        Returns:
            Rescheduling result
        """
        self.logger.info(f"🔄 Rescheduling interview {interview_id}")
        
        try:
            # Get existing interview
            interview = db.query(Interview).filter(Interview.id == interview_id).first()
            if not interview:
                return self._create_error_response("interview_not_found", ["Interview not found"])
            
            # Check if can reschedule
            if not interview.can_reschedule:
                return self._create_error_response(
                    "cannot_reschedule", 
                    ["Interview cannot be rescheduled (too many attempts or not upcoming)"]
                )
            
            # Create new scheduling request based on existing interview
            if new_request is None:
                new_request = SchedulingRequest(
                    candidate_id=str(interview.candidate_id),
                    job_position_id=str(interview.job_position_id),
                    interview_type=InterviewType(interview.interview_type),
                    interviewer_emails=interview.interviewer_emails,
                    duration_minutes=interview.duration_minutes,
                    timezone=interview.timezone,
                    priority=SchedulingPriority.HIGH  # Higher priority for rescheduling
                )
            
            # Schedule new interview
            scheduling_result = await self.schedule_interview(new_request, db)
            
            if scheduling_result['success']:
                # Update original interview
                interview.status = InterviewStatus.RESCHEDULED
                interview.reschedule_count += 1
                interview.reschedule_reason = reason
                
                # Update new interview to reference original
                new_interview = db.query(Interview).filter(
                    Interview.id == scheduling_result['interview']['id']
                ).first()
                new_interview.original_interview_id = interview.id
                
                db.commit()
                
                self.logger.info(f"✅ Successfully rescheduled interview {interview_id}")
                
                return {
                    'success': True,
                    'original_interview_id': interview_id,
                    'new_interview': scheduling_result['interview'],
                    'reschedule_reason': reason,
                    'reschedule_count': interview.reschedule_count
                }
            else:
                return scheduling_result
                
        except Exception as e:
            self.logger.error(f"❌ Rescheduling failed: {str(e)}")
            return self._create_error_response("rescheduling_error", [str(e)])
    
    async def find_optimal_slots(
        self,
        request: SchedulingRequest,
        max_slots: int = 10,
        db: Session = None
    ) -> List[TimeSlot]:
        """
        Find optimal time slots without creating interview
        
        Args:
            request: Scheduling request
            max_slots: Maximum number of slots to return
            db: Database session
            
        Returns:
            List of optimal time slots
        """
        try:
            # Get availability for all participants
            availability_data = await self._gather_availability(request, db)
            
            # Generate candidate slots
            candidate_slots = await self._generate_candidate_slots(
                request, 
                availability_data, 
                db
            )
            
            # Score and rank slots
            scored_slots = await self._score_and_rank_slots(
                candidate_slots, 
                request, 
                availability_data,
                db
            )
            
            return scored_slots[:max_slots]
            
        except Exception as e:
            self.logger.error(f"❌ Finding optimal slots failed: {str(e)}")
            return []
    
    async def detect_conflicts(
        self,
        start_time: datetime,
        end_time: datetime,
        participant_emails: List[str],
        db: Session
    ) -> Dict[str, List[str]]:
        """
        Detect scheduling conflicts for given time and participants
        
        Args:
            start_time: Proposed start time
            end_time: Proposed end time
            participant_emails: List of participant emails
            db: Database session
            
        Returns:
            Dictionary of conflicts by participant
        """
        conflicts = {}
        
        for email in participant_emails:
            participant_conflicts = []
            
            # Check existing interviews
            existing_interviews = db.query(Interview).filter(
                and_(
                    Interview.interviewer_emails.contains([email]),
                    Interview.status.in_([InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED]),
                    or_(
                        and_(
                            Interview.scheduled_start <= start_time,
                            Interview.scheduled_end > start_time
                        ),
                        and_(
                            Interview.scheduled_start < end_time,
                            Interview.scheduled_end >= end_time
                        ),
                        and_(
                            Interview.scheduled_start >= start_time,
                            Interview.scheduled_end <= end_time
                        )
                    )
                )
            ).all()
            
            for interview in existing_interviews:
                participant_conflicts.append(
                    f"Existing interview: {interview.title} "
                    f"({interview.scheduled_start.strftime('%H:%M')}-{interview.scheduled_end.strftime('%H:%M')})"
                )
            
            # Check availability slots marked as busy
            busy_slots = db.query(AvailabilitySlot).filter(
                and_(
                    AvailabilitySlot.email == email,
                    AvailabilitySlot.availability_type == "busy",
                    or_(
                        and_(
                            AvailabilitySlot.start_time <= start_time,
                            AvailabilitySlot.end_time > start_time
                        ),
                        and_(
                            AvailabilitySlot.start_time < end_time,
                            AvailabilitySlot.end_time >= end_time
                        ),
                        and_(
                            AvailabilitySlot.start_time >= start_time,
                            AvailabilitySlot.end_time <= end_time
                        )
                    )
                )
            ).all()
            
            for slot in busy_slots:
                participant_conflicts.append(
                    f"Busy: {slot.notes or 'Unavailable'} "
                    f"({slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')})"
                )
            
            if participant_conflicts:
                conflicts[email] = participant_conflicts
        
        return conflicts
    
    async def get_availability_summary(
        self,
        emails: List[str],
        start_date: datetime,
        end_date: datetime,
        db: Session
    ) -> Dict[str, Dict]:
        """
        Get availability summary for participants over a date range
        
        Args:
            emails: List of participant emails
            start_date: Start of date range
            end_date: End of date range
            db: Database session
            
        Returns:
            Availability summary by participant
        """
        summary = {}
        
        for email in emails:
            # Get calendar integration
            integration = db.query(CalendarIntegration).filter(
                CalendarIntegration.email == email
            ).first()
            
            # Get existing interviews
            interviews = db.query(Interview).filter(
                and_(
                    Interview.interviewer_emails.contains([email]),
                    Interview.status.in_([InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED]),
                    Interview.scheduled_start >= start_date,
                    Interview.scheduled_start <= end_date
                )
            ).all()
            
            # Get availability slots
            slots = db.query(AvailabilitySlot).filter(
                and_(
                    AvailabilitySlot.email == email,
                    AvailabilitySlot.start_time >= start_date,
                    AvailabilitySlot.start_time <= end_date
                )
            ).all()
            
            summary[email] = {
                'has_calendar_integration': integration is not None,
                'integration_status': integration.integration_status if integration else 'none',
                'total_interviews': len(interviews),
                'busy_slots': len([s for s in slots if s.availability_type == 'busy']),
                'available_slots': len([s for s in slots if s.availability_type == 'available']),
                'working_hours': {
                    'start': integration.working_hours_start if integration else "09:00",
                    'end': integration.working_hours_end if integration else "17:00",
                    'days': integration.working_days if integration else ["monday", "tuesday", "wednesday", "thursday", "friday"]
                },
                'last_sync': integration.last_sync_at.isoformat() if integration and integration.last_sync_at else None
            }
        
        return summary
    
    # Private helper methods
    
    async def _validate_request(self, request: SchedulingRequest, db: Session) -> Dict[str, Any]:
        """Validate scheduling request"""
        errors = []
        
        # Check if candidate exists
        candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
        if not candidate:
            errors.append("Candidate not found")
        
        # Check if job position exists
        job = db.query(JobPosition).filter(JobPosition.id == request.job_position_id).first()
        if not job:
            errors.append("Job position not found")
        
        # Validate time constraints
        if request.earliest_start >= request.latest_end:
            errors.append("Earliest start time must be before latest end time")
        
        # Validate duration
        if request.duration_minutes < 15 or request.duration_minutes > 480:
            errors.append("Duration must be between 15 minutes and 8 hours")
        
        # Check interviewer emails
        if not request.interviewer_emails:
            errors.append("At least one interviewer email is required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'candidate': candidate.to_dict() if candidate else None,
            'job': job.to_dict() if job else None
        }
    
    async def _gather_availability(self, request: SchedulingRequest, db: Session) -> Dict[str, Any]:
        """Gather availability data for all participants"""
        # Get calendar integrations
        integrations = {}
        for email in request.interviewer_emails:
            integration = db.query(CalendarIntegration).filter(
                CalendarIntegration.email == email
            ).first()
            if integration:
                integrations[email] = integration
        
        # Get existing interviews for interviewers
        existing_interviews = db.query(Interview).filter(
            and_(
                Interview.status.in_([InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED]),
                Interview.scheduled_start >= request.earliest_start,
                Interview.scheduled_start <= request.latest_end
            )
        ).all()
        
        # Get availability slots
        availability_slots = db.query(AvailabilitySlot).filter(
            and_(
                AvailabilitySlot.email.in_(request.interviewer_emails),
                AvailabilitySlot.start_time >= request.earliest_start,
                AvailabilitySlot.start_time <= request.latest_end
            )
        ).all()
        
        return {
            'integrations': integrations,
            'existing_interviews': existing_interviews,
            'availability_slots': availability_slots,
            'request': request
        }
    
    async def _generate_candidate_slots(
        self, 
        request: SchedulingRequest, 
        availability_data: Dict, 
        db: Session
    ) -> List[TimeSlot]:
        """Generate all possible time slots for the interview"""
        slots = []
        current_time = request.earliest_start
        
        while current_time < request.latest_end:
            # Skip if outside working hours
            if not self._is_working_time(current_time):
                current_time += timedelta(minutes=30)
                continue
            
            # Calculate end time
            end_time = current_time + timedelta(minutes=request.duration_minutes)
            
            # Skip if end time is past latest allowed time
            if end_time > request.latest_end:
                break
            
            # Create time slot
            slot = TimeSlot(
                start_time=current_time,
                end_time=end_time
            )
            
            # Check for conflicts
            conflicts = await self.detect_conflicts(
                current_time,
                end_time,
                request.interviewer_emails,
                db
            )
            
            slot.conflicts = []
            slot.participants_unavailable = []
            for email, email_conflicts in conflicts.items():
                slot.conflicts.extend(email_conflicts)
                slot.participants_unavailable.append(email)
            
            slot.participants_available = [
                email for email in request.interviewer_emails 
                if email not in slot.participants_unavailable
            ]
            
            # Only add slots with at least one available participant
            if slot.participants_available:
                slots.append(slot)
            
            # Move to next slot (30-minute intervals)
            current_time += timedelta(minutes=30)
        
        return slots
    
    async def _score_and_rank_slots(
        self,
        slots: List[TimeSlot],
        request: SchedulingRequest,
        availability_data: Dict,
        db: Session
    ) -> List[TimeSlot]:
        """Score and rank time slots based on multiple criteria"""
        
        for slot in slots:
            score = 0.0
            reasons = []
            
            # 1. Time preference scoring (30%)
            time_score = self._score_time_preference(slot, request)
            score += time_score * self.scoring_weights['time_preference']
            if time_score > 0.7:
                reasons.append(f"Good time match (score: {time_score:.1f})")
            
            # 2. Availability quality scoring (25%)
            availability_score = self._score_availability_quality(slot, request, availability_data)
            score += availability_score * self.scoring_weights['availability_quality']
            if availability_score > 0.8:
                reasons.append("High availability quality")
            
            # 3. Interviewer workload scoring (20%)
            workload_score = self._score_interviewer_workload(slot, request, availability_data)
            score += workload_score * self.scoring_weights['interviewer_workload']
            if workload_score > 0.7:
                reasons.append("Good interviewer availability")
            
            # 4. Candidate convenience scoring (15%)
            convenience_score = self._score_candidate_convenience(slot, request)
            score += convenience_score * self.scoring_weights['candidate_convenience']
            if convenience_score > 0.8:
                reasons.append("Convenient for candidate")
            
            # 5. Urgency factor (10%)
            urgency_score = self._score_urgency_factor(slot, request)
            score += urgency_score * self.scoring_weights['urgency_factor']
            if urgency_score > 0.5:
                reasons.append("Meets urgency requirements")
            
            # Penalty for conflicts
            if slot.conflicts:
                score *= 0.7  # 30% penalty for conflicts
                reasons.append(f"Has {len(slot.conflicts)} conflicts")
            
            slot.score = score
            slot.reasons = reasons
        
        # Sort by score (descending)
        return sorted(slots, key=lambda x: x.score, reverse=True)
    
    def _score_time_preference(self, slot: TimeSlot, request: SchedulingRequest) -> float:
        """Score based on time preferences"""
        # Basic working hours score
        hour = slot.start_time.hour
        
        if 9 <= hour <= 11:      # Morning peak
            return 1.0
        elif 13 <= hour <= 15:   # Afternoon peak
            return 0.9
        elif 8 <= hour <= 17:    # Regular working hours
            return 0.7
        else:                    # Outside normal hours
            return 0.3
    
    def _score_availability_quality(self, slot: TimeSlot, request: SchedulingRequest, availability_data: Dict) -> float:
        """Score based on participant availability quality"""
        total_participants = len(request.interviewer_emails)
        available_participants = len(slot.participants_available)
        
        if available_participants == 0:
            return 0.0
        
        return available_participants / total_participants
    
    def _score_interviewer_workload(self, slot: TimeSlot, request: SchedulingRequest, availability_data: Dict) -> float:
        """Score based on interviewer workload for the day"""
        slot_date = slot.start_time.date()
        total_workload_score = 0.0
        
        for email in slot.participants_available:
            daily_interviews = 0
            for interview in availability_data.get('existing_interviews', []):
                if (email in interview.interviewer_emails and 
                    interview.scheduled_start.date() == slot_date):
                    daily_interviews += 1
            
            # Score based on daily workload (lower workload = higher score)
            if daily_interviews == 0:
                workload_score = 1.0
            elif daily_interviews <= 2:
                workload_score = 0.8
            elif daily_interviews <= 4:
                workload_score = 0.6
            else:
                workload_score = 0.3
            
            total_workload_score += workload_score
        
        return total_workload_score / len(slot.participants_available) if slot.participants_available else 0.0
    
    def _score_candidate_convenience(self, slot: TimeSlot, request: SchedulingRequest) -> float:
        """Score based on candidate convenience factors"""
        # Time zone considerations
        try:
            candidate_tz = pytz.timezone(request.timezone)
            slot_in_candidate_tz = slot.start_time.astimezone(candidate_tz)
            candidate_hour = slot_in_candidate_tz.hour
            
            # Prefer business hours in candidate's timezone
            if 9 <= candidate_hour <= 17:
                return 1.0
            elif 8 <= candidate_hour <= 18:
                return 0.8
            else:
                return 0.4
        except:
            return 0.8  # Default score if timezone handling fails
    
    def _score_urgency_factor(self, slot: TimeSlot, request: SchedulingRequest) -> float:
        """Score based on urgency and how soon the slot is"""
        time_diff = slot.start_time - datetime.utcnow()
        hours_until = time_diff.total_seconds() / 3600
        
        if request.priority == SchedulingPriority.URGENT:
            if hours_until <= 24:
                return 1.0
            elif hours_until <= 48:
                return 0.8
            else:
                return 0.5
        elif request.priority == SchedulingPriority.HIGH:
            if hours_until <= 72:
                return 1.0
            else:
                return 0.7
        else:
            # For medium/low priority, prefer slots that are not too soon
            if hours_until >= 24:
                return 1.0
            else:
                return 0.6
    
    def _is_working_time(self, dt: datetime) -> bool:
        """Check if datetime is within working hours"""
        return (
            dt.weekday() in self.working_days and
            self.working_hours_start <= dt.time() <= self.working_hours_end
        )
    
    async def _create_interview(self, slot: TimeSlot, request: SchedulingRequest, db: Session) -> Interview:
        """Create interview record from selected slot"""
        # Get candidate and job info
        candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
        job = db.query(JobPosition).filter(JobPosition.id == request.job_position_id).first()
        
        # Create interview
        interview = Interview(
            candidate_id=request.candidate_id,
            job_position_id=request.job_position_id,
            title=f"{request.interview_type.value.replace('_', ' ').title()} Interview - {candidate.name}",
            interview_type=request.interview_type,
            status=InterviewStatus.SCHEDULED,
            scheduled_start=slot.start_time,
            scheduled_end=slot.end_time,
            duration_minutes=request.duration_minutes,
            timezone=request.timezone,
            interviewer_emails=slot.participants_available,
            interviewer_names=[email.split('@')[0].replace('.', ' ').title() for email in slot.participants_available],
            primary_interviewer=slot.participants_available[0] if slot.participants_available else None,
            auto_scheduled=True,
            scheduling_preferences=request.requirements,
            conflicts_detected=slot.conflicts,
            description=f"Interview for {job.title} position"
        )
        
        db.add(interview)
        db.commit()
        db.refresh(interview)
        
        return interview
    
    async def _log_scheduling_activity(
        self,
        interview_id: Optional[str],
        action_type: str,
        action_status: str,
        metadata: Dict,
        db: Session
    ):
        """Log scheduling activity for analytics"""
        try:
            log_entry = SchedulingLog(
                interview_id=interview_id,
                action_type=action_type,
                action_status=action_status,
                algorithm_used=metadata.get('algorithm'),
                conflicts_found=metadata.get('conflicts'),
                alternatives_considered=metadata.get('alternatives'),
                decision_factors=metadata.get('decision_factors'),
                processing_time_ms=metadata.get('processing_time_ms'),
                slots_evaluated=metadata.get('slots_evaluated'),
                success_score=metadata.get('best_score'),
                error_message=metadata.get('error')
            )
            
            db.add(log_entry)
            db.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to log scheduling activity: {str(e)}")
    
    async def _send_scheduling_notifications(self, interview: Interview, slot: TimeSlot, db: Session):
        """Send notifications about scheduled interview"""
        try:
            if message_broker and hasattr(message_broker, 'publish'):
                # Prepare notification data
                notification_data = {
                    'interview_id': str(interview.id),
                    'candidate_id': str(interview.candidate_id),
                    'job_position_id': str(interview.job_position_id),
                    'interview_type': interview.interview_type,
                    'scheduled_start': interview.scheduled_start.isoformat(),
                    'scheduled_end': interview.scheduled_end.isoformat(),
                    'interviewer_emails': interview.interviewer_emails,
                    'meeting_details': {
                        'duration': interview.duration_minutes,
                        'timezone': interview.timezone,
                        'conflicts': slot.conflicts
                    }
                }
                
                # Send to communication agent for notification processing
                await message_broker.publish(
                    'interview.scheduled',
                    notification_data
                )
                
                self.logger.info(f"📨 Sent scheduling notifications for interview {interview.id}")
                
        except Exception as e:
            self.logger.error(f"Failed to send notifications: {str(e)}")
    
    def _create_error_response(self, error_type: str, errors: List[str]) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            'success': False,
            'error_type': error_type,
            'errors': errors,
            'interview': None,
            'alternatives': [],
            'metadata': {
                'timestamp': datetime.utcnow().isoformat()
            }
        }

# Global instance
scheduler_agent = SchedulerAgent() 