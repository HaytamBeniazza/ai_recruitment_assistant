"""
Comprehensive Test Suite for Phase 4: Dashboard & Analytics
Tests all dashboard functionality, KPIs, charts, and reporting features
"""

import asyncio
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
DASHBOARD_BASE = f"{BASE_URL}/dashboard"

class DashboardTester:
    """Test suite for Dashboard & Analytics functionality"""
    
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
        print(f"{status} | {test_name}")
        if details:
            print(f"    📋 {details}")
            
    def test_dashboard_health(self):
        """Test dashboard health endpoint"""
        try:
            response = self.session.get(f"{DASHBOARD_BASE}/health")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = f"Status: {data.get('status')}, Service: {data.get('service')}"
            else:
                details = f"HTTP {response.status_code}: {response.text}"
                
            self.log_test("Dashboard Health Check", success, details)
            return success
            
        except Exception as e:
            self.log_test("Dashboard Health Check", False, f"Exception: {str(e)}")
            return False
    
    def test_dashboard_agent_status(self):
        """Test dashboard agent status endpoint"""
        try:
            response = self.session.get(f"{DASHBOARD_BASE}/agent/status")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = f"Agent: {data.get('agent_name')}, Status: {data.get('status')}, KPIs: {data.get('kpis_defined')}"
            else:
                details = f"HTTP {response.status_code}: {response.text}"
                
            self.log_test("Dashboard Agent Status", success, details)
            return success
            
        except Exception as e:
            self.log_test("Dashboard Agent Status", False, f"Exception: {str(e)}")
            return False
    
    def test_get_dashboard_data(self):
        """Test main dashboard data endpoint"""
        try:
            # Test different time ranges
            time_ranges = ["24h", "7d", "30d"]
            
            for time_range in time_ranges:
                response = self.session.get(f"{DASHBOARD_BASE}/data?time_range={time_range}")
                success = response.status_code == 200
                
                if success:
                    data = response.json()
                    kpis_count = len(data.get("kpis", []))
                    charts_count = len(data.get("charts", {}))
                    details = f"Range: {time_range}, KPIs: {kpis_count}, Charts: {charts_count}"
                else:
                    details = f"HTTP {response.status_code}: {response.text}"
                    
                self.log_test(f"Dashboard Data ({time_range})", success, details)
                
                if not success:
                    return False
                    
            return True
            
        except Exception as e:
            self.log_test("Dashboard Data", False, f"Exception: {str(e)}")
            return False
    
    def test_kpis_endpoint(self):
        """Test KPIs calculation endpoint"""
        try:
            response = self.session.get(f"{DASHBOARD_BASE}/kpis?time_range=7d")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                kpis = data.get("kpis", [])
                total_kpis = data.get("total_kpis", 0)
                
                # Verify KPI structure
                if kpis:
                    sample_kpi = kpis[0]
                    required_fields = ["name", "value", "unit", "trend"]
                    has_required = all(field in sample_kpi for field in required_fields)
                    
                    details = f"Total KPIs: {total_kpis}, Structure valid: {has_required}"
                    if not has_required:
                        details += f", Missing: {[f for f in required_fields if f not in sample_kpi]}"
                else:
                    details = "No KPIs returned"
                    success = False
            else:
                details = f"HTTP {response.status_code}: {response.text}"
                
            self.log_test("KPIs Calculation", success, details)
            return success
            
        except Exception as e:
            self.log_test("KPIs Calculation", False, f"Exception: {str(e)}")
            return False
    
    def test_chart_data_endpoint(self):
        """Test chart data endpoint"""
        try:
            response = self.session.get(f"{DASHBOARD_BASE}/charts?time_range=7d")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                charts = data.get("charts", {})
                available_charts = data.get("available_charts", [])
                
                # Verify chart structure
                valid_charts = 0
                for chart_name, chart_data in charts.items():
                    if "chart_type" in chart_data and "data" in chart_data:
                        valid_charts += 1
                
                details = f"Available charts: {len(available_charts)}, Valid: {valid_charts}"
                if available_charts:
                    details += f", Types: {', '.join(available_charts[:3])}"
            else:
                details = f"HTTP {response.status_code}: {response.text}"
                
            self.log_test("Chart Data", success, details)
            return success
            
        except Exception as e:
            self.log_test("Chart Data", False, f"Exception: {str(e)}")
            return False
    
    def test_system_stats(self):
        """Test system statistics endpoint"""
        try:
            response = self.session.get(f"{DASHBOARD_BASE}/stats")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                stats = data.get("system_stats", {})
                
                # Check for required stats
                required_stats = [
                    "total_candidates", "total_interviews", 
                    "total_messages", "total_jobs"
                ]
                
                has_stats = all(stat in stats for stat in required_stats)
                details = f"Has required stats: {has_stats}"
                
                if has_stats:
                    details += f", Candidates: {stats.get('total_candidates')}"
                    details += f", Interviews: {stats.get('total_interviews')}"
                    details += f", Messages: {stats.get('total_messages')}"
                
                success = has_stats
            else:
                details = f"HTTP {response.status_code}: {response.text}"
                
            self.log_test("System Statistics", success, details)
            return success
            
        except Exception as e:
            self.log_test("System Statistics", False, f"Exception: {str(e)}")
            return False
    
    def test_agents_status(self):
        """Test all agents status endpoint"""
        try:
            response = self.session.get(f"{DASHBOARD_BASE}/agents/status")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                agents = data.get("agents", {})
                overall_health = data.get("overall_health")
                
                expected_agents = [
                    "Resume Analyzer", "Scheduler", 
                    "Communication", "Dashboard"
                ]
                
                found_agents = list(agents.keys())
                has_all_agents = all(agent in found_agents for agent in expected_agents)
                
                details = f"Overall health: {overall_health}, Agents: {len(found_agents)}"
                details += f", All expected: {has_all_agents}"
                
                success = has_all_agents and overall_health == "healthy"
            else:
                details = f"HTTP {response.status_code}: {response.text}"
                
            self.log_test("Agents Status", success, details)
            return success
            
        except Exception as e:
            self.log_test("Agents Status", False, f"Exception: {str(e)}")
            return False
    
    def test_specific_chart_types(self):
        """Test requesting specific chart types"""
        try:
            # Try to get specific chart types
            chart_types = ["candidates_timeline", "communication_volume"]
            
            for chart_type in chart_types:
                response = self.session.get(f"{DASHBOARD_BASE}/charts?chart_type={chart_type}")
                success = response.status_code == 200
                
                if success:
                    data = response.json()
                    charts = data.get("charts", {})
                    has_chart = chart_type in charts
                    details = f"Chart found: {has_chart}"
                    
                    if has_chart:
                        chart_data = charts[chart_type]
                        details += f", Type: {chart_data.get('chart_type')}"
                        details += f", Data points: {len(chart_data.get('data', []))}"
                else:
                    details = f"HTTP {response.status_code}: {response.text}"
                    
                self.log_test(f"Chart Type: {chart_type}", success, details)
                
                if not success:
                    return False
                    
            return True
            
        except Exception as e:
            self.log_test("Specific Chart Types", False, f"Exception: {str(e)}")
            return False
    
    def test_error_handling(self):
        """Test error handling with invalid requests"""
        try:
            # Test invalid time range
            response = self.session.get(f"{DASHBOARD_BASE}/data?time_range=invalid")
            
            # Should still work with invalid range (defaults to 24h)
            success = response.status_code == 200
            details = "Invalid time range handled gracefully"
            
            self.log_test("Error Handling", success, details)
            return success
            
        except Exception as e:
            self.log_test("Error Handling", False, f"Exception: {str(e)}")
            return False
    
    def test_main_app_integration(self):
        """Test integration with main application"""
        try:
            # Test main health endpoint
            response = self.session.get(f"{BASE_URL}/health")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                agents = data.get("agents", {})
                has_dashboard = "dashboard" in agents
                details = f"Dashboard in main health: {has_dashboard}"
                
                # Test main status endpoint
                response = self.session.get(f"{BASE_URL}/status")
                if response.status_code == 200:
                    status_data = response.json()
                    status_agents = status_data.get("agents", {})
                    has_dashboard_status = "dashboard" in status_agents
                    details += f", Dashboard in status: {has_dashboard_status}"
                    success = has_dashboard and has_dashboard_status
                else:
                    success = False
                    details += ", Status endpoint failed"
            else:
                details = f"HTTP {response.status_code}: {response.text}"
                
            self.log_test("Main App Integration", success, details)
            return success
            
        except Exception as e:
            self.log_test("Main App Integration", False, f"Exception: {str(e)}")
            return False
    
    def run_comprehensive_test(self):
        """Run all dashboard tests"""
        print("🧪 Starting Phase 4 Dashboard & Analytics Test Suite")
        print("=" * 60)
        
        # List of all tests to run
        tests = [
            self.test_dashboard_health,
            self.test_dashboard_agent_status,
            self.test_get_dashboard_data,
            self.test_kpis_endpoint,
            self.test_chart_data_endpoint,
            self.test_system_stats,
            self.test_agents_status,
            self.test_specific_chart_types,
            self.test_error_handling,
            self.test_main_app_integration
        ]
        
        # Run all tests
        passed = 0
        total = len(tests)
        
        for test in tests:
            if test():
                passed += 1
            print()  # Add spacing between tests
        
        # Print summary
        print("=" * 60)
        print(f"📊 PHASE 4 DASHBOARD TEST SUMMARY")
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("🎉 ALL PHASE 4 DASHBOARD TESTS PASSED!")
            print("🚀 Dashboard & Analytics system is fully operational!")
        else:
            print("⚠️  Some tests failed. Check the details above.")
            
        return passed == total

def main():
    """Main test execution"""
    print("🤖 RecruitAI Pro - Phase 4 Dashboard & Analytics Test")
    print("📈 Testing real-time analytics, KPIs, and reporting features")
    print()
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server is not responding correctly")
            print("💡 Please start the server with: python backend/main.py")
            return False
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to server")
        print("💡 Please start the server with: python backend/main.py")
        return False
    
    print("✅ Server is running, starting tests...")
    print()
    
    # Run comprehensive test suite
    tester = DashboardTester()
    return tester.run_comprehensive_test()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 