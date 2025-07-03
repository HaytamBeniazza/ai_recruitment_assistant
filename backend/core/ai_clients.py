"""
AI Client Configuration for RecruitAI Pro
Handles OpenAI and other AI service integrations
"""

import openai
from typing import Dict, List, Any, Optional
import asyncio

# Import settings
from .config import settings

class OpenAIClient:
    """OpenAI API client for resume analysis"""
    
    def __init__(self):
        if settings.openai_api_key:
            self.client = openai.OpenAI(api_key=settings.openai_api_key)
            self.available = True
            print("✅ OpenAI client initialized")
        else:
            self.available = False
            print("⚠️  OpenAI API key not configured")
    
    async def extract_skills_from_resume(self, resume_text: str) -> Dict[str, Any]:
        """Extract skills from resume text using GPT-4"""
        if not self.available:
            return {"error": "OpenAI client not available"}
        
        try:
            prompt = f"""
            Extract skills from this resume text:
            
            {resume_text}
            
            Return JSON with technical_skills, soft_skills, and experience_years.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            
            return {"skills": response.choices[0].message.content}
            
        except Exception as e:
            return {"error": str(e)}
    
    def check_connection(self) -> bool:
        """Test OpenAI API connection"""
        if not self.available:
            return False
            
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            print("✅ OpenAI connection successful")
            return True
        except Exception as e:
            print(f"❌ OpenAI connection failed: {e}")
            return False

# Create global AI client instance
openai_client = OpenAIClient()

print(f"🤖 AI Clients initialized")
print(f"   OpenAI: {'✅ Available' if openai_client.available else '❌ Unavailable'}") 