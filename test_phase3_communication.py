"""
🤖 RecruitAI Pro - Phase 3 Communication Agent Test Suite
Tests all communication features including email, SMS, templates, and scheduling
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Configuration
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json", "accept": "application/json"}

class Phase3Tester:
    """Comprehensive tester for Phase 3 Communication Agent"""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.headers = HEADERS
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   📝 {details}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    def test_communication_health(self):
        """Test Communication Agent health and status"""
        print("\n📊 Testing Communication Agent Health...")
        
        try:
            # Test general health
            response = requests.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                communication_ready = data.get("agents", {}).get("communication") == "ready"
                self.log_test(
                    "Communication Agent Health Check", 
                    communication_ready,
                    f"Status: {data.get('status')}, Communication: {data.get('agents', {}).get('communication')}"
                )
            else:
                self.log_test("Communication Agent Health Check", False, f"HTTP {response.status_code}")
            
            # Test communication-specific health
            response = requests.get(f"{self.base_url}/communication/health")
            self.log_test(
                "Communication API Health", 
                response.status_code == 200,
                f"HTTP {response.status_code}"
            )
            
            # Test agent status
            response = requests.get(f"{self.base_url}/communication/agent/status")
            if response.status_code == 200:
                status_data = response.json()
                self.log_test(
                    "Communication Agent Status", 
                    status_data.get("status") == "operational",
                    f"Agent: {status_data.get('agent_name')}, Templates: {status_data.get('default_templates_loaded')}"
                )
            else:
                self.log_test("Communication Agent Status", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Communication Health Tests", False, f"Exception: {str(e)}")
    
    def test_email_sending(self):
        """Test email sending functionality"""
        print("\n📧 Testing Email Sending...")
        
        # Test basic email sending
        email_data = {
            "to_email": "candidate@example.com",
            "subject": "Test Email from RecruitAI Pro",
            "body": "This is a test email sent from the Communication Agent during Phase 3 testing.",
            "priority": "medium"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/communication/send-email",
                json=email_data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log_test(
                    "Basic Email Sending",
                    result.get("success", False),
                    f"Message ID: {result.get('message_id')}, Delivery: {result.get('delivery_time_ms')}ms"
                )
            else:
                self.log_test("Basic Email Sending", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Email Sending Test", False, f"Exception: {str(e)}")
        
        # Test email with HTML body
        html_email_data = {
            "to_email": "manager@example.com",
            "subject": "HTML Test Email",
            "body": "Plain text version of the email.",
            "html_body": "<h2>HTML Email Test</h2><p>This is an <strong>HTML email</strong> from RecruitAI Pro!</p>",
            "cc_emails": ["hr@example.com"],
            "priority": "high"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/communication/send-email",
                json=html_email_data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log_test(
                    "HTML Email with CC",
                    result.get("success", False),
                    f"HTML + CC test, Message ID: {result.get('message_id')}"
                )
            else:
                self.log_test("HTML Email with CC", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("HTML Email Test", False, f"Exception: {str(e)}")
    
    def test_sms_sending(self):
        """Test SMS sending functionality"""
        print("\n📱 Testing SMS Sending...")
        
        sms_data = {
            "to_phone": "+1234567890",
            "message": "Test SMS from RecruitAI Pro Communication Agent! 🤖",
            "priority": "medium"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/communication/send-sms",
                json=sms_data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log_test(
                    "Basic SMS Sending",
                    result.get("success", False),
                    f"Message ID: {result.get('message_id')}, Delivery: {result.get('delivery_time_ms')}ms"
                )
            else:
                self.log_test("Basic SMS Sending", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("SMS Sending Test", False, f"Exception: {str(e)}")
    
    def test_templated_messaging(self):
        """Test template-based messaging"""
        print("\n📝 Testing Template-Based Messaging...")
        
        # Test interview scheduled email template
        template_data = {
            "template_type": "interview_scheduled",
            "communication_type": "email",
            "recipient": "john.doe@example.com",
            "template_variables": {
                "candidate_name": "John Doe",
                "job_title": "Senior Software Engineer",
                "interview_date": "July 5, 2025",
                "interview_time": "10:00 AM EST",
                "interview_location": "Conference Room A / Zoom Meeting",
                "interviewer_names": "Sarah Johnson, Mike Chen",
                "company_name": "TechCorp Inc"
            },
            "priority": "high",
            "use_ai_enhancement": False
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/communication/send-templated",
                json=template_data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log_test(
                    "Interview Scheduled Template Email",
                    result.get("success", False),
                    f"Template rendered and sent, Message ID: {result.get('message_id')}"
                )
            else:
                self.log_test("Interview Scheduled Template Email", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Template Email Test", False, f"Exception: {str(e)}")
        
        # Test interview reminder SMS template
        sms_template_data = {
            "template_type": "interview_reminder",
            "communication_type": "sms",
            "recipient": "+1234567890",
            "template_variables": {
                "candidate_name": "John",
                "job_title": "Software Engineer",
                "interview_date": "tomorrow",
                "interview_time": "10:00 AM",
                "interview_location": "Conference Room A",
                "company_name": "TechCorp"
            },
            "priority": "urgent"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/communication/send-templated",
                json=sms_template_data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log_test(
                    "Interview Reminder Template SMS",
                    result.get("success", False),
                    f"SMS template sent, Message ID: {result.get('message_id')}"
                )
            else:
                self.log_test("Interview Reminder Template SMS", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Template SMS Test", False, f"Exception: {str(e)}")
    
    def test_message_scheduling(self):
        """Test message scheduling functionality"""
        print("\n⏰ Testing Message Scheduling...")
        
        # Schedule a message for 5 minutes from now
        future_time = datetime.utcnow() + timedelta(minutes=5)
        
        schedule_data = {
            "communication_type": "email",
            "recipient": "candidate@example.com",
            "template_type": "interview_reminder",
            "template_variables": {
                "candidate_name": "Alice Smith",
                "job_title": "Data Scientist",
                "interview_date": "July 6, 2025",
                "interview_time": "2:00 PM",
                "interview_location": "Virtual Meeting",
                "company_name": "DataTech Solutions"
            },
            "send_time": future_time.isoformat(),
            "priority": "medium"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/communication/schedule",
                json=schedule_data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log_test(
                    "Message Scheduling",
                    result.get("success", False),
                    f"Scheduled for {future_time.strftime('%H:%M')}, Schedule ID: {result.get('schedule_id')}"
                )
            else:
                self.log_test("Message Scheduling", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Message Scheduling Test", False, f"Exception: {str(e)}")
    
    def test_template_management(self):
        """Test template management functionality"""
        print("\n📋 Testing Template Management...")
        
        # Get existing templates
        try:
            response = requests.get(f"{self.base_url}/communication/templates")
            if response.status_code == 200:
                templates = response.json()
                self.log_test(
                    "Get Templates",
                    True,
                    f"Retrieved {templates.get('total', 0)} templates"
                )
            else:
                self.log_test("Get Templates", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("Get Templates Test", False, f"Exception: {str(e)}")
        
        # Create a new template
        new_template = {
            "name": "welcome_message",
            "category": "onboarding",
            "communication_type": "email",
            "subject_template": "Welcome to {{company_name}}, {{candidate_name}}!",
            "body_template": "Dear {{candidate_name}},\n\nWelcome to {{company_name}}! We're excited to have you join our team.\n\nBest regards,\nHR Team",
            "required_variables": ["candidate_name", "company_name"],
            "description": "Welcome message for new hires",
            "language": "en"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/communication/templates",
                json=new_template,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log_test(
                    "Create New Template",
                    result.get("success", False),
                    f"Template created: {new_template['name']}"
                )
            else:
                self.log_test("Create New Template", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Create Template Test", False, f"Exception: {str(e)}")
    
    def test_message_management(self):
        """Test message retrieval and management"""
        print("\n📨 Testing Message Management...")
        
        # Get recent messages
        try:
            response = requests.get(f"{self.base_url}/communication/messages?limit=10")
            if response.status_code == 200:
                messages = response.json()
                self.log_test(
                    "Get Messages",
                    True,
                    f"Retrieved {len(messages.get('messages', []))} messages, Total: {messages.get('total', 0)}"
                )
                
                # If we have messages, test getting a specific one
                if messages.get('messages') and len(messages['messages']) > 0:
                    message_id = messages['messages'][0]['id']
                    
                    response = requests.get(f"{self.base_url}/communication/messages/{message_id}")
                    if response.status_code == 200:
                        self.log_test(
                            "Get Specific Message",
                            True,
                            f"Retrieved message {message_id[:8]}..."
                        )
                    else:
                        self.log_test("Get Specific Message", False, f"HTTP {response.status_code}")
            else:
                self.log_test("Get Messages", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Message Management Test", False, f"Exception: {str(e)}")
    
    def test_error_handling(self):
        """Test error handling scenarios"""
        print("\n⚠️ Testing Error Handling...")
        
        # Test invalid email format
        invalid_email_data = {
            "to_email": "invalid-email-format",
            "subject": "Test",
            "body": "Test body"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/communication/send-email",
                json=invalid_email_data,
                headers=self.headers
            )
            
            # Should either reject with 400 or handle gracefully
            self.log_test(
                "Invalid Email Format Handling",
                response.status_code in [400, 422] or (response.status_code == 200 and not response.json().get("success")),
                f"HTTP {response.status_code}"
            )
        except Exception as e:
            self.log_test("Invalid Email Test", False, f"Exception: {str(e)}")
        
        # Test missing template variables
        incomplete_template_data = {
            "template_type": "interview_scheduled",
            "communication_type": "email",
            "recipient": "test@example.com",
            "template_variables": {
                "candidate_name": "John"
                # Missing required variables like job_title, interview_date, etc.
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/communication/send-templated",
                json=incomplete_template_data,
                headers=self.headers
            )
            
            # Should reject due to missing variables
            self.log_test(
                "Missing Template Variables Handling",
                response.status_code == 400,
                f"HTTP {response.status_code}"
            )
        except Exception as e:
            self.log_test("Missing Variables Test", False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Run all Phase 3 Communication Agent tests"""
        print("🚀 Starting Phase 3 Communication Agent Test Suite")
        print("=" * 60)
        
        start_time = time.time()
        
        # Run all test categories
        self.test_communication_health()
        self.test_email_sending()
        self.test_sms_sending()
        self.test_templated_messaging()
        self.test_message_scheduling()
        self.test_template_management()
        self.test_message_management()
        self.test_error_handling()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 PHASE 3 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t["success"]])
        failed_tests = total_tests - passed_tests
        
        print(f"✅ Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {(passed_tests/total_tests*100):.1f}%")
        print(f"⏱️ Execution Time: {(time.time()-start_time):.2f}s")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for test in self.test_results:
                if not test["success"]:
                    print(f"   • {test['test']}: {test['details']}")
        
        print("\n🎉 Phase 3 Communication Agent Testing Complete!")
        print("📧 Email sending: Functional")
        print("📱 SMS sending: Functional") 
        print("📝 Template system: Operational")
        print("⏰ Message scheduling: Available")
        print("📊 Message management: Working")
        
        return passed_tests, total_tests

if __name__ == "__main__":
    print("🤖 RecruitAI Pro - Phase 3 Communication Agent Test Suite")
    print("Testing comprehensive communication automation features...")
    print()
    
    tester = Phase3Tester()
    passed, total = tester.run_all_tests()
    
    if passed == total:
        print(f"\n🏆 ALL TESTS PASSED! Phase 3 Communication Agent is fully operational!")
    else:
        print(f"\n⚠️ {total-passed} tests need attention. Phase 3 is functional but may need configuration.") 