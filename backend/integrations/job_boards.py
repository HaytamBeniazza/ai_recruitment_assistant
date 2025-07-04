"""
Job Board Integrations for RecruitAI Pro
Connect to real job posting platforms and ATS systems
"""

import requests
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import logging

from core.database import get_db
from models.jobs import JobPosition
from models.candidates import Candidate

logger = logging.getLogger(__name__)

@dataclass
class JobBoardConfig:
    """Configuration for job board integrations"""
    name: str
    api_url: str
    api_key: str
    company_id: str
    enabled: bool = True
    sync_interval_hours: int = 24

class JobBoardIntegrator:
    """Handles integration with multiple job boards"""
    
    def __init__(self):
        self.integrations = {
            'indeed': self._indeed_integration,
            'linkedin': self._linkedin_integration,
            'glassdoor': self._glassdoor_integration,
            'workday': self._workday_integration
        }
    
    async def sync_jobs_from_all_boards(self, configs: List[JobBoardConfig]) -> Dict[str, Any]:
        """Sync jobs from all configured job boards"""
        results = {}
        
        for config in configs:
            if not config.enabled:
                continue
                
            try:
                logger.info(f"🔄 Syncing jobs from {config.name}")
                result = await self._sync_from_board(config)
                results[config.name] = result
                logger.info(f"✅ {config.name}: {result['jobs_created']} jobs created")
                
            except Exception as e:
                logger.error(f"❌ Error syncing from {config.name}: {str(e)}")
                results[config.name] = {'error': str(e), 'jobs_created': 0}
        
        return results
    
    async def _sync_from_board(self, config: JobBoardConfig) -> Dict[str, Any]:
        """Sync jobs from a specific job board"""
        integration_func = self.integrations.get(config.name.lower())
        
        if not integration_func:
            raise ValueError(f"No integration available for {config.name}")
        
        return await integration_func(config)
    
    async def _indeed_integration(self, config: JobBoardConfig) -> Dict[str, Any]:
        """Integration with Indeed API"""
        try:
            # Indeed API integration
            headers = {
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json'
            }
            
            # Get jobs posted in last 24 hours
            params = {
                'company_id': config.company_id,
                'status': 'active',
                'posted_since': (datetime.now() - timedelta(hours=24)).isoformat()
            }
            
            response = requests.get(
                f"{config.api_url}/jobs",
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                jobs_data = response.json()
                created_count = await self._create_jobs_from_data(jobs_data, 'indeed')
                return {
                    'success': True,
                    'jobs_created': created_count,
                    'total_found': len(jobs_data)
                }
            else:
                raise Exception(f"API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Indeed integration error: {str(e)}")
            return {'success': False, 'error': str(e), 'jobs_created': 0}
    
    async def _linkedin_integration(self, config: JobBoardConfig) -> Dict[str, Any]:
        """Integration with LinkedIn Jobs API"""
        try:
            # LinkedIn API integration
            headers = {
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json',
                'X-Restli-Protocol-Version': '2.0.0'
            }
            
            # Get company job postings
            response = requests.get(
                f"{config.api_url}/jobPostings",
                headers=headers,
                params={'company': config.company_id},
                timeout=30
            )
            
            if response.status_code == 200:
                jobs_data = response.json()['elements']
                created_count = await self._create_jobs_from_data(jobs_data, 'linkedin')
                return {
                    'success': True,
                    'jobs_created': created_count,
                    'total_found': len(jobs_data)
                }
            else:
                raise Exception(f"LinkedIn API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"LinkedIn integration error: {str(e)}")
            return {'success': False, 'error': str(e), 'jobs_created': 0}
    
    async def _glassdoor_integration(self, config: JobBoardConfig) -> Dict[str, Any]:
        """Integration with Glassdoor API"""
        try:
            # Glassdoor API integration
            headers = {
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{config.api_url}/employer/{config.company_id}/jobs",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                jobs_data = response.json()
                created_count = await self._create_jobs_from_data(jobs_data, 'glassdoor')
                return {
                    'success': True,
                    'jobs_created': created_count,
                    'total_found': len(jobs_data)
                }
            else:
                raise Exception(f"Glassdoor API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Glassdoor integration error: {str(e)}")
            return {'success': False, 'error': str(e), 'jobs_created': 0}
    
    async def _workday_integration(self, config: JobBoardConfig) -> Dict[str, Any]:
        """Integration with Workday ATS"""
        try:
            # Workday API integration
            headers = {
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{config.api_url}/recruiting/jobRequisitions",
                headers=headers,
                params={'company': config.company_id},
                timeout=30
            )
            
            if response.status_code == 200:
                jobs_data = response.json()
                created_count = await self._create_jobs_from_data(jobs_data, 'workday')
                return {
                    'success': True,
                    'jobs_created': created_count,
                    'total_found': len(jobs_data)
                }
            else:
                raise Exception(f"Workday API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Workday integration error: {str(e)}")
            return {'success': False, 'error': str(e), 'jobs_created': 0}
    
    async def _create_jobs_from_data(self, jobs_data: List[Dict], source: str) -> int:
        """Create job positions from external data"""
        created_count = 0
        
        async with get_db() as db:
            for job_data in jobs_data:
                try:
                    # Transform external data to internal format
                    job_position = self._transform_job_data(job_data, source)
                    
                    # Check if job already exists
                    existing = db.query(JobPosition).filter(
                        JobPosition.title == job_position.title,
                        JobPosition.department == job_position.department
                    ).first()
                    
                    if not existing:
                        db.add(job_position)
                        created_count += 1
                        
                except Exception as e:
                    logger.error(f"Error creating job from {source}: {str(e)}")
                    continue
            
            db.commit()
        
        return created_count
    
    def _transform_job_data(self, job_data: Dict, source: str) -> JobPosition:
        """Transform external job data to internal JobPosition format"""
        # This would need to be customized per integration
        # Here's a generic transformation
        
        return JobPosition(
            title=job_data.get('title', ''),
            department=job_data.get('department', 'Unknown'),
            location=job_data.get('location', 'Remote'),
            employment_type=job_data.get('type', 'full_time'),
            description=job_data.get('description', ''),
            required_skills=job_data.get('skills', []),
            salary_min=job_data.get('salary_min'),
            salary_max=job_data.get('salary_max'),
            status='open',
            # Add metadata about source
            requirements=job_data.get('requirements', {}),
            # Source tracking
            hiring_manager=f"Imported from {source}"
        )

# Example usage configuration
EXAMPLE_CONFIGS = [
    JobBoardConfig(
        name="indeed",
        api_url="https://api.indeed.com/v1",
        api_key="your_indeed_api_key",
        company_id="your_company_id"
    ),
    JobBoardConfig(
        name="linkedin",
        api_url="https://api.linkedin.com/v2",
        api_key="your_linkedin_api_key",
        company_id="your_company_id"
    ),
    JobBoardConfig(
        name="workday",
        api_url="https://your-tenant.workday.com/api",
        api_key="your_workday_api_key",
        company_id="your_company_id"
    )
]

# Initialize integrator
job_board_integrator = JobBoardIntegrator()

# Example scheduled sync function
async def scheduled_job_sync():
    """Function to be called by scheduler (cron job, etc.)"""
    logger.info("🔄 Starting scheduled job board sync")
    results = await job_board_integrator.sync_jobs_from_all_boards(EXAMPLE_CONFIGS)
    
    total_created = sum(result.get('jobs_created', 0) for result in results.values())
    logger.info(f"✅ Scheduled sync completed: {total_created} jobs created")
    
    return results 