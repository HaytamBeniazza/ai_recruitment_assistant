"""
RecruitAI Pro Data Manager
Comprehensive data management tool for both real and fake data integration

Usage:
    python data_manager.py --mode real --source email
    python data_manager.py --mode fake --count 10
    python data_manager.py --mode status
"""

import argparse
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import json

# Import integration modules
from integrations.job_boards import job_board_integrator, JobBoardConfig
from integrations.resume_sources import resume_source_integrator, EmailConfig, CloudStorageConfig
from integrations.webhooks import webhook_processor

# Import existing sample data generators
from create_sample_data import create_jobs, create_candidates, create_interviews, create_communications
from sample_data import fake

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataManager:
    """Unified data management system"""
    
    def __init__(self):
        self.stats = {
            'jobs_created': 0,
            'candidates_created': 0,
            'interviews_created': 0,
            'communications_sent': 0,
            'errors': []
        }
    
    async def run_real_data_integration(self, source: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Run real data integration from specified source"""
        logger.info(f"🔄 Starting real data integration from {source}")
        
        try:
            if source == 'job_boards':
                return await self._integrate_job_boards(config)
            elif source == 'email':
                return await self._integrate_email_resumes(config)
            elif source == 'cloud_storage':
                return await self._integrate_cloud_storage(config)
            elif source == 'webhooks':
                return await self._setup_webhooks(config)
            elif source == 'all':
                return await self._integrate_all_sources(config)
            else:
                raise ValueError(f"Unknown source: {source}")
                
        except Exception as e:
            logger.error(f"❌ Real data integration failed: {str(e)}")
            self.stats['errors'].append(f"Real data integration: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def run_fake_data_generation(self, count: int = 10) -> Dict[str, Any]:
        """Generate fake data for testing and development"""
        logger.info(f"🎭 Generating {count} fake data records")
        
        try:
            # Generate jobs
            jobs_result = await create_jobs(count // 2)
            self.stats['jobs_created'] += jobs_result.get('created', 0)
            
            # Generate candidates
            candidates_result = await create_candidates(count)
            self.stats['candidates_created'] += candidates_result.get('created', 0)
            
            # Generate interviews
            interviews_result = await create_interviews(count // 3)
            self.stats['interviews_created'] += interviews_result.get('created', 0)
            
            # Generate communications
            comms_result = await create_communications(count // 2)
            self.stats['communications_sent'] += comms_result.get('sent', 0)
            
            logger.info(f"✅ Fake data generation completed")
            
            return {
                'success': True,
                'stats': self.stats,
                'message': f'Generated {count} fake data records'
            }
            
        except Exception as e:
            logger.error(f"❌ Fake data generation failed: {str(e)}")
            self.stats['errors'].append(f"Fake data generation: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _integrate_job_boards(self, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Integrate with job boards"""
        logger.info("🔍 Integrating with job boards")
        
        # Use provided config or defaults
        if config:
            job_configs = [
                JobBoardConfig(
                    name=cfg['name'],
                    api_url=cfg['api_url'],
                    api_key=cfg['api_key'],
                    company_id=cfg['company_id']
                )
                for cfg in config.get('job_boards', [])
            ]
        else:
            # Demo configuration (will fail without real API keys)
            job_configs = [
                JobBoardConfig(
                    name="indeed",
                    api_url="https://api.indeed.com/v1",
                    api_key="demo_key_replace_with_real",
                    company_id="demo_company_id"
                )
            ]
        
        result = await job_board_integrator.sync_jobs_from_all_boards(job_configs)
        
        # Update stats
        for board_result in result.values():
            self.stats['jobs_created'] += board_result.get('jobs_created', 0)
        
        return {
            'success': True,
            'source': 'job_boards',
            'results': result,
            'jobs_created': sum(r.get('jobs_created', 0) for r in result.values())
        }
    
    async def _integrate_email_resumes(self, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Integrate with email resume processing"""
        logger.info("📧 Integrating with email resume processing")
        
        # Use provided config or defaults
        if config and 'email' in config:
            email_config = EmailConfig(**config['email'])
        else:
            # Demo configuration
            email_config = EmailConfig(
                server="imap.gmail.com",
                port=993,
                username="demo@company.com",
                password="demo_password_replace_with_real"
            )
        
        result = await resume_source_integrator.process_email_resumes(email_config)
        
        # Update stats
        self.stats['candidates_created'] += result.get('processed_count', 0)
        
        return {
            'success': result.get('success', False),
            'source': 'email',
            'processed_count': result.get('processed_count', 0),
            'total_emails': result.get('total_emails', 0)
        }
    
    async def _integrate_cloud_storage(self, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Integrate with cloud storage resume processing"""
        logger.info("☁️ Integrating with cloud storage")
        
        # Use provided config or defaults
        if config and 'cloud_storage' in config:
            cloud_config = CloudStorageConfig(**config['cloud_storage'])
        else:
            # Demo configuration
            cloud_config = CloudStorageConfig(
                provider="aws",
                credentials={
                    "access_key": "demo_access_key",
                    "secret_key": "demo_secret_key"
                },
                bucket_name="demo-resumes"
            )
        
        result = await resume_source_integrator.process_cloud_storage_resumes(cloud_config)
        
        # Update stats
        self.stats['candidates_created'] += result.get('processed_count', 0)
        
        return {
            'success': result.get('success', False),
            'source': 'cloud_storage',
            'processed_count': result.get('processed_count', 0)
        }
    
    async def _setup_webhooks(self, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Setup webhook endpoints"""
        logger.info("🔗 Setting up webhook endpoints")
        
        # Webhooks are already set up in the FastAPI app
        # This function provides information about available endpoints
        
        webhook_info = {
            'endpoints': [
                'POST /webhooks/indeed',
                'POST /webhooks/linkedin',
                'POST /webhooks/workday',
                'POST /webhooks/career-site',
                'POST /webhooks/generic'
            ],
            'required_headers': {
                'indeed': ['X-Indeed-Signature'],
                'linkedin': ['X-LinkedIn-Signature'],
                'workday': ['X-Workday-Signature'],
                'career-site': ['X-Career-Signature'],
                'generic': ['X-Source', 'X-Event-Type', 'X-Signature']
            }
        }
        
        return {
            'success': True,
            'source': 'webhooks',
            'message': 'Webhook endpoints are active',
            'webhook_info': webhook_info
        }
    
    async def _integrate_all_sources(self, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Integrate with all available sources"""
        logger.info("🔄 Integrating with all sources")
        
        results = {}
        
        # Job boards
        try:
            results['job_boards'] = await self._integrate_job_boards(config)
        except Exception as e:
            results['job_boards'] = {'success': False, 'error': str(e)}
        
        # Email resumes
        try:
            results['email'] = await self._integrate_email_resumes(config)
        except Exception as e:
            results['email'] = {'success': False, 'error': str(e)}
        
        # Cloud storage
        try:
            results['cloud_storage'] = await self._integrate_cloud_storage(config)
        except Exception as e:
            results['cloud_storage'] = {'success': False, 'error': str(e)}
        
        # Webhooks
        try:
            results['webhooks'] = await self._setup_webhooks(config)
        except Exception as e:
            results['webhooks'] = {'success': False, 'error': str(e)}
        
        return {
            'success': True,
            'source': 'all',
            'results': results,
            'total_stats': self.stats
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status and data counts"""
        logger.info("📊 Getting system status")
        
        # This would query the database for current counts
        # For demo purposes, returning mock data
        
        return {
            'system_status': 'operational',
            'data_sources': {
                'job_boards': {
                    'enabled': True,
                    'last_sync': '2024-01-15T10:00:00Z',
                    'status': 'configured'
                },
                'email_integration': {
                    'enabled': True,
                    'last_check': '2024-01-15T09:30:00Z',
                    'status': 'configured'
                },
                'cloud_storage': {
                    'enabled': True,
                    'last_sync': '2024-01-15T09:45:00Z',
                    'status': 'configured'
                },
                'webhooks': {
                    'enabled': True,
                    'active_endpoints': 5,
                    'status': 'active'
                }
            },
            'current_stats': self.stats,
            'recommendations': self._get_recommendations()
        }
    
    def _get_recommendations(self) -> List[str]:
        """Get recommendations for data management"""
        recommendations = []
        
        if self.stats['jobs_created'] == 0:
            recommendations.append("Consider adding job positions to improve candidate matching")
        
        if self.stats['candidates_created'] == 0:
            recommendations.append("Add candidate data via real integrations or sample data")
        
        if len(self.stats['errors']) > 0:
            recommendations.append("Review and fix integration errors")
        
        recommendations.append("Set up scheduled data synchronization for production")
        recommendations.append("Configure webhook endpoints for real-time updates")
        
        return recommendations

# Example configuration file format
EXAMPLE_CONFIG = {
    "job_boards": [
        {
            "name": "indeed",
            "api_url": "https://api.indeed.com/v1",
            "api_key": "your_indeed_api_key",
            "company_id": "your_company_id"
        },
        {
            "name": "linkedin",
            "api_url": "https://api.linkedin.com/v2",
            "api_key": "your_linkedin_api_key",
            "company_id": "your_company_id"
        }
    ],
    "email": {
        "server": "imap.gmail.com",
        "port": 993,
        "username": "hr@yourcompany.com",
        "password": "your_email_password",
        "folder": "INBOX",
        "use_ssl": True
    },
    "cloud_storage": {
        "provider": "aws",
        "credentials": {
            "access_key": "your_aws_access_key",
            "secret_key": "your_aws_secret_key",
            "region": "us-east-1"
        },
        "bucket_name": "your-resumes-bucket",
        "folder_path": "incoming/"
    }
}

async def main():
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description='RecruitAI Pro Data Manager')
    parser.add_argument('--mode', choices=['real', 'fake', 'status'], required=True,
                       help='Data management mode')
    parser.add_argument('--source', choices=['job_boards', 'email', 'cloud_storage', 'webhooks', 'all'],
                       help='Data source for real mode')
    parser.add_argument('--count', type=int, default=10,
                       help='Number of fake records to generate')
    parser.add_argument('--config', type=str,
                       help='Configuration file path')
    
    args = parser.parse_args()
    
    # Initialize data manager
    data_manager = DataManager()
    
    # Load configuration if provided
    config = None
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config file: {str(e)}")
            return
    
    # Execute based on mode
    if args.mode == 'real':
        if not args.source:
            logger.error("--source is required for real mode")
            return
        
        result = await data_manager.run_real_data_integration(args.source, config)
        print(json.dumps(result, indent=2))
        
    elif args.mode == 'fake':
        result = await data_manager.run_fake_data_generation(args.count)
        print(json.dumps(result, indent=2))
        
    elif args.mode == 'status':
        status = data_manager.get_status()
        print(json.dumps(status, indent=2))

if __name__ == "__main__":
    asyncio.run(main()) 