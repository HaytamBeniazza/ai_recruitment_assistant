"""
Dashboard Agent for RecruitAI Pro
Handles real-time analytics, performance tracking, and intelligent reporting
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
import uuid
import json
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, asc

from core.database import get_db
from core.config import settings
# Analytics models will be implemented in a future update
# from models.analytics import (
#     DashboardMetric, AgentPerformance, RecruitmentPipeline, 
#     SystemReport, DashboardWidget, UserActivity
# )
from models.candidates import Candidate
from models.interviews import Interview
from models.communications import CommunicationMessage
from models.jobs import JobPosition

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class KPIResult:
    """Result for a KPI calculation"""
    name: str
    value: float
    previous_value: Optional[float] = None
    target_value: Optional[float] = None
    unit: str = ""
    change_percentage: Optional[float] = None
    trend: str = "stable"  # improving, declining, stable
    metadata: Optional[Dict] = None

@dataclass
class DashboardData:
    """Complete dashboard data structure"""
    kpis: List[KPIResult]
    charts: Dict[str, Any]
    recent_activity: List[Dict]
    agent_status: Dict[str, Any]
    pipeline_summary: Dict[str, Any]
    alerts: List[Dict]
    timestamp: datetime

class DashboardAgent:
    """
    Intelligent Dashboard Agent for comprehensive recruitment analytics
    
    Features:
    - Real-time KPI calculation and tracking
    - Agent performance monitoring
    - Recruitment pipeline analytics
    - Automated reporting and insights
    - Customizable dashboard widgets
    - Predictive analytics and trends
    """
    
    def __init__(self):
        """Initialize Dashboard Agent"""
        self.settings = settings
        
        # Key Performance Indicators configuration
        self.kpi_definitions = self._load_kpi_definitions()
        
        # Dashboard widgets configuration
        self.widget_templates = self._load_widget_templates()
        
        # Performance thresholds
        self.performance_thresholds = {
            "response_time_warning": 5000,  # ms
            "response_time_critical": 10000,  # ms
            "success_rate_warning": 0.85,
            "success_rate_critical": 0.70,
            "queue_length_warning": 10,
            "queue_length_critical": 25
        }
        
        logger.info("Dashboard Agent initialized successfully")
    
    def _load_kpi_definitions(self) -> Dict[str, Dict]:
        """Load KPI definitions and calculation methods"""
        return {
            "total_candidates": {
                "name": "Total Candidates",
                "description": "Total number of candidates in the system",
                "category": "volume",
                "unit": "count",
                "target": None,
                "calculation": "count"
            },
            "candidates_this_week": {
                "name": "New Candidates This Week",
                "description": "Candidates added in the last 7 days",
                "category": "volume",
                "unit": "count",
                "target": 10,
                "calculation": "count_time_filtered"
            },
            "average_resume_score": {
                "name": "Average Resume Score",
                "description": "Average AI analysis score for resumes",
                "category": "quality",
                "unit": "score",
                "target": 75,
                "calculation": "average"
            },
            "time_to_schedule": {
                "name": "Average Time to Schedule",
                "description": "Average time from application to interview scheduling",
                "category": "efficiency",
                "unit": "hours",
                "target": 48,
                "calculation": "time_difference"
            },
            "interview_success_rate": {
                "name": "Interview Success Rate",
                "description": "Percentage of successfully scheduled interviews",
                "category": "success_rate",
                "unit": "percentage",
                "target": 90,
                "calculation": "success_rate"
            },
            "communication_delivery_rate": {
                "name": "Communication Delivery Rate",
                "description": "Percentage of messages successfully delivered",
                "category": "success_rate",
                "unit": "percentage",
                "target": 95,
                "calculation": "delivery_rate"
            },
            "automation_rate": {
                "name": "Process Automation Rate",
                "description": "Percentage of processes handled by AI agents",
                "category": "efficiency",
                "unit": "percentage",
                "target": 80,
                "calculation": "automation_percentage"
            },
            "agent_uptime": {
                "name": "System Uptime",
                "description": "Percentage of time all agents are operational",
                "category": "performance",
                "unit": "percentage",
                "target": 99,
                "calculation": "uptime"
            }
        }
    
    def _load_widget_templates(self) -> Dict[str, Dict]:
        """Load default widget templates"""
        return {
            "kpi_card": {
                "type": "metric",
                "config": {
                    "display_type": "card",
                    "show_trend": True,
                    "show_target": True,
                    "color_scheme": "auto"
                }
            },
            "timeline_chart": {
                "type": "chart",
                "config": {
                    "chart_type": "line",
                    "time_series": True,
                    "aggregation": "daily"
                }
            },
            "pipeline_funnel": {
                "type": "chart",
                "config": {
                    "chart_type": "funnel",
                    "stages": ["applied", "screened", "interviewed", "offered", "hired"]
                }
            },
            "agent_status": {
                "type": "status",
                "config": {
                    "display_type": "grid",
                    "show_metrics": True,
                    "refresh_interval": 30
                }
            }
        }
    
    async def get_dashboard_data(self, db: Session, time_range: str = "24h") -> DashboardData:
        """Get complete dashboard data"""
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            if time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)  # Default
            
            # Get all KPIs
            kpis = await self.calculate_all_kpis(db, start_time, end_time)
            
            # Get chart data
            charts = await self.generate_chart_data(db, start_time, end_time)
            
            # Get recent activity (simplified for now)
            recent_activity = []
            
            # Get agent status (simplified for now)
            agent_status = {
                "Resume Analyzer": {"status": "healthy", "health_score": 95},
                "Scheduler": {"status": "healthy", "health_score": 92},
                "Communication": {"status": "healthy", "health_score": 88}
            }
            
            # Get pipeline summary (simplified for now)
            pipeline_summary = {
                "active_candidates": 0,
                "average_time_hours": 0,
                "completion_rate": 0,
                "hire_rate": 0
            }
            
            # Get alerts (simplified for now)
            alerts = []
            
            return DashboardData(
                kpis=kpis,
                charts=charts,
                recent_activity=recent_activity,
                agent_status=agent_status,
                pipeline_summary=pipeline_summary,
                alerts=alerts,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {str(e)}")
            raise
    
    async def calculate_all_kpis(self, db: Session, start_time: datetime, end_time: datetime) -> List[KPIResult]:
        """Calculate all defined KPIs"""
        kpis = []
        
        for kpi_key, kpi_def in self.kpi_definitions.items():
            try:
                kpi_result = await self.calculate_kpi(db, kpi_key, kpi_def, start_time, end_time)
                kpis.append(kpi_result)
            except Exception as e:
                logger.error(f"Failed to calculate KPI {kpi_key}: {str(e)}")
                # Add error KPI
                kpis.append(KPIResult(
                    name=kpi_def["name"],
                    value=0,
                    unit=kpi_def["unit"],
                    metadata={"error": str(e)}
                ))
        
        return kpis
    
    async def calculate_kpi(self, db: Session, kpi_key: str, kpi_def: Dict, 
                           start_time: datetime, end_time: datetime) -> KPIResult:
        """Calculate a specific KPI"""
        calculation_type = kpi_def["calculation"]
        
        if kpi_key == "total_candidates":
            value = db.query(Candidate).count()
            
        elif kpi_key == "candidates_this_week":
            value = db.query(Candidate)\
                     .filter(Candidate.created_at >= start_time)\
                     .count()
            
        elif kpi_key == "average_resume_score":
            result = db.query(func.avg(Candidate.resume_score))\
                       .filter(Candidate.resume_score.isnot(None))\
                       .scalar()
            value = float(result) if result else 0.0
            
        elif kpi_key == "time_to_schedule":
            # Calculate average time from candidate creation to interview scheduling
            interviews = db.query(Interview, Candidate)\
                          .join(Candidate, Interview.candidate_id == Candidate.id)\
                          .filter(Interview.created_at >= start_time)\
                          .all()
            
            if interviews:
                total_hours = 0
                count = 0
                for interview, candidate in interviews:
                    time_diff = interview.created_at - candidate.created_at
                    total_hours += time_diff.total_seconds() / 3600
                    count += 1
                value = total_hours / count if count > 0 else 0
            else:
                value = 0
                
        elif kpi_key == "interview_success_rate":
            total_interviews = db.query(Interview)\
                                .filter(Interview.created_at >= start_time)\
                                .count()
            successful_interviews = db.query(Interview)\
                                     .filter(
                                         Interview.created_at >= start_time,
                                         Interview.status.in_(["scheduled", "completed"])
                                     )\
                                     .count()
            value = (successful_interviews / total_interviews * 100) if total_interviews > 0 else 0
            
        elif kpi_key == "communication_delivery_rate":
            total_messages = db.query(CommunicationMessage)\
                              .filter(CommunicationMessage.created_at >= start_time)\
                              .count()
            delivered_messages = db.query(CommunicationMessage)\
                                  .filter(
                                      CommunicationMessage.created_at >= start_time,
                                      CommunicationMessage.status.in_(["sent", "delivered"])
                                  )\
                                  .count()
            value = (delivered_messages / total_messages * 100) if total_messages > 0 else 0
            
        elif kpi_key == "automation_rate":
            # Calculate based on auto-scheduled interviews and automated communications
            total_interviews = db.query(Interview).count()
            auto_interviews = db.query(Interview)\
                               .filter(Interview.auto_scheduled == True)\
                               .count()
            value = (auto_interviews / total_interviews * 100) if total_interviews > 0 else 0
            
        elif kpi_key == "agent_uptime":
            # Simplified uptime calculation (in production, this would track actual downtime)
            value = 99.5  # Placeholder value
            
        else:
            value = 0
        
        # Get previous value for comparison
        previous_value = await self.get_previous_kpi_value(db, kpi_key, start_time)
        
        # Calculate trend
        trend = "stable"
        change_percentage = None
        if previous_value is not None and previous_value > 0:
            change_percentage = ((value - previous_value) / previous_value) * 100
            if change_percentage > 5:
                trend = "improving"
            elif change_percentage < -5:
                trend = "declining"
        
        return KPIResult(
            name=kpi_def["name"],
            value=value,
            previous_value=previous_value,
            target_value=kpi_def.get("target"),
            unit=kpi_def["unit"],
            change_percentage=change_percentage,
            trend=trend,
            metadata={
                "category": kpi_def["category"],
                "period": f"{start_time.isoformat()} to {end_time.isoformat()}"
            }
        )
    
    async def get_previous_kpi_value(self, db: Session, kpi_key: str, current_start: datetime) -> Optional[float]:
        """Get previous period value for KPI comparison"""
        try:
            # Simplified for Phase 4 - return None for now
            # In full implementation, this would query DashboardMetric table
            return None
            
        except Exception as e:
            logger.error(f"Failed to get previous KPI value for {kpi_key}: {str(e)}")
            return None
    
    async def generate_chart_data(self, db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate data for various charts"""
        try:
            charts = {}
            
            # Candidates over time
            charts["candidates_timeline"] = await self.get_candidates_timeline(db, start_time, end_time)
            
            # Interview success rate over time
            charts["interview_success"] = await self.get_interview_success_timeline(db, start_time, end_time)
            
            # Communication volume
            charts["communication_volume"] = await self.get_communication_volume(db, start_time, end_time)
            
            # Pipeline funnel
            charts["pipeline_funnel"] = await self.get_pipeline_funnel_data(db)
            
            # Agent performance comparison
            charts["agent_performance"] = await self.get_agent_performance_comparison(db)
            
            return charts
            
        except Exception as e:
            logger.error(f"Failed to generate chart data: {str(e)}")
            return {}
    
    async def get_candidates_timeline(self, db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get candidates added over time"""
        try:
            # Group candidates by day
            candidates_by_day = db.query(
                func.date(Candidate.created_at).label('date'),
                func.count(Candidate.id).label('count')
            )\
            .filter(Candidate.created_at >= start_time)\
            .group_by(func.date(Candidate.created_at))\
            .order_by(func.date(Candidate.created_at))\
            .all()
            
            return {
                "chart_type": "line",
                "title": "Candidates Added Over Time",
                "data": [
                    {
                        "date": day.date.isoformat(),
                        "count": day.count
                    }
                    for day in candidates_by_day
                ],
                "x_axis": "date",
                "y_axis": "count"
            }
            
        except Exception as e:
            logger.error(f"Failed to get candidates timeline: {str(e)}")
            return {"chart_type": "line", "data": [], "error": str(e)}
    
    async def get_interview_success_timeline(self, db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get interview success rate over time"""
        try:
            # Get interview success by day
            interview_stats = db.query(
                func.date(Interview.created_at).label('date'),
                func.count(Interview.id).label('total'),
                func.sum(
                    func.case(
                        (Interview.status.in_(["scheduled", "completed"]), 1),
                        else_=0
                    )
                ).label('successful')
            )\
            .filter(Interview.created_at >= start_time)\
            .group_by(func.date(Interview.created_at))\
            .order_by(func.date(Interview.created_at))\
            .all()
            
            return {
                "chart_type": "line",
                "title": "Interview Success Rate Over Time",
                "data": [
                    {
                        "date": stat.date.isoformat(),
                        "success_rate": (stat.successful / stat.total * 100) if stat.total > 0 else 0,
                        "total_interviews": stat.total
                    }
                    for stat in interview_stats
                ],
                "x_axis": "date",
                "y_axis": "success_rate"
            }
            
        except Exception as e:
            logger.error(f"Failed to get interview success timeline: {str(e)}")
            return {"chart_type": "line", "data": [], "error": str(e)}
    
    async def get_communication_volume(self, db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get communication volume by type"""
        try:
            comm_stats = db.query(
                CommunicationMessage.communication_type,
                func.count(CommunicationMessage.id).label('count')
            )\
            .filter(CommunicationMessage.created_at >= start_time)\
            .group_by(CommunicationMessage.communication_type)\
            .all()
            
            return {
                "chart_type": "pie",
                "title": "Communication Volume by Type",
                "data": [
                    {
                        "type": stat.communication_type,
                        "count": stat.count
                    }
                    for stat in comm_stats
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get communication volume: {str(e)}")
            return {"chart_type": "pie", "data": [], "error": str(e)}
    
    async def get_pipeline_funnel_data(self, db: Session) -> Dict[str, Any]:
        """Get recruitment pipeline funnel data"""
        try:
            # Get current pipeline state
            pipeline_stats = db.query(
                RecruitmentPipeline.current_stage,
                func.count(RecruitmentPipeline.id).label('count')
            )\
            .filter(RecruitmentPipeline.is_active == True)\
            .group_by(RecruitmentPipeline.current_stage)\
            .all()
            
            # Define standard pipeline stages
            stages = ["applied", "screened", "interviewed", "offered", "hired"]
            stage_data = {stage: 0 for stage in stages}
            
            # Map actual data to standard stages
            for stat in pipeline_stats:
                stage = stat.current_stage.lower()
                if stage in stage_data:
                    stage_data[stage] = stat.count
                elif "screen" in stage or "review" in stage:
                    stage_data["screened"] += stat.count
                elif "interview" in stage:
                    stage_data["interviewed"] += stat.count
                elif "offer" in stage:
                    stage_data["offered"] += stat.count
                elif "hire" in stage or "accept" in stage:
                    stage_data["hired"] += stat.count
                else:
                    stage_data["applied"] += stat.count
            
            return {
                "chart_type": "funnel",
                "title": "Recruitment Pipeline",
                "data": [
                    {"stage": stage.title(), "count": count}
                    for stage, count in stage_data.items()
                    if count > 0
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get pipeline funnel data: {str(e)}")
            return {"chart_type": "funnel", "data": [], "error": str(e)}
    
    async def get_agent_performance_comparison(self, db: Session) -> Dict[str, Any]:
        """Get agent performance comparison"""
        try:
            # Get latest performance for each agent
            agents = ["Resume Analyzer", "Scheduler", "Communication"]
            performance_data = []
            
            for agent in agents:
                perf = db.query(AgentPerformance)\
                        .filter(AgentPerformance.agent_name == agent)\
                        .order_by(desc(AgentPerformance.created_at))\
                        .first()
                
                if perf:
                    performance_data.append({
                        "agent": agent,
                        "success_rate": perf.success_rate,
                        "response_time": perf.average_response_time or 0,
                        "health_score": perf.health_score or 100
                    })
                else:
                    performance_data.append({
                        "agent": agent,
                        "success_rate": 0,
                        "response_time": 0,
                        "health_score": 0
                    })
            
            return {
                "chart_type": "bar",
                "title": "Agent Performance Comparison",
                "data": performance_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get agent performance comparison: {str(e)}")
            return {"chart_type": "bar", "data": [], "error": str(e)}
    
    async def get_recent_activity(self, db: Session, limit: int = 10) -> List[Dict]:
        """Get recent system activity"""
        try:
            activities = db.query(UserActivity)\
                          .order_by(desc(UserActivity.created_at))\
                          .limit(limit)\
                          .all()
            
            return [activity.to_dict() for activity in activities]
            
        except Exception as e:
            logger.error(f"Failed to get recent activity: {str(e)}")
            return []
    
    async def get_agent_status_summary(self, db: Session) -> Dict[str, Any]:
        """Get summary of all agent statuses"""
        try:
            agents = ["Resume Analyzer", "Scheduler", "Communication"]
            status_summary = {}
            
            for agent in agents:
                latest_perf = db.query(AgentPerformance)\
                               .filter(AgentPerformance.agent_name == agent)\
                               .order_by(desc(AgentPerformance.created_at))\
                               .first()
                
                if latest_perf:
                    status_summary[agent] = {
                        "status": "healthy" if latest_perf.is_healthy else "unhealthy",
                        "health_score": latest_perf.health_score or 0,
                        "success_rate": latest_perf.success_rate,
                        "response_time": latest_perf.average_response_time or 0,
                        "last_updated": latest_perf.updated_at.isoformat()
                    }
                else:
                    status_summary[agent] = {
                        "status": "unknown",
                        "health_score": 0,
                        "success_rate": 0,
                        "response_time": 0,
                        "last_updated": None
                    }
            
            return status_summary
            
        except Exception as e:
            logger.error(f"Failed to get agent status summary: {str(e)}")
            return {}
    
    async def get_pipeline_summary(self, db: Session) -> Dict[str, Any]:
        """Get recruitment pipeline summary"""
        try:
            # Active candidates in pipeline
            active_candidates = db.query(RecruitmentPipeline)\
                                 .filter(RecruitmentPipeline.is_active == True)\
                                 .count()
            
            # Average time in pipeline
            avg_time = db.query(func.avg(RecruitmentPipeline.total_time_in_pipeline))\
                        .filter(RecruitmentPipeline.is_active == True)\
                        .scalar()
            
            # Completion rate (hired + rejected vs total)
            total_completed = db.query(RecruitmentPipeline)\
                               .filter(RecruitmentPipeline.is_active == False)\
                               .count()
            
            hired_count = db.query(RecruitmentPipeline)\
                           .filter(RecruitmentPipeline.final_outcome == "hired")\
                           .count()
            
            return {
                "active_candidates": active_candidates,
                "average_time_hours": float(avg_time) / 60 if avg_time else 0,  # Convert minutes to hours
                "completion_rate": total_completed,
                "hire_rate": (hired_count / total_completed * 100) if total_completed > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get pipeline summary: {str(e)}")
            return {}
    
    async def get_system_alerts(self, db: Session) -> List[Dict]:
        """Get system alerts and warnings"""
        try:
            alerts = []
            
            # Check agent performance
            for agent in ["Resume Analyzer", "Scheduler", "Communication"]:
                latest_perf = db.query(AgentPerformance)\
                               .filter(AgentPerformance.agent_name == agent)\
                               .order_by(desc(AgentPerformance.created_at))\
                               .first()
                
                if latest_perf:
                    if latest_perf.success_rate < self.performance_thresholds["success_rate_critical"]:
                        alerts.append({
                            "type": "critical",
                            "category": "agent_performance",
                            "message": f"{agent} success rate critically low: {latest_perf.success_rate:.1f}%",
                            "agent": agent,
                            "value": latest_perf.success_rate,
                            "threshold": self.performance_thresholds["success_rate_critical"] * 100
                        })
                    elif latest_perf.success_rate < self.performance_thresholds["success_rate_warning"]:
                        alerts.append({
                            "type": "warning",
                            "category": "agent_performance",
                            "message": f"{agent} success rate low: {latest_perf.success_rate:.1f}%",
                            "agent": agent,
                            "value": latest_perf.success_rate,
                            "threshold": self.performance_thresholds["success_rate_warning"] * 100
                        })
                    
                    if (latest_perf.average_response_time and 
                        latest_perf.average_response_time > self.performance_thresholds["response_time_critical"]):
                        alerts.append({
                            "type": "critical",
                            "category": "response_time",
                            "message": f"{agent} response time critically high: {latest_perf.average_response_time:.0f}ms",
                            "agent": agent,
                            "value": latest_perf.average_response_time,
                            "threshold": self.performance_thresholds["response_time_critical"]
                        })
            
            # Check for stuck candidates in pipeline
            stuck_candidates = db.query(RecruitmentPipeline)\
                                .filter(
                                    RecruitmentPipeline.is_active == True,
                                    RecruitmentPipeline.stage_entry_time < datetime.utcnow() - timedelta(days=7)
                                )\
                                .count()
            
            if stuck_candidates > 0:
                alerts.append({
                    "type": "warning",
                    "category": "pipeline_stuck",
                    "message": f"{stuck_candidates} candidates stuck in pipeline for over 7 days",
                    "count": stuck_candidates
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to get system alerts: {str(e)}")
            return []
    
    async def store_kpi_metrics(self, db: Session, kpis: List[KPIResult], period_start: datetime, period_end: datetime):
        """Store calculated KPIs in database for historical tracking"""
        try:
            for kpi in kpis:
                metric = DashboardMetric(
                    metric_name=kpi.name.lower().replace(" ", "_"),
                    metric_type=kpi.metadata.get("category", "unknown") if kpi.metadata else "unknown",
                    category="dashboard_kpi",
                    value=kpi.value,
                    previous_value=kpi.previous_value,
                    target_value=kpi.target_value,
                    metadata=kpi.metadata,
                    period_start=period_start,
                    period_end=period_end,
                    agent_source="dashboard_agent"
                )
                
                db.add(metric)
            
            db.commit()
            logger.info(f"Stored {len(kpis)} KPI metrics")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to store KPI metrics: {str(e)}")
    
    async def generate_automated_report(self, db: Session, report_type: str = "daily") -> Dict[str, Any]:
        """Generate an automated system report"""
        try:
            # Determine time range based on report type
            end_time = datetime.utcnow()
            if report_type == "daily":
                start_time = end_time - timedelta(days=1)
            elif report_type == "weekly":
                start_time = end_time - timedelta(days=7)
            elif report_type == "monthly":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(days=1)
            
            # Get dashboard data
            dashboard_data = await self.get_dashboard_data(db, f"{int((end_time - start_time).total_seconds() / 3600)}h")
            
            # Generate insights and recommendations
            insights = await self.generate_insights(dashboard_data)
            recommendations = await self.generate_recommendations(dashboard_data)
            
            # Create report
            report = SystemReport(
                report_name=f"{report_type.title()} System Report",
                report_type=report_type,
                category="automated",
                period_start=start_time,
                period_end=end_time,
                summary_metrics={
                    "total_kpis": len(dashboard_data.kpis),
                    "alerts_count": len(dashboard_data.alerts),
                    "active_candidates": dashboard_data.pipeline_summary.get("active_candidates", 0)
                },
                detailed_data={
                    "kpis": [kpi.__dict__ for kpi in dashboard_data.kpis],
                    "charts": dashboard_data.charts,
                    "agent_status": dashboard_data.agent_status,
                    "pipeline": dashboard_data.pipeline_summary
                },
                insights=insights,
                recommendations=recommendations,
                generated_by="dashboard_agent"
            )
            
            db.add(report)
            db.commit()
            db.refresh(report)
            
            logger.info(f"Generated {report_type} report: {report.id}")
            return report.to_dict()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to generate automated report: {str(e)}")
            return {"error": str(e)}
    
    async def generate_insights(self, dashboard_data: DashboardData) -> List[Dict]:
        """Generate AI-powered insights from dashboard data"""
        insights = []
        
        try:
            # Analyze KPI trends
            for kpi in dashboard_data.kpis:
                if kpi.trend == "declining" and kpi.change_percentage and kpi.change_percentage < -10:
                    insights.append({
                        "type": "performance_decline",
                        "severity": "high",
                        "title": f"{kpi.name} Declining Significantly",
                        "description": f"{kpi.name} has decreased by {abs(kpi.change_percentage):.1f}% in the current period.",
                        "impact": "This may indicate system issues or process bottlenecks that need attention.",
                        "kpi": kpi.name
                    })
                elif kpi.trend == "improving" and kpi.change_percentage and kpi.change_percentage > 20:
                    insights.append({
                        "type": "performance_improvement",
                        "severity": "positive",
                        "title": f"{kpi.name} Showing Strong Improvement",
                        "description": f"{kpi.name} has increased by {kpi.change_percentage:.1f}% in the current period.",
                        "impact": "Current strategies are working well and should be maintained or expanded.",
                        "kpi": kpi.name
                    })
            
            # Analyze alerts
            if len(dashboard_data.alerts) > 5:
                insights.append({
                    "type": "system_health",
                    "severity": "medium",
                    "title": "Multiple System Alerts Detected",
                    "description": f"There are currently {len(dashboard_data.alerts)} active alerts in the system.",
                    "impact": "System performance may be degraded. Review and address alerts promptly."
                })
            
            # Pipeline analysis
            if dashboard_data.pipeline_summary.get("active_candidates", 0) > 50:
                insights.append({
                    "type": "pipeline_volume",
                    "severity": "medium", 
                    "title": "High Volume in Recruitment Pipeline",
                    "description": f"There are {dashboard_data.pipeline_summary['active_candidates']} active candidates in the pipeline.",
                    "impact": "Consider increasing automation or adding resources to handle the increased volume."
                })
            
        except Exception as e:
            logger.error(f"Failed to generate insights: {str(e)}")
            insights.append({
                "type": "error",
                "severity": "low",
                "title": "Insight Generation Error",
                "description": f"Unable to generate some insights: {str(e)}"
            })
        
        return insights
    
    async def generate_recommendations(self, dashboard_data: DashboardData) -> List[Dict]:
        """Generate actionable recommendations based on data"""
        recommendations = []
        
        try:
            # Agent performance recommendations
            for agent, status in dashboard_data.agent_status.items():
                if status.get("health_score", 0) < 80:
                    recommendations.append({
                        "category": "agent_optimization",
                        "priority": "high",
                        "title": f"Optimize {agent} Performance",
                        "description": f"{agent} health score is {status.get('health_score', 0):.1f}%. Consider reviewing configuration and resource allocation.",
                        "actions": [
                            "Review agent logs for errors",
                            "Check resource utilization",
                            "Consider scaling or optimization"
                        ]
                    })
            
            # Communication recommendations
            comm_kpi = next((kpi for kpi in dashboard_data.kpis if "communication" in kpi.name.lower()), None)
            if comm_kpi and comm_kpi.value < 90:
                recommendations.append({
                    "category": "communication",
                    "priority": "medium",
                    "title": "Improve Communication Delivery",
                    "description": f"Communication delivery rate is {comm_kpi.value:.1f}%. Consider reviewing email/SMS configuration.",
                    "actions": [
                        "Verify email service configuration",
                        "Check SMS provider settings",
                        "Review bounce and failure logs"
                    ]
                })
            
            # Pipeline recommendations
            if dashboard_data.pipeline_summary.get("average_time_hours", 0) > 72:
                recommendations.append({
                    "category": "process_efficiency",
                    "priority": "medium",
                    "title": "Reduce Pipeline Time",
                    "description": f"Average time in pipeline is {dashboard_data.pipeline_summary['average_time_hours']:.1f} hours. Consider increasing automation.",
                    "actions": [
                        "Enable more automated screening",
                        "Implement faster interview scheduling",
                        "Review manual approval steps"
                    ]
                })
            
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {str(e)}")
            recommendations.append({
                "category": "system",
                "priority": "low",
                "title": "Recommendation Generation Error",
                "description": f"Unable to generate some recommendations: {str(e)}"
            })
        
        return recommendations
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get Dashboard Agent status"""
        return {
            "agent_name": "Dashboard Agent",
            "version": "1.0.0",
            "status": "operational",
            "kpis_defined": len(self.kpi_definitions),
            "widget_templates": len(self.widget_templates),
            "features": [
                "Real-time KPI calculation",
                "Agent performance monitoring", 
                "Pipeline analytics",
                "Automated reporting",
                "Predictive insights",
                "Custom dashboards"
            ],
            "timestamp": datetime.utcnow().isoformat()
        }

# Global instance
dashboard_agent = None

def get_dashboard_agent() -> DashboardAgent:
    """Get or create the global Dashboard Agent instance"""
    global dashboard_agent
    if dashboard_agent is None:
        dashboard_agent = DashboardAgent()
    return dashboard_agent 