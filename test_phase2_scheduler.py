#!/usr/bin/env python3
"""
Phase 2 Scheduler Agent Test Suite
Comprehensive testing for RecruitAI Pro Scheduler functionality
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any

# Base URL for the API
BASE_URL = "http://localhost:8000"

class SchedulerTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.test_data = {}
    
    def log(self, message: str, data: Any = None):
        """Helper function to log test results"""
        print(f"🔹 {message}")
        if data and isinstance(data, dict):
            print(f"   Data: {json.dumps(data, indent=2, default=str)}")
        print()
    
    def test_health_check(self):
        """Test if the scheduler service is healthy"""
        print("🏥 Testing Scheduler Health Check...")
        
        try:
            response = self.session.get(f"{self.base_url}/scheduler/health")
            if response.status_code == 200:
                self.log("✅ Scheduler service is healthy", response.json())
                return True
            else:
                self.log(f"❌ Health check failed with status {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ Health check error: {str(e)}")
            return False
    
    def create_test_candidate(self) -> str:
        """Create a test candidate and return the ID"""
        print("👤 Creating Test Candidate...")
        
        candidate_data = {
            "name": "Alice Johnson",
            "email": "alice.johnson@example.com",
            "phone": "+1-555-0123",
            "experience_years": 5,
            "skills": ["Python", "FastAPI", "SQL", "Docker", "AWS"],
            "education": "BS Computer Science",
            "location": "San Francisco, CA",
            "desired_salary": 120000,
            "availability": "immediate",
            "notes": "Experienced backend developer with strong API skills"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/candidates/",
                json=candidate_data
            )
            
            if response.status_code == 201:
                result = response.json()
                candidate_id = result['data']['candidate']['id']
                self.test_data['candidate_id'] = candidate_id
                self.log("✅ Candidate created successfully")
                print(f"   Candidate ID: {candidate_id}")
                return candidate_id
            else:
                self.log(f"❌ Failed to create candidate: {response.status_code}")
                return None
        except Exception as e:
            self.log(f"❌ Error creating candidate: {str(e)}")
            return None
    
    def create_test_job(self) -> str:
        """Create a test job position and return the ID"""
        print("💼 Creating Test Job Position...")
        
        job_data = {
            "title": "Senior Backend Developer",
            "department": "Engineering",
            "location": "San Francisco, CA",
            "employment_type": "full_time",
            "remote_work_allowed": True,
            "description": "We're looking for a senior backend developer to join our growing team.",
            "requirements": {
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "experience_years": 5,
                "education": "Bachelor's degree preferred"
            },
            "responsibilities": [
                "Design and implement scalable APIs",
                "Optimize database performance",
                "Collaborate with frontend teams"
            ],
            "salary_range": {
                "min": 100000,
                "max": 140000,
                "currency": "USD"
            },
            "benefits": ["Health insurance", "401k", "Flexible PTO"],
            "status": "active"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/jobs/",
                json=job_data
            )
            
            if response.status_code == 201:
                result = response.json()
                job_id = result['data']['job']['id']
                self.test_data['job_id'] = job_id
                self.log("✅ Job position created successfully")
                print(f"   Job ID: {job_id}")
                return job_id
            else:
                self.log(f"❌ Failed to create job: {response.status_code}")
                return None
        except Exception as e:
            self.log(f"❌ Error creating job: {str(e)}")
            return None
    
    def test_find_optimal_slots(self):
        """Test finding optimal time slots for an interview"""
        print("🎯 Testing Optimal Slot Finding...")
        
        if not self.test_data.get('candidate_id') or not self.test_data.get('job_id'):
            self.log("❌ Missing test data - need candidate and job first")
            return False
        
        # Calculate time window (tomorrow to next week)
        earliest_start = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        latest_end = (datetime.now() + timedelta(days=7)).replace(hour=17, minute=0, second=0, microsecond=0)
        
        params = {
            "candidate_id": self.test_data['candidate_id'],
            "job_position_id": self.test_data['job_id'],
            "interview_type": "video_call",
            "interviewer_emails": ["john.smith@company.com", "sarah.wilson@company.com"],
            "duration_minutes": 60,
            "max_slots": 5,
            "earliest_start": earliest_start.isoformat(),
            "latest_end": latest_end.isoformat()
        }
        
        try:
            response = self.session.get(
                f"{self.base_url}/scheduler/optimal-slots",
                params=params
            )
            
            if response.status_code == 200:
                result = response.json()
                optimal_slots = result['data']['optimal_slots']
                self.test_data['optimal_slots'] = optimal_slots
                
                self.log("✅ Found optimal slots successfully")
                print(f"   📊 Total slots found: {len(optimal_slots)}")
                
                if optimal_slots:
                    print(f"   🏆 Best slot: {optimal_slots[0]['start_time']} (Score: {optimal_slots[0]['score']})")
                    for i, slot in enumerate(optimal_slots[:3]):
                        print(f"      Slot {i+1}: {slot['start_time']} - {slot['end_time']} (Score: {slot['score']:.3f})")
                
                return True
            else:
                self.log(f"❌ Failed to find optimal slots: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ Error finding optimal slots: {str(e)}")
            return False
    
    def test_schedule_interview(self):
        """Test scheduling an interview"""
        print("📅 Testing Interview Scheduling...")
        
        if not self.test_data.get('candidate_id') or not self.test_data.get('job_id'):
            self.log("❌ Missing test data - need candidate and job first")
            return False
        
        earliest_start = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        latest_end = (datetime.now() + timedelta(days=5)).replace(hour=16, minute=0, second=0, microsecond=0)
        
        schedule_data = {
            "candidate_id": self.test_data['candidate_id'],
            "job_position_id": self.test_data['job_id'],
            "interview_type": "video_call",
            "interviewer_emails": ["john.smith@company.com", "sarah.wilson@company.com"],
            "duration_minutes": 60,
            "earliest_start": earliest_start.isoformat(),
            "latest_end": latest_end.isoformat(),
            "timezone": "America/Los_Angeles",
            "priority": "medium",
            "strategy": "balanced",
            "requirements": {
                "preparation_time": 30,
                "meeting_type": "video_conference"
            }
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/scheduler/schedule",
                json=schedule_data
            )
            
            if response.status_code == 201:
                result = response.json()
                interview = result['data']['interview']
                self.test_data['interview_id'] = interview['id']
                
                self.log("✅ Interview scheduled successfully!")
                print(f"   📅 Interview ID: {interview['id']}")
                print(f"   🕐 Scheduled: {interview['scheduled_start']} - {interview['scheduled_end']}")
                print(f"   👥 Interviewers: {', '.join(interview['interviewer_emails'])}")
                print(f"   🎯 Score: {result['data']['slot_details']['score']:.3f}")
                
                return True
            else:
                self.log(f"❌ Failed to schedule interview: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ Error scheduling interview: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run the complete test suite"""
        print("🧪 STARTING PHASE 2 SCHEDULER AGENT TEST SUITE")
        print("=" * 60)
        
        test_results = []
        
        # Test 1: Health Check
        test_results.append(("Health Check", self.test_health_check()))
        
        # Test 2: Create Test Data
        candidate_id = self.create_test_candidate()
        job_id = self.create_test_job()
        test_results.append(("Test Data Creation", candidate_id is not None and job_id is not None))
        
        # Test 3: Find Optimal Slots
        test_results.append(("Optimal Slot Finding", self.test_find_optimal_slots()))
        
        # Test 4: Schedule Interview
        test_results.append(("Interview Scheduling", self.test_schedule_interview()))
        
        # Summary
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name:<25} {status}")
            if result:
                passed += 1
        
        print(f"\n🎯 OVERALL RESULT: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! Phase 2 Scheduler Agent is working perfectly!")
        else:
            print("⚠️ Some tests failed. Check the logs above for details.")
        
        return passed == total

if __name__ == "__main__":
    tester = SchedulerTester()
    tester.run_all_tests() 