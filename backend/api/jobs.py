"""
Job Position API endpoints for RecruitAI Pro
Handles job creation, management, and candidate matching
"""

import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_

from core.database import get_db
from models.jobs import JobPosition
from models.candidates import Candidate

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

@router.post("/", response_model=dict)
async def create_job_position(
    job_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Create a new job position with requirements and scoring criteria
    
    **Demo Use Case**: Create a "Senior Python Developer" position with specific requirements
    """
    
    try:
        # Validate required fields
        required_fields = ["title", "required_skills"]
        for field in required_fields:
            if field not in job_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {field}"
                )
        
        # Create job position
        job_position = JobPosition(
            title=job_data["title"],
            department=job_data.get("department"),
            location=job_data.get("location"),
            employment_type=job_data.get("employment_type", "full_time"),
            experience_level=job_data.get("experience_level"),
            description=job_data.get("description"),
            responsibilities=job_data.get("responsibilities", []),
            required_skills=job_data["required_skills"],
            preferred_skills=job_data.get("preferred_skills", []),
            required_experience_years=job_data.get("required_experience_years"),
            required_education=job_data.get("required_education", []),
            certifications_required=job_data.get("certifications_required", []),
            certifications_preferred=job_data.get("certifications_preferred", []),
            soft_skills_required=job_data.get("soft_skills_required", []),
            cultural_values=job_data.get("cultural_values", []),
            salary_min=job_data.get("salary_min"),
            salary_max=job_data.get("salary_max"),
            currency=job_data.get("currency", "USD"),
            benefits=job_data.get("benefits", []),
            interview_stages=job_data.get("interview_stages", []),
            estimated_hire_time_days=job_data.get("estimated_hire_time_days"),
            hiring_manager=job_data.get("hiring_manager"),
            hiring_team=job_data.get("hiring_team", []),
            # Scoring weights (ensure they add up to 100)
            technical_skills_weight=job_data.get("technical_skills_weight", 40.0),
            experience_weight=job_data.get("experience_weight", 30.0),
            education_weight=job_data.get("education_weight", 20.0),
            soft_skills_weight=job_data.get("soft_skills_weight", 10.0),
            # Thresholds
            minimum_score_threshold=job_data.get("minimum_score_threshold", 50),
            auto_schedule_threshold=job_data.get("auto_schedule_threshold", 75),
            human_review_threshold=job_data.get("human_review_threshold", 85),
            priority=job_data.get("priority", "medium"),
            positions_available=job_data.get("positions_available", 1)
        )
        
        # Validate scoring weights
        if not job_position.validate_scoring_weights():
            raise HTTPException(
                status_code=400,
                detail="Scoring weights must add up to 100%"
            )
        
        db.add(job_position)
        db.commit()
        db.refresh(job_position)
        
        return {
            "success": True,
            "message": "Job position created successfully",
            "job_id": str(job_position.id),
            "job_position": job_position.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating job position: {str(e)}"
        )

@router.get("/", response_model=dict)
async def get_job_positions(
    skip: int = Query(0, ge=0, description="Number of jobs to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of jobs to return"),
    status: Optional[str] = Query(None, description="Filter by status (open/paused/closed/filled)"),
    department: Optional[str] = Query(None, description="Filter by department"),
    employment_type: Optional[str] = Query(None, description="Filter by employment type"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    db: Session = Depends(get_db)
):
    """
    Get list of job positions with filtering and sorting options
    
    **Demo Use Case**: Browse available positions and their requirements
    """
    
    try:
        # Build query
        query = db.query(JobPosition)
        
        # Apply filters
        if status:
            query = query.filter(JobPosition.status == status)
        
        if department:
            query = query.filter(JobPosition.department == department)
        
        if employment_type:
            query = query.filter(JobPosition.employment_type == employment_type)
        
        if priority:
            query = query.filter(JobPosition.priority == priority)
        
        # Apply sorting
        sort_column = getattr(JobPosition, sort_by, JobPosition.created_at)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        jobs = query.offset(skip).limit(limit).all()
        
        # Convert to dict
        job_list = [job.to_dict() for job in jobs]
        
        # Add summary statistics
        stats = db.query(
            func.count(JobPosition.id).label("total"),
            func.count(JobPosition.id).filter(JobPosition.status == "open").label("open_positions"),
            func.sum(JobPosition.positions_available).label("total_openings"),
            func.sum(JobPosition.total_applications).label("total_applications")
        ).first()
        
        return {
            "success": True,
            "jobs": job_list,
            "pagination": {
                "total": total_count,
                "skip": skip,
                "limit": limit,
                "returned": len(job_list)
            },
            "statistics": {
                "total_positions": stats.total or 0,
                "open_positions": stats.open_positions or 0,
                "total_openings": stats.total_openings or 0,
                "total_applications": stats.total_applications or 0
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving job positions: {str(e)}"
        )

@router.get("/{job_id}", response_model=dict)
async def get_job_position_details(
    job_id: str,
    include_candidates: bool = Query(False, description="Include matching candidates"),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific job position
    
    **Demo Use Case**: View job requirements and matching candidates
    """
    
    try:
        # Get job position
        job = db.query(JobPosition).filter(
            JobPosition.id == uuid.UUID(job_id)
        ).first()
        
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job position {job_id} not found"
            )
        
        response_data = {
            "success": True,
            "job_position": job.to_dict(),
            "matching_criteria": job.get_matching_criteria(),
            "performance_metrics": {
                "fill_rate": job.fill_rate,
                "qualification_rate": job.qualification_rate,
                "is_active": job.is_active
            }
        }
        
        # Include matching candidates if requested
        if include_candidates:
            # Get candidates with analysis completed
            candidates_query = db.query(Candidate).filter(
                and_(
                    Candidate.analysis_completed == True,
                    Candidate.overall_score >= job.minimum_score_threshold
                )
            ).order_by(desc(Candidate.overall_score))
            
            candidates = candidates_query.all()
            
            response_data["matching_candidates"] = {
                "total_matches": len(candidates),
                "candidates": [
                    {
                        "id": str(candidate.id),
                        "name": candidate.name,
                        "email": candidate.email,
                        "overall_score": candidate.overall_score,
                        "status": candidate.status,
                        "recommendation": candidate.recommendation,
                        "analysis_timestamp": candidate.analysis_timestamp.isoformat() if candidate.analysis_timestamp else None
                    }
                    for candidate in candidates[:20]  # Limit to top 20
                ]
            }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving job position details: {str(e)}"
        )

@router.put("/{job_id}", response_model=dict)
async def update_job_position(
    job_id: str,
    updates: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Update an existing job position
    """
    
    try:
        # Get job position
        job = db.query(JobPosition).filter(
            JobPosition.id == uuid.UUID(job_id)
        ).first()
        
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job position {job_id} not found"
            )
        
        # Update allowed fields
        updateable_fields = [
            "title", "department", "location", "employment_type", "experience_level",
            "description", "responsibilities", "required_skills", "preferred_skills",
            "required_experience_years", "required_education", "certifications_required",
            "certifications_preferred", "soft_skills_required", "cultural_values",
            "salary_min", "salary_max", "currency", "benefits", "interview_stages",
            "estimated_hire_time_days", "hiring_manager", "hiring_team",
            "technical_skills_weight", "experience_weight", "education_weight", "soft_skills_weight",
            "minimum_score_threshold", "auto_schedule_threshold", "human_review_threshold",
            "status", "priority", "positions_available"
        ]
        
        for field, value in updates.items():
            if field in updateable_fields:
                setattr(job, field, value)
        
        # Validate scoring weights if they were updated
        if any(field.endswith("_weight") for field in updates.keys()):
            if not job.validate_scoring_weights():
                raise HTTPException(
                    status_code=400,
                    detail="Scoring weights must add up to 100%"
                )
        
        db.commit()
        db.refresh(job)
        
        return {
            "success": True,
            "message": "Job position updated successfully",
            "job_id": job_id,
            "updated_job": job.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error updating job position: {str(e)}"
        )

@router.get("/{job_id}/candidates", response_model=dict)
async def get_job_candidates(
    job_id: str,
    min_score: int = Query(0, ge=0, le=100, description="Minimum score filter"),
    status: Optional[str] = Query(None, description="Candidate status filter"),
    limit: int = Query(50, ge=1, le=500, description="Number of candidates to return"),
    db: Session = Depends(get_db)
):
    """
    Get candidates that match a specific job position
    
    **Demo Use Case**: See ranked candidates for a position with AI scores
    """
    
    try:
        # Verify job exists
        job = db.query(JobPosition).filter(
            JobPosition.id == uuid.UUID(job_id)
        ).first()
        
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job position {job_id} not found"
            )
        
        # Build candidates query
        query = db.query(Candidate).filter(
            and_(
                Candidate.analysis_completed == True,
                Candidate.overall_score >= max(min_score, job.minimum_score_threshold)
            )
        )
        
        if status:
            query = query.filter(Candidate.status == status)
        
        # Order by score descending
        candidates = query.order_by(desc(Candidate.overall_score)).limit(limit).all()
        
        # Categorize candidates by recommendation thresholds
        auto_schedule = []
        needs_review = []
        qualified = []
        
        for candidate in candidates:
            if candidate.overall_score >= job.auto_schedule_threshold:
                auto_schedule.append(candidate)
            elif candidate.overall_score >= job.human_review_threshold:
                needs_review.append(candidate)
            else:
                qualified.append(candidate)
        
        return {
            "success": True,
            "job_id": job_id,
            "job_title": job.title,
            "total_candidates": len(candidates),
            "categorized_candidates": {
                "auto_schedule": {
                    "count": len(auto_schedule),
                    "threshold": job.auto_schedule_threshold,
                    "candidates": [candidate.to_dict() for candidate in auto_schedule]
                },
                "needs_review": {
                    "count": len(needs_review),
                    "threshold": job.human_review_threshold,
                    "candidates": [candidate.to_dict() for candidate in needs_review]
                },
                "qualified": {
                    "count": len(qualified),
                    "threshold": job.minimum_score_threshold,
                    "candidates": [candidate.to_dict() for candidate in qualified]
                }
            },
            "all_candidates": [candidate.to_dict() for candidate in candidates]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving job candidates: {str(e)}"
        )

@router.post("/{job_id}/template", response_model=dict)
async def create_job_template(
    job_id: str,
    template_name: str = Body(...),
    description: Optional[str] = Body(None),
    db: Session = Depends(get_db)
):
    """
    Create a reusable job template from an existing position
    """
    
    try:
        # Get source job
        source_job = db.query(JobPosition).filter(
            JobPosition.id == uuid.UUID(job_id)
        ).first()
        
        if not source_job:
            raise HTTPException(
                status_code=404,
                detail=f"Job position {job_id} not found"
            )
        
        # Create template (simplified version for demo)
        template_data = {
            "name": template_name,
            "description": description,
            "source_job_id": str(source_job.id),
            "requirements": source_job.get_matching_criteria(),
            "scoring_weights": {
                "technical_skills": source_job.technical_skills_weight,
                "experience": source_job.experience_weight,
                "education": source_job.education_weight,
                "soft_skills": source_job.soft_skills_weight
            },
            "thresholds": {
                "minimum_score": source_job.minimum_score_threshold,
                "auto_schedule": source_job.auto_schedule_threshold,
                "human_review": source_job.human_review_threshold
            }
        }
        
        return {
            "success": True,
            "message": f"Job template '{template_name}' created successfully",
            "template": template_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating job template: {str(e)}"
        )

@router.delete("/{job_id}", response_model=dict)
async def delete_job_position(
    job_id: str,
    confirm: bool = Query(False, description="Confirmation required"),
    db: Session = Depends(get_db)
):
    """
    Delete a job position (only if no applications exist)
    """
    
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set confirm=true to delete job position."
        )
    
    try:
        job = db.query(JobPosition).filter(
            JobPosition.id == uuid.UUID(job_id)
        ).first()
        
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job position {job_id} not found"
            )
        
        # Check if job has applications
        if job.total_applications > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete job position with existing applications. Set status to 'closed' instead."
            )
        
        job_title = job.title
        db.delete(job)
        db.commit()
        
        return {
            "success": True,
            "message": f"Job position '{job_title}' deleted successfully",
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting job position: {str(e)}"
        ) 