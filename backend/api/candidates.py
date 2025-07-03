"""
Candidate API endpoints for RecruitAI Pro
Handles resume upload, analysis, and candidate management
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from core.database import get_db
from models.candidates import Candidate, CandidateAnalysisLog
from models.jobs import JobPosition
from agents.resume_analyzer import resume_analyzer
from services.file_processor import file_processor

router = APIRouter(prefix="/api/candidates", tags=["candidates"])

@router.post("/upload-resume", response_model=dict)
async def upload_and_analyze_resume(
    file: UploadFile = File(...),
    candidate_name: str = Form(...),
    candidate_email: str = Form(...),
    candidate_phone: Optional[str] = Form(None),
    job_position_id: Optional[str] = Form(None),
    auto_analyze: bool = Form(True),
    db: Session = Depends(get_db)
):
    """
    Upload a resume file and optionally trigger immediate AI analysis
    
    **Demo Use Case**: Upload PDF resume → Get analysis in 30 seconds
    """
    
    try:
        # Check if candidate already exists
        existing_candidate = db.query(Candidate).filter(
            Candidate.email == candidate_email
        ).first()
        
        if existing_candidate:
            raise HTTPException(
                status_code=400,
                detail=f"Candidate with email {candidate_email} already exists"
            )
        
        # Process uploaded file
        file_result = await file_processor.process_resume_file(file)
        
        if not file_result["success"]:
            raise HTTPException(
                status_code=422,
                detail="Failed to process resume file"
            )
        
        # Create new candidate record
        candidate = Candidate(
            name=candidate_name,
            email=candidate_email,
            phone=candidate_phone,
            resume_filename=file_result["filename"],
            resume_file_path=file_result["file_path"],
            resume_text=file_result["extracted_text"],
            status="new"
        )
        
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        
        # Get job position if specified
        job_position = None
        if job_position_id:
            job_position = db.query(JobPosition).filter(
                JobPosition.id == uuid.UUID(job_position_id)
            ).first()
            
            if not job_position:
                raise HTTPException(
                    status_code=404,
                    detail=f"Job position {job_position_id} not found"
                )
        
        response_data = {
            "success": True,
            "message": "Resume uploaded successfully",
            "candidate_id": str(candidate.id),
            "candidate": candidate.to_dict(),
            "file_processing": {
                "filename": file_result["filename"],
                "file_size": file_result["file_size"],
                "text_length": file_result["text_length"],
                "word_count": file_result["word_count"]
            }
        }
        
        # Trigger analysis if requested
        if auto_analyze:
            try:
                analysis_result = await resume_analyzer.analyze_resume(
                    candidate,
                    job_position
                )
                
                # Refresh candidate from database to get updated analysis
                db.refresh(candidate)
                
                response_data.update({
                    "analysis_completed": True,
                    "analysis_result": analysis_result,
                    "updated_candidate": candidate.to_dict()
                })
                
            except Exception as analysis_error:
                # Don't fail the upload if analysis fails
                response_data.update({
                    "analysis_completed": False,
                    "analysis_error": str(analysis_error),
                    "message": "Resume uploaded successfully, but analysis failed. You can retry analysis later."
                })
        
        return JSONResponse(content=response_data, status_code=201)
        
    except HTTPException:
        raise
    except Exception as e:
        # Clean up file if candidate creation failed
        if 'file_result' in locals() and file_result.get("file_path"):
            file_processor.cleanup_file(file_result["file_path"])
        
        raise HTTPException(
            status_code=500,
            detail=f"Error processing resume upload: {str(e)}"
        )

@router.post("/{candidate_id}/analyze", response_model=dict)
async def analyze_candidate_resume(
    candidate_id: str,
    job_position_id: Optional[str] = None,
    force_reanalysis: bool = False,
    db: Session = Depends(get_db)
):
    """
    Trigger AI analysis for an existing candidate
    
    **Demo Use Case**: Manual analysis trigger with job-specific scoring
    """
    
    try:
        # Get candidate
        candidate = db.query(Candidate).filter(
            Candidate.id == uuid.UUID(candidate_id)
        ).first()
        
        if not candidate:
            raise HTTPException(
                status_code=404,
                detail=f"Candidate {candidate_id} not found"
            )
        
        if not candidate.resume_text:
            raise HTTPException(
                status_code=400,
                detail="Candidate has no resume text to analyze"
            )
        
        # Get job position if specified
        job_position = None
        if job_position_id:
            job_position = db.query(JobPosition).filter(
                JobPosition.id == uuid.UUID(job_position_id)
            ).first()
            
            if not job_position:
                raise HTTPException(
                    status_code=404,
                    detail=f"Job position {job_position_id} not found"
                )
        
        # Run analysis
        analysis_result = await resume_analyzer.analyze_resume(
            candidate,
            job_position,
            force_reanalysis
        )
        
        # Refresh candidate to get updated data
        db.refresh(candidate)
        
        return {
            "success": True,
            "message": "Resume analysis completed",
            "candidate_id": candidate_id,
            "analysis_result": analysis_result,
            "updated_candidate": candidate.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing resume: {str(e)}"
        )

@router.get("/", response_model=dict)
async def get_candidates(
    skip: int = Query(0, ge=0, description="Number of candidates to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of candidates to return"),
    status: Optional[str] = Query(None, description="Filter by candidate status"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum overall score"),
    job_position_id: Optional[str] = Query(None, description="Filter by job position"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    db: Session = Depends(get_db)
):
    """
    Get list of candidates with filtering and sorting options
    
    **Demo Use Case**: Browse analyzed candidates with scores and recommendations
    """
    
    try:
        # Build query
        query = db.query(Candidate)
        
        # Apply filters
        if status:
            query = query.filter(Candidate.status == status)
        
        if min_score is not None:
            query = query.filter(Candidate.overall_score >= min_score)
        
        # Apply sorting
        sort_column = getattr(Candidate, sort_by, Candidate.created_at)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        candidates = query.offset(skip).limit(limit).all()
        
        # Convert to dict
        candidate_list = [candidate.to_dict() for candidate in candidates]
        
        # Add summary statistics
        stats = db.query(
            func.count(Candidate.id).label("total"),
            func.avg(Candidate.overall_score).label("avg_score"),
            func.count(Candidate.id).filter(Candidate.analysis_completed == True).label("analyzed")
        ).first()
        
        return {
            "success": True,
            "candidates": candidate_list,
            "pagination": {
                "total": total_count,
                "skip": skip,
                "limit": limit,
                "returned": len(candidate_list)
            },
            "statistics": {
                "total_candidates": stats.total or 0,
                "average_score": round(stats.avg_score or 0, 1),
                "analyzed_candidates": stats.analyzed or 0
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving candidates: {str(e)}"
        )

@router.get("/{candidate_id}", response_model=dict)
async def get_candidate_details(
    candidate_id: str,
    include_analysis_logs: bool = Query(False, description="Include analysis logs"),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific candidate
    
    **Demo Use Case**: View complete candidate profile with AI analysis breakdown
    """
    
    try:
        # Get candidate
        candidate = db.query(Candidate).filter(
            Candidate.id == uuid.UUID(candidate_id)
        ).first()
        
        if not candidate:
            raise HTTPException(
                status_code=404,
                detail=f"Candidate {candidate_id} not found"
            )
        
        response_data = {
            "success": True,
            "candidate": candidate.to_dict(),
            "score_breakdown": candidate.score_breakdown if candidate.overall_score else None,
            "recommendation": candidate.recommendation
        }
        
        # Include analysis logs if requested
        if include_analysis_logs:
            analysis_logs = db.query(CandidateAnalysisLog).filter(
                CandidateAnalysisLog.candidate_id == candidate.id
            ).order_by(desc(CandidateAnalysisLog.started_at)).all()
            
            response_data["analysis_logs"] = [
                {
                    "id": str(log.id),
                    "analysis_type": log.analysis_type,
                    "status": log.status,
                    "confidence_score": log.confidence_score,
                    "processing_time": log.processing_time_seconds,
                    "ai_model_used": log.ai_model_used,
                    "tokens_used": log.tokens_used,
                    "started_at": log.started_at.isoformat() if log.started_at else None,
                    "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                    "error_message": log.error_message
                }
                for log in analysis_logs
            ]
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving candidate details: {str(e)}"
        )

@router.put("/{candidate_id}/status", response_model=dict)
async def update_candidate_status(
    candidate_id: str,
    new_status: str,
    human_decision: Optional[str] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Update candidate status and add human review decisions
    
    **Demo Use Case**: Human override of AI recommendation
    """
    
    valid_statuses = ["new", "analyzed", "scheduled", "interviewed", "hired", "rejected"]
    valid_decisions = ["approved", "rejected", "needs_interview", None]
    
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid options: {valid_statuses}"
        )
    
    if human_decision and human_decision not in valid_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid human decision. Valid options: {valid_decisions}"
        )
    
    try:
        # Get candidate
        candidate = db.query(Candidate).filter(
            Candidate.id == uuid.UUID(candidate_id)
        ).first()
        
        if not candidate:
            raise HTTPException(
                status_code=404,
                detail=f"Candidate {candidate_id} not found"
            )
        
        # Update status
        old_status = candidate.status
        candidate.status = new_status
        
        if human_decision:
            candidate.human_decision = human_decision
            candidate.needs_human_review = False
        
        if notes:
            candidate.human_review_notes = notes
        
        db.commit()
        db.refresh(candidate)
        
        return {
            "success": True,
            "message": f"Candidate status updated from '{old_status}' to '{new_status}'",
            "candidate_id": candidate_id,
            "updated_candidate": candidate.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating candidate status: {str(e)}"
        )

@router.get("/{candidate_id}/score-breakdown", response_model=dict)
async def get_score_breakdown(
    candidate_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed score breakdown and analysis insights
    
    **Demo Use Case**: Detailed view of how AI calculated the candidate score
    """
    
    try:
        candidate = db.query(Candidate).filter(
            Candidate.id == uuid.UUID(candidate_id)
        ).first()
        
        if not candidate:
            raise HTTPException(
                status_code=404,
                detail=f"Candidate {candidate_id} not found"
            )
        
        if not candidate.analysis_completed:
            raise HTTPException(
                status_code=400,
                detail="Candidate analysis not completed yet"
            )
        
        return {
            "success": True,
            "candidate_id": candidate_id,
            "candidate_name": candidate.name,
            "overall_score": candidate.overall_score,
            "score_breakdown": candidate.score_breakdown,
            "recommendation": candidate.recommendation,
            "technical_skills": candidate.technical_skills,
            "experience": candidate.experience,
            "education": candidate.education,
            "soft_skills": candidate.soft_skills,
            "certifications": candidate.certifications,
            "analysis_timestamp": candidate.analysis_timestamp.isoformat() if candidate.analysis_timestamp else None,
            "analysis_model_version": candidate.analysis_model_version
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving score breakdown: {str(e)}"
        )

@router.delete("/{candidate_id}", response_model=dict)
async def delete_candidate(
    candidate_id: str,
    confirm: bool = Query(False, description="Confirmation required"),
    db: Session = Depends(get_db)
):
    """
    Delete a candidate and cleanup associated files
    """
    
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set confirm=true to delete candidate."
        )
    
    try:
        candidate = db.query(Candidate).filter(
            Candidate.id == uuid.UUID(candidate_id)
        ).first()
        
        if not candidate:
            raise HTTPException(
                status_code=404,
                detail=f"Candidate {candidate_id} not found"
            )
        
        # Clean up uploaded file
        if candidate.resume_file_path:
            file_processor.cleanup_file(candidate.resume_file_path)
        
        # Delete analysis logs
        db.query(CandidateAnalysisLog).filter(
            CandidateAnalysisLog.candidate_id == candidate.id
        ).delete()
        
        # Delete candidate
        candidate_name = candidate.name
        db.delete(candidate)
        db.commit()
        
        return {
            "success": True,
            "message": f"Candidate '{candidate_name}' deleted successfully",
            "candidate_id": candidate_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting candidate: {str(e)}"
        ) 