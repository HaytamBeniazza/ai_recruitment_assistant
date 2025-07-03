# 📚 **RecruitAI Pro - Complete API Documentation**

This document provides comprehensive documentation for all API endpoints in the RecruitAI Pro system.

## 🌐 **Base URL**
```
http://localhost:8000
```

## 🔧 **Authentication**
Currently, the API operates without authentication for development. In production, implement JWT-based authentication.

---

## 📊 **System Endpoints**

### **Health Check**
```http
GET /health
```

**Description**: Basic health check for the entire system

**Response Example**:
```json
{
  "status": "healthy",
  "service": "RecruitAI Pro",
  "version": "1.0.0",
  "agents": {
    "resume_analyzer": "ready",
    "scheduler": "ready",
    "communication": "ready",
    "dashboard": "ready"
  }
}
```

### **System Status**
```http
GET /status
```

**Description**: Detailed system status with performance metrics

**Response Example**:
```json
{
  "system": "RecruitAI Pro",
  "status": "operational",
  "uptime": "online",
  "agents": {
    "resume_analyzer": {
      "status": "active",
      "processed_today": 25,
      "avg_processing_time": "25 seconds",
      "accuracy": "87%"
    },
    "scheduler": {
      "status": "active",
      "interviews_scheduled": 12,
      "success_rate": "96%",
      "conflicts_resolved": 3
    },
    "communication": {
      "status": "active",
      "emails_sent": 45,
      "delivery_rate": "98%",
      "response_rate": "45%"
    },
    "dashboard": {
      "status": "active",
      "kpis_tracked": 8,
      "charts_available": 5,
      "data_freshness": "real-time"
    }
  }
}
```

---

## 👥 **Candidates API**

### **Create Candidate**
```http
POST /candidates
```

**Request Body**:
```json
{
  "name": "John Doe",
  "email": "john.doe@example.com",
  "phone": "+1234567890",
  "skills": ["Python", "FastAPI", "Machine Learning"],
  "experience_years": 5,
  "education": "Bachelor's in Computer Science",
  "location": "San Francisco, CA",
  "resume_text": "Experienced software engineer with 5 years..."
}
```

**Response**:
```json
{
  "success": true,
  "candidate_id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Candidate created successfully"
}
```

### **List Candidates**
```http
GET /candidates?limit=10&offset=0&skills=Python&min_score=70
```

**Query Parameters**:
- `limit` (int): Number of candidates to return (default: 10)
- `offset` (int): Number of candidates to skip (default: 0)
- `skills` (string): Filter by skills (comma-separated)
- `min_score` (float): Minimum resume score filter
- `location` (string): Filter by location

**Response**:
```json
{
  "candidates": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "John Doe",
      "email": "john.doe@example.com",
      "resume_score": 85.5,
      "skills": ["Python", "FastAPI", "Machine Learning"],
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

### **Get Candidate**
```http
GET /candidates/{candidate_id}
```

**Response**:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "John Doe",
  "email": "john.doe@example.com",
  "phone": "+1234567890",
  "skills": ["Python", "FastAPI", "Machine Learning"],
  "resume_score": 85.5,
  "analysis_results": {
    "technical_skills": 90,
    "experience_score": 80,
    "education_score": 85,
    "soft_skills": 75
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### **Update Candidate**
```http
PUT /candidates/{candidate_id}
```

**Request Body**: Same as Create Candidate

### **Delete Candidate**
```http
DELETE /candidates/{candidate_id}
```

### **Analyze Resume**
```http
POST /candidates/{candidate_id}/analyze
```

**Request Body**:
```json
{
  "job_requirements": "Python, FastAPI, 3+ years experience",
  "force_reanalysis": false
}
```

**Response**:
```json
{
  "success": true,
  "analysis_results": {
    "overall_score": 85.5,
    "technical_skills": 90,
    "experience_score": 80,
    "education_score": 85,
    "soft_skills": 75,
    "strengths": ["Strong Python skills", "FastAPI experience"],
    "weaknesses": ["Limited cloud experience"],
    "recommendations": ["Consider for senior developer role"]
  }
}
```

### **Upload Resume**
```http
POST /candidates/upload
```

**Request**: Multipart form data with file upload

**Response**:
```json
{
  "success": true,
  "file_id": "resume_123.pdf",
  "extracted_text": "John Doe\nSoftware Engineer...",
  "metadata": {
    "file_size": 245760,
    "pages": 2,
    "processing_time": 1.5
  }
}
```

---

## 💼 **Jobs API**

### **Create Job Position**
```http
POST /jobs
```

**Request Body**:
```json
{
  "title": "Senior Python Developer",
  "department": "Engineering",
  "location": "San Francisco, CA",
  "job_type": "full-time",
  "required_skills": ["Python", "FastAPI", "PostgreSQL"],
  "preferred_skills": ["AWS", "Docker", "Kubernetes"],
  "min_experience_years": 3,
  "max_experience_years": 8,
  "salary_range": {
    "min": 120000,
    "max": 180000,
    "currency": "USD"
  },
  "description": "We are looking for a senior Python developer...",
  "requirements": "Bachelor's degree in Computer Science or equivalent"
}
```

**Response**:
```json
{
  "success": true,
  "job_id": "456e7890-e89b-12d3-a456-426614174001",
  "message": "Job position created successfully"
}
```

### **List Jobs**
```http
GET /jobs?limit=10&offset=0&department=Engineering&status=active
```

### **Get Job Details**
```http
GET /jobs/{job_id}
```

### **Update Job**
```http
PUT /jobs/{job_id}
```

### **Get Ranked Candidates for Job**
```http
GET /jobs/{job_id}/candidates?limit=10&min_score=70
```

**Response**:
```json
{
  "job_id": "456e7890-e89b-12d3-a456-426614174001",
  "job_title": "Senior Python Developer",
  "ranked_candidates": [
    {
      "candidate_id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "John Doe",
      "match_score": 92.5,
      "skill_match": 95,
      "experience_match": 90,
      "ranking": 1
    }
  ],
  "total_candidates": 25,
  "matching_candidates": 12
}
```

---

## 📅 **Scheduler API**

### **Schedule Interview**
```http
POST /scheduler/schedule
```

**Request Body**:
```json
{
  "candidate_id": "123e4567-e89b-12d3-a456-426614174000",
  "job_position_id": "456e7890-e89b-12d3-a456-426614174001",
  "interviewer_email": "interviewer@company.com",
  "start_time": "2024-01-15T10:00:00Z",
  "duration_minutes": 60,
  "interview_type": "technical",
  "location": "Conference Room A",
  "notes": "Technical interview for Python developer position"
}
```

**Response**:
```json
{
  "success": true,
  "interview_id": "789e0123-e89b-12d3-a456-426614174002",
  "message": "Interview scheduled successfully",
  "details": {
    "candidate_name": "John Doe",
    "interviewer": "interviewer@company.com",
    "start_time": "2024-01-15T10:00:00Z",
    "end_time": "2024-01-15T11:00:00Z",
    "location": "Conference Room A"
  }
}
```

### **List Interviews**
```http
GET /scheduler/interviews?start_date=2024-01-15&end_date=2024-01-22&status=scheduled
```

### **Get Interview Details**
```http
GET /scheduler/interviews/{interview_id}
```

### **Reschedule Interview**
```http
PUT /scheduler/interviews/{interview_id}/reschedule
```

**Request Body**:
```json
{
  "new_start_time": "2024-01-16T14:00:00Z",
  "reason": "Interviewer conflict"
}
```

### **Find Available Slots**
```http
GET /scheduler/availability?interviewer_email=interviewer@company.com&date=2024-01-15&duration=60
```

**Response**:
```json
{
  "available_slots": [
    {
      "start_time": "2024-01-15T09:00:00Z",
      "end_time": "2024-01-15T10:00:00Z",
      "score": 95
    },
    {
      "start_time": "2024-01-15T14:00:00Z",
      "end_time": "2024-01-15T15:00:00Z",
      "score": 88
    }
  ],
  "total_slots": 2,
  "date": "2024-01-15"
}
```

### **Detect Conflicts**
```http
POST /scheduler/conflicts/detect
```

**Request Body**:
```json
{
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T11:00:00Z",
  "participants": ["interviewer@company.com", "john.doe@example.com"]
}
```

---

## 📧 **Communication API**

### **Send Email**
```http
POST /communication/send-email
```

**Request Body**:
```json
{
  "to_email": "john.doe@example.com",
  "subject": "Interview Confirmation",
  "body": "Dear John, your interview is scheduled for...",
  "html_body": "<h1>Interview Confirmation</h1><p>Dear John...</p>",
  "cc": ["hr@company.com"],
  "bcc": ["archive@company.com"],
  "priority": "normal"
}
```

**Response**:
```json
{
  "success": true,
  "message_id": "msg_123e4567-e89b-12d3-a456-426614174003",
  "status": "sent",
  "delivery_time": "2024-01-15T10:35:22Z"
}
```

### **Send SMS**
```http
POST /communication/send-sms
```

**Request Body**:
```json
{
  "phone_number": "+1234567890",
  "message": "Hi John, your interview is scheduled for tomorrow at 10 AM.",
  "priority": "normal"
}
```

### **Send Templated Message**
```http
POST /communication/send-templated
```

**Request Body**:
```json
{
  "template_name": "interview_scheduled",
  "recipient_email": "john.doe@example.com",
  "variables": {
    "candidate_name": "John Doe",
    "interview_date": "2024-01-15",
    "interview_time": "10:00 AM",
    "interviewer_name": "Sarah Johnson",
    "location": "Conference Room A"
  },
  "communication_type": "email",
  "enhance_with_ai": true
}
```

### **Schedule Message**
```http
POST /communication/schedule
```

**Request Body**:
```json
{
  "template_name": "interview_reminder",
  "recipient_email": "john.doe@example.com",
  "variables": {
    "candidate_name": "John Doe",
    "interview_date": "2024-01-15",
    "interview_time": "10:00 AM"
  },
  "scheduled_time": "2024-01-14T18:00:00Z",
  "communication_type": "email"
}
```

### **List Messages**
```http
GET /communication/messages?status=sent&limit=20&offset=0
```

### **Get Message Details**
```http
GET /communication/messages/{message_id}
```

### **Retry Failed Message**
```http
PUT /communication/messages/{message_id}/retry
```

### **List Templates**
```http
GET /communication/templates
```

**Response**:
```json
{
  "templates": [
    {
      "name": "interview_scheduled",
      "subject": "Interview Scheduled - {{job_title}}",
      "variables": ["candidate_name", "interview_date", "interview_time"],
      "communication_types": ["email", "sms"]
    }
  ]
}
```

### **Create Template**
```http
POST /communication/templates
```

---

## 📊 **Dashboard API**

### **Get Dashboard Data**
```http
GET /dashboard/data?time_range=7d
```

**Query Parameters**:
- `time_range`: 24h, 7d, 30d (default: 24h)

**Response**:
```json
{
  "kpis": [
    {
      "name": "Total Candidates",
      "value": 150,
      "unit": "count",
      "target_value": 200,
      "trend": "improving",
      "change_percentage": 12.5
    }
  ],
  "charts": {
    "candidates_timeline": {
      "chart_type": "line",
      "title": "Candidates Added Over Time",
      "data": [
        {"date": "2024-01-15", "count": 5},
        {"date": "2024-01-16", "count": 8}
      ]
    }
  },
  "recent_activity": [],
  "agent_status": {
    "Resume Analyzer": {"status": "healthy", "health_score": 95},
    "Scheduler": {"status": "healthy", "health_score": 92}
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### **Get KPIs**
```http
GET /dashboard/kpis?time_range=7d
```

### **Get Charts**
```http
GET /dashboard/charts?time_range=7d&chart_type=candidates_timeline
```

### **Get System Statistics**
```http
GET /dashboard/stats
```

**Response**:
```json
{
  "system_stats": {
    "total_candidates": 150,
    "total_interviews": 45,
    "total_messages": 230,
    "total_jobs": 12,
    "candidates_this_week": 25,
    "interviews_this_week": 12,
    "messages_this_week": 67
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### **Get Agent Status**
```http
GET /dashboard/agents/status
```

---

## 🚨 **Error Handling**

### **Standard Error Response**
```json
{
  "error": "ValidationError",
  "message": "Invalid request parameters",
  "detail": "Field 'email' is required",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### **HTTP Status Codes**
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

---

## 📝 **Rate Limiting**

Currently no rate limiting is implemented. In production, implement:
- 100 requests per minute per IP for general endpoints
- 10 requests per minute for AI-heavy operations (resume analysis)
- 1000 requests per hour for dashboard endpoints

---

## 🔒 **Security Considerations**

For production deployment:
1. Implement JWT authentication
2. Add API key validation
3. Use HTTPS only
4. Implement request validation
5. Add CORS configuration
6. Sanitize file uploads
7. Add rate limiting

---

## 🧪 **Testing the API**

### **Using cURL**
```bash
# Health check
curl -X GET http://localhost:8000/health

# Create candidate
curl -X POST http://localhost:8000/candidates \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com"}'

# Get dashboard data
curl -X GET http://localhost:8000/dashboard/data?time_range=7d
```

### **Using Python requests**
```python
import requests

# Health check
response = requests.get("http://localhost:8000/health")
print(response.json())

# Create candidate
candidate_data = {
    "name": "John Doe",
    "email": "john@example.com",
    "skills": ["Python", "FastAPI"]
}
response = requests.post("http://localhost:8000/candidates", json=candidate_data)
print(response.json())
```

---

## 📚 **Additional Resources**

- **Interactive API Docs**: http://localhost:8000/docs
- **OpenAPI Specification**: http://localhost:8000/openapi.json
- **System Health**: http://localhost:8000/health
- **System Status**: http://localhost:8000/status 