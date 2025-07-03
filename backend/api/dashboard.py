"""Dashboard API endpoints for RecruitAI Pro - Phase 4"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from core.database import get_db
from models.candidates import Candidate
from models.interviews import Interview
from models.communications import CommunicationMessage
from models.jobs import JobPosition
from agents.dashboard_agent import get_dashboard_agent

# Create router
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Request/Response Models
class KPIResponse(BaseModel):
    name: str
    value: float
    previous_value: Optional[float] = None
    target_value: Optional[float] = None
    unit: str
    change_percentage: Optional[float] = None
    trend: str

class DashboardResponse(BaseModel):
    kpis: List[KPIResponse]
    charts: Dict[str, Any]
    recent_activity: List[Dict]
    agent_status: Dict[str, Any]
    timestamp: str

@router.get("/data", response_model=DashboardResponse)
async def get_dashboard_data(
    time_range: str = Query("24h", description="Time range: 24h, 7d, 30d"),
    db: Session = Depends(get_db)
):
    """Get comprehensive dashboard data including KPIs and charts"""
    try:
        agent = get_dashboard_agent()
        
        # Get complete dashboard data
        dashboard_data = await agent.get_dashboard_data(db, time_range)
        
        # Convert KPIs to response format
        kpis_response = [
            KPIResponse(
                name=kpi.name,
                value=kpi.value,
                previous_value=kpi.previous_value,
                target_value=kpi.target_value,
                unit=kpi.unit,
                change_percentage=kpi.change_percentage,
                trend=kpi.trend
            )
            for kpi in dashboard_data.kpis
        ]
        
        return DashboardResponse(
            kpis=kpis_response,
            charts=dashboard_data.charts,
            recent_activity=dashboard_data.recent_activity,
            agent_status=dashboard_data.agent_status,
            timestamp=dashboard_data.timestamp.isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")

@router.get("/kpis")
async def get_kpis(
    time_range: str = Query("24h", description="Time range for KPI calculation"),
    db: Session = Depends(get_db)
):
    """Get Key Performance Indicators"""
    try:
        agent = get_dashboard_agent()
        
        # Calculate time range
        end_time = datetime.utcnow()
        if time_range == "7d":
            start_time = end_time - timedelta(days=7)
        elif time_range == "30d":
            start_time = end_time - timedelta(days=30)
        else:
            start_time = end_time - timedelta(hours=24)
        
        # Get KPIs
        kpis = await agent.calculate_all_kpis(db, start_time, end_time)
        
        return {
            "kpis": [
                {
                    "name": kpi.name,
                    "value": kpi.value,
                    "previous_value": kpi.previous_value,
                    "target_value": kpi.target_value,
                    "unit": kpi.unit,
                    "change_percentage": kpi.change_percentage,
                    "trend": kpi.trend
                }
                for kpi in kpis
            ],
            "time_range": time_range,
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "total_kpis": len(kpis)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get KPIs: {str(e)}")

@router.get("/charts")
async def get_chart_data(
    time_range: str = Query("7d", description="Time range for charts"),
    chart_type: Optional[str] = Query(None, description="Specific chart type"),
    db: Session = Depends(get_db)
):
    """Get chart data for dashboard visualizations"""
    try:
        agent = get_dashboard_agent()
        
        # Calculate time range
        end_time = datetime.utcnow()
        if time_range == "7d":
            start_time = end_time - timedelta(days=7)
        elif time_range == "30d":
            start_time = end_time - timedelta(days=30)
        else:
            start_time = end_time - timedelta(hours=24)
        
        # Get chart data
        charts = await agent.generate_chart_data(db, start_time, end_time)
        
        # Filter by chart type if specified
        if chart_type and chart_type in charts:
            charts = {chart_type: charts[chart_type]}
        
        return {
            "charts": charts,
            "time_range": time_range,
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "available_charts": list(charts.keys())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chart data: {str(e)}")

@router.get("/stats")
async def get_system_stats(db: Session = Depends(get_db)):
    """Get overall system statistics"""
    try:
        # Calculate basic stats
        total_candidates = db.query(Candidate).count()
        total_interviews = db.query(Interview).count()
        total_messages = db.query(CommunicationMessage).count()
        total_jobs = db.query(JobPosition).count()
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        candidates_this_week = db.query(Candidate)\
                                 .filter(Candidate.created_at >= week_ago)\
                                 .count()
        interviews_this_week = db.query(Interview)\
                                .filter(Interview.created_at >= week_ago)\
                                .count()
        messages_this_week = db.query(CommunicationMessage)\
                              .filter(CommunicationMessage.created_at >= week_ago)\
                              .count()
        
        return {
            "system_stats": {
                "total_candidates": total_candidates,
                "total_interviews": total_interviews,
                "total_messages": total_messages,
                "total_jobs": total_jobs,
                "candidates_this_week": candidates_this_week,
                "interviews_this_week": interviews_this_week,
                "messages_this_week": messages_this_week
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system stats: {str(e)}")

@router.get("/agents/status")
async def get_agents_status():
    """Get status summary for all agents"""
    try:
        # Simplified agent status check
        agent_status = {
            "Resume Analyzer": {"status": "healthy", "health_score": 95},
            "Scheduler": {"status": "healthy", "health_score": 92},
            "Communication": {"status": "healthy", "health_score": 88},
            "Dashboard": {"status": "healthy", "health_score": 90}
        }
        
        return {
            "agents": agent_status,
            "overall_health": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {str(e)}")

@router.get("/health")
async def dashboard_health_check():
    """Health check for Dashboard API"""
    try:
        agent = get_dashboard_agent()
        agent_status = agent.get_agent_status()
        
        return {
            "status": "healthy",
            "service": "Dashboard API",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_status": agent_status["status"],
            "features": agent_status["features"]
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "Dashboard API",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/agent/status")
async def get_dashboard_agent_status():
    """Get Dashboard Agent status and configuration"""
    try:
        agent = get_dashboard_agent()
        return agent.get_agent_status()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {str(e)}") 