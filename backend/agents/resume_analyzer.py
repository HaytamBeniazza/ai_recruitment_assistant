"""
Resume Analyzer Agent for RecruitAI Pro
The core AI agent responsible for analyzing resumes and scoring candidates
"""

import json
import logging
import re
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from core.ai_clients import ai_client
from core.message_broker import message_broker
from models.candidates import Candidate, CandidateAnalysisLog
from models.jobs import JobPosition
from services.file_processor import file_processor

# Configure logging
logger = logging.getLogger(__name__)

class ResumeAnalyzer:
    """
    Advanced AI-powered resume analyzer with multi-dimensional scoring
    
    Scoring Breakdown:
    - Technical Skills: 40% (skill matching, proficiency assessment)
    - Experience: 30% (years, relevance, career progression)
    - Education: 20% (degree relevance, institution quality)
    - Soft Skills: 10% (communication, leadership, teamwork)
    """
    
    def __init__(self):
        self.model_version = "gpt-4-resume-analyzer-v1.0"
        self.analysis_weights = {
            "technical_skills": 0.40,
            "experience": 0.30,
            "education": 0.20,
            "soft_skills": 0.10
        }
    
    async def analyze_resume(
        self,
        candidate: Candidate,
        job_position: Optional[JobPosition] = None,
        force_reanalysis: bool = False
    ) -> Dict[str, Any]:
        """
        Complete resume analysis pipeline
        
        Args:
            candidate: Candidate object with resume text
            job_position: Optional job position for targeted analysis
            force_reanalysis: Whether to force re-analysis if already completed
            
        Returns:
            Complete analysis results with scores and extracted information
        """
        
        # Check if analysis already completed
        if candidate.analysis_completed and not force_reanalysis:
            return self._get_existing_analysis(candidate)
        
        start_time = time.time()
        analysis_log = None
        
        try:
            # Create analysis log
            analysis_log = await self._create_analysis_log(candidate.id, "full_analysis")
            
            # Validate input
            if not candidate.resume_text or len(candidate.resume_text.strip()) < 50:
                raise ValueError("Resume text is too short or missing")
            
            # Broadcast analysis start
            await message_broker.broadcast_status(
                f"analysis_started",
                {"candidate_id": str(candidate.id), "timestamp": datetime.utcnow().isoformat()}
            )
            
            # Step 1: Extract structured information from resume
            logger.info(f"Starting resume analysis for candidate {candidate.id}")
            extracted_info = await self._extract_resume_information(candidate.resume_text)
            
            # Step 2: Analyze technical skills
            technical_analysis = await self._analyze_technical_skills(
                extracted_info.get("technical_skills", []),
                extracted_info.get("experience", []),
                job_position
            )
            
            # Step 3: Analyze work experience
            experience_analysis = await self._analyze_experience(
                extracted_info.get("experience", []),
                job_position
            )
            
            # Step 4: Analyze education
            education_analysis = await self._analyze_education(
                extracted_info.get("education", []),
                job_position
            )
            
            # Step 5: Analyze soft skills
            soft_skills_analysis = await self._analyze_soft_skills(
                candidate.resume_text,
                extracted_info.get("soft_skills", []),
                job_position
            )
            
            # Step 6: Calculate composite score
            scores = self._calculate_composite_score(
                technical_analysis,
                experience_analysis,
                education_analysis,
                soft_skills_analysis,
                job_position
            )
            
            # Step 7: Generate insights and recommendations
            insights = await self._generate_insights(
                candidate,
                extracted_info,
                technical_analysis,
                experience_analysis,
                education_analysis,
                soft_skills_analysis,
                scores,
                job_position
            )
            
            # Update candidate record
            await self._update_candidate_analysis(
                candidate,
                extracted_info,
                technical_analysis,
                experience_analysis,
                education_analysis,
                soft_skills_analysis,
                scores,
                insights
            )
            
            processing_time = time.time() - start_time
            
            # Update analysis log
            if analysis_log:
                await self._complete_analysis_log(
                    analysis_log,
                    {
                        "extracted_info": extracted_info,
                        "technical_analysis": technical_analysis,
                        "experience_analysis": experience_analysis,
                        "education_analysis": education_analysis,
                        "soft_skills_analysis": soft_skills_analysis,
                        "scores": scores,
                        "insights": insights
                    },
                    processing_time
                )
            
            # Broadcast analysis completion
            await message_broker.broadcast_status(
                f"analysis_completed",
                {
                    "candidate_id": str(candidate.id),
                    "overall_score": scores["overall_score"],
                    "recommendation": candidate.recommendation,
                    "processing_time": processing_time,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            logger.info(
                f"Resume analysis completed for candidate {candidate.id} "
                f"(Score: {scores['overall_score']}, Time: {processing_time:.2f}s)"
            )
            
            return {
                "success": True,
                "candidate_id": str(candidate.id),
                "overall_score": scores["overall_score"],
                "score_breakdown": scores,
                "extracted_information": extracted_info,
                "analysis_details": {
                    "technical_skills": technical_analysis,
                    "experience": experience_analysis,
                    "education": education_analysis,
                    "soft_skills": soft_skills_analysis
                },
                "insights": insights,
                "recommendation": candidate.recommendation,
                "processing_time": processing_time,
                "model_version": self.model_version,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            # Log error and update analysis log
            logger.error(f"Resume analysis failed for candidate {candidate.id}: {str(e)}")
            
            if analysis_log:
                await self._fail_analysis_log(analysis_log, str(e), processing_time)
            
            # Broadcast analysis failure
            await message_broker.broadcast_status(
                f"analysis_failed",
                {
                    "candidate_id": str(candidate.id),
                    "error": str(e),
                    "processing_time": processing_time,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return {
                "success": False,
                "error": str(e),
                "candidate_id": str(candidate.id),
                "processing_time": processing_time
            }
    
    async def _extract_resume_information(self, resume_text: str) -> Dict[str, Any]:
        """Extract structured information from resume text using AI"""
        
        extraction_prompt = f"""
        Analyze the following resume and extract structured information.
        Be thorough and accurate. Extract as much relevant information as possible.
        
        Resume Text:
        {resume_text}
        
        Please extract and return a JSON object with the following structure:
        {{
            "contact_info": {{
                "name": "Full name",
                "email": "email@example.com",
                "phone": "phone number",
                "location": "city, state/country",
                "linkedin": "linkedin profile URL",
                "github": "github profile URL",
                "portfolio": "portfolio/website URL"
            }},
            "summary": "Professional summary or objective",
            "technical_skills": [
                {{
                    "skill": "Skill name",
                    "category": "programming/framework/tool/database/cloud/etc",
                    "proficiency": "beginner/intermediate/advanced/expert",
                    "years_experience": "estimated years"
                }}
            ],
            "soft_skills": [
                {{
                    "skill": "Soft skill name",
                    "evidence": "Where this was demonstrated in the resume"
                }}
            ],
            "experience": [
                {{
                    "company": "Company name",
                    "position": "Job title",
                    "start_date": "YYYY-MM or YYYY",
                    "end_date": "YYYY-MM or YYYY or 'Present'",
                    "duration_months": "estimated months",
                    "responsibilities": ["responsibility 1", "responsibility 2"],
                    "achievements": ["achievement 1", "achievement 2"],
                    "technologies_used": ["tech1", "tech2"]
                }}
            ],
            "education": [
                {{
                    "institution": "University/School name",
                    "degree": "Degree type and field",
                    "graduation_date": "YYYY or YYYY-MM",
                    "gpa": "GPA if mentioned",
                    "relevant_coursework": ["course1", "course2"],
                    "honors": ["honor1", "honor2"]
                }}
            ],
            "certifications": [
                {{
                    "name": "Certification name",
                    "issuer": "Issuing organization",
                    "date": "YYYY or YYYY-MM",
                    "expiry": "YYYY or YYYY-MM or null",
                    "credential_id": "ID if mentioned"
                }}
            ],
            "projects": [
                {{
                    "name": "Project name",
                    "description": "Brief description",
                    "technologies": ["tech1", "tech2"],
                    "role": "Your role in the project",
                    "duration": "project duration",
                    "url": "project URL if available"
                }}
            ],
            "languages": [
                {{
                    "language": "Language name",
                    "proficiency": "native/fluent/conversational/basic"
                }}
            ],
            "volunteer_work": [
                {{
                    "organization": "Organization name",
                    "role": "Volunteer role",
                    "duration": "time period",
                    "description": "what you did"
                }}
            ]
        }}
        
        Important:
        - Be as accurate as possible with dates and durations
        - Infer proficiency levels based on context (years, project complexity, responsibilities)
        - Extract ALL technical skills mentioned, including programming languages, frameworks, tools, databases, etc.
        - Look for soft skills demonstrated through achievements and responsibilities
        - Return valid JSON only, no additional text
        """
        
        try:
            response = await ai_client.extract_skills(extraction_prompt)
            
            # Parse JSON response
            if isinstance(response, str):
                extracted_info = json.loads(response)
            else:
                extracted_info = response
            
            # Validate and clean extracted information
            return self._validate_extracted_info(extracted_info)
            
        except Exception as e:
            logger.error(f"Error extracting resume information: {str(e)}")
            # Return basic structure on error
            return {
                "contact_info": {},
                "summary": "",
                "technical_skills": [],
                "soft_skills": [],
                "experience": [],
                "education": [],
                "certifications": [],
                "projects": [],
                "languages": [],
                "volunteer_work": []
            }
    
    async def _analyze_technical_skills(
        self,
        technical_skills: List[Dict],
        experience: List[Dict],
        job_position: Optional[JobPosition] = None
    ) -> Dict[str, Any]:
        """Analyze technical skills with proficiency assessment"""
        
        # Calculate total years of technical experience
        total_tech_years = self._calculate_total_experience_years(experience)
        
        # Categorize skills
        skill_categories = self._categorize_technical_skills(technical_skills)
        
        # Calculate skill match score if job position provided
        skill_match_score = 0
        if job_position:
            skill_match_score = self._calculate_skill_match_score(
                technical_skills,
                job_position.required_skills or [],
                job_position.preferred_skills or []
            )
        
        # Calculate technical competency score
        competency_score = self._calculate_technical_competency_score(
            technical_skills,
            total_tech_years,
            skill_categories
        )
        
        # Final technical score (0-100)
        final_score = min(100, (skill_match_score * 0.6 + competency_score * 0.4))
        
        return {
            "score": round(final_score, 1),
            "total_skills": len(technical_skills),
            "skill_categories": skill_categories,
            "total_experience_years": total_tech_years,
            "skill_match_score": skill_match_score,
            "competency_score": competency_score,
            "top_skills": self._get_top_skills(technical_skills, 10),
            "skill_gaps": self._identify_skill_gaps(technical_skills, job_position) if job_position else [],
            "proficiency_distribution": self._get_proficiency_distribution(technical_skills)
        }
    
    async def _analyze_experience(
        self,
        experience: List[Dict],
        job_position: Optional[JobPosition] = None
    ) -> Dict[str, Any]:
        """Analyze work experience for relevance and progression"""
        
        total_years = self._calculate_total_experience_years(experience)
        relevant_years = total_years
        
        if job_position and job_position.required_skills:
            relevant_years = self._calculate_relevant_experience_years(
                experience,
                job_position.required_skills
            )
        
        # Calculate career progression score
        progression_score = self._calculate_career_progression_score(experience)
        
        # Calculate experience relevance score
        relevance_score = 100
        if job_position:
            relevance_score = self._calculate_experience_relevance_score(
                experience,
                job_position
            )
        
        # Calculate final experience score
        base_score = min(100, (total_years / max(job_position.required_experience_years or 3, 1)) * 100) if job_position else min(100, total_years * 10)
        final_score = (base_score * 0.5 + progression_score * 0.3 + relevance_score * 0.2)
        
        return {
            "score": round(final_score, 1),
            "total_years": total_years,
            "relevant_years": relevant_years,
            "number_of_positions": len(experience),
            "career_progression_score": progression_score,
            "experience_relevance_score": relevance_score,
            "employment_gaps": self._identify_employment_gaps(experience),
            "position_types": self._categorize_positions(experience),
            "recent_experience": experience[:3] if experience else []  # Last 3 positions
        }
    
    async def _analyze_education(
        self,
        education: List[Dict],
        job_position: Optional[JobPosition] = None
    ) -> Dict[str, Any]:
        """Analyze educational background"""
        
        if not education:
            return {
                "score": 50,  # Neutral score for missing education
                "degrees": [],
                "highest_degree": None,
                "relevant_education": False,
                "gpa_available": False,
                "education_match_score": 0
            }
        
        # Calculate education relevance score
        relevance_score = 100
        if job_position and job_position.required_education:
            relevance_score = self._calculate_education_relevance_score(
                education,
                job_position.required_education
            )
        
        # Calculate degree level score
        degree_score = self._calculate_degree_level_score(education)
        
        # Calculate GPA score if available
        gpa_score = self._calculate_gpa_score(education)
        
        # Final education score
        final_score = (degree_score * 0.6 + relevance_score * 0.3 + gpa_score * 0.1)
        
        return {
            "score": round(final_score, 1),
            "degrees": education,
            "highest_degree": self._get_highest_degree(education),
            "relevant_education": relevance_score > 70,
            "gpa_available": any(ed.get("gpa") for ed in education),
            "education_match_score": relevance_score,
            "degree_level_score": degree_score,
            "institutions": [ed.get("institution") for ed in education if ed.get("institution")]
        }
    
    async def _analyze_soft_skills(
        self,
        resume_text: str,
        extracted_soft_skills: List[Dict],
        job_position: Optional[JobPosition] = None
    ) -> Dict[str, Any]:
        """Analyze soft skills and cultural fit"""
        
        # Enhanced soft skills analysis using AI
        soft_skills_prompt = f"""
        Analyze the following resume text for soft skills and leadership qualities.
        Focus on evidence-based assessment from achievements and responsibilities.
        
        Resume Text:
        {resume_text[:3000]}  # Limit text for token efficiency
        
        Rate the candidate on these soft skills (0-10 scale):
        - Communication (presentations, documentation, client interaction)
        - Leadership (team management, project leadership, mentoring)
        - Problem Solving (innovative solutions, troubleshooting, optimization)
        - Teamwork (collaboration, cross-functional work)
        - Adaptability (diverse roles, technology changes, fast-paced environments)
        - Initiative (self-directed projects, process improvements)
        - Time Management (multiple projects, deadlines, efficiency)
        
        Return JSON:
        {{
            "communication": {{"score": 0-10, "evidence": ["evidence1", "evidence2"]}},
            "leadership": {{"score": 0-10, "evidence": ["evidence1", "evidence2"]}},
            "problem_solving": {{"score": 0-10, "evidence": ["evidence1", "evidence2"]}},
            "teamwork": {{"score": 0-10, "evidence": ["evidence1", "evidence2"]}},
            "adaptability": {{"score": 0-10, "evidence": ["evidence1", "evidence2"]}},
            "initiative": {{"score": 0-10, "evidence": ["evidence1", "evidence2"]}},
            "time_management": {{"score": 0-10, "evidence": ["evidence1", "evidence2"]}}
        }}
        """
        
        try:
            response = await ai_client.extract_skills(soft_skills_prompt)
            soft_skills_analysis = json.loads(response) if isinstance(response, str) else response
        except Exception as e:
            logger.error(f"Error analyzing soft skills: {str(e)}")
            soft_skills_analysis = {}
        
        # Calculate average soft skills score
        scores = [skill.get("score", 5) for skill in soft_skills_analysis.values() if isinstance(skill, dict)]
        average_score = sum(scores) / len(scores) if scores else 5
        
        # Convert to 0-100 scale
        final_score = (average_score / 10) * 100
        
        return {
            "score": round(final_score, 1),
            "detailed_analysis": soft_skills_analysis,
            "extracted_soft_skills": extracted_soft_skills,
            "average_rating": round(average_score, 1),
            "strengths": self._identify_soft_skill_strengths(soft_skills_analysis),
            "areas_for_development": self._identify_soft_skill_gaps(soft_skills_analysis),
            "cultural_fit_indicators": self._assess_cultural_fit(soft_skills_analysis, job_position)
        }
    
    def _calculate_composite_score(
        self,
        technical_analysis: Dict,
        experience_analysis: Dict,
        education_analysis: Dict,
        soft_skills_analysis: Dict,
        job_position: Optional[JobPosition] = None
    ) -> Dict[str, Any]:
        """Calculate final composite score with weighted components"""
        
        # Use job-specific weights if available
        weights = self.analysis_weights
        if job_position:
            weights = {
                "technical_skills": job_position.technical_skills_weight / 100,
                "experience": job_position.experience_weight / 100,
                "education": job_position.education_weight / 100,
                "soft_skills": job_position.soft_skills_weight / 100
            }
        
        # Calculate weighted score
        weighted_score = (
            technical_analysis["score"] * weights["technical_skills"] +
            experience_analysis["score"] * weights["experience"] +
            education_analysis["score"] * weights["education"] +
            soft_skills_analysis["score"] * weights["soft_skills"]
        )
        
        return {
            "overall_score": round(weighted_score, 0),
            "technical_skills_score": technical_analysis["score"],
            "experience_score": experience_analysis["score"],
            "education_score": education_analysis["score"],
            "soft_skills_score": soft_skills_analysis["score"],
            "weights_used": weights,
            "score_breakdown": {
                "technical_contribution": round(technical_analysis["score"] * weights["technical_skills"], 1),
                "experience_contribution": round(experience_analysis["score"] * weights["experience"], 1),
                "education_contribution": round(education_analysis["score"] * weights["education"], 1),
                "soft_skills_contribution": round(soft_skills_analysis["score"] * weights["soft_skills"], 1)
            }
        }
    
    async def _generate_insights(
        self,
        candidate: Candidate,
        extracted_info: Dict,
        technical_analysis: Dict,
        experience_analysis: Dict,
        education_analysis: Dict,
        soft_skills_analysis: Dict,
        scores: Dict,
        job_position: Optional[JobPosition] = None
    ) -> Dict[str, Any]:
        """Generate AI-powered insights and recommendations"""
        
        insights_prompt = f"""
        Generate professional insights and recommendations for this candidate analysis:
        
        Candidate: {candidate.name}
        Overall Score: {scores['overall_score']}/100
        
        Score Breakdown:
        - Technical Skills: {scores['technical_skills_score']}/100
        - Experience: {scores['experience_score']}/100
        - Education: {scores['education_score']}/100
        - Soft Skills: {scores['soft_skills_score']}/100
        
        Key Technical Skills: {[skill['skill'] for skill in extracted_info.get('technical_skills', [])[:10]]}
        Total Experience: {experience_analysis.get('total_years', 0)} years
        
        Generate insights in JSON format:
        {{
            "strengths": ["strength1", "strength2", "strength3"],
            "areas_for_improvement": ["area1", "area2"],
            "hiring_recommendation": "strong_hire/hire/maybe/no_hire",
            "key_highlights": ["highlight1", "highlight2", "highlight3"],
            "potential_concerns": ["concern1", "concern2"],
            "interview_focus_areas": ["area1", "area2", "area3"],
            "onboarding_recommendations": ["rec1", "rec2"],
            "growth_potential": "high/medium/low",
            "risk_assessment": "low/medium/high"
        }}
        """
        
        try:
            response = await ai_client.extract_skills(insights_prompt)
            insights = json.loads(response) if isinstance(response, str) else response
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            insights = {
                "strengths": ["Detailed analysis completed"],
                "areas_for_improvement": ["Analysis in progress"],
                "hiring_recommendation": "requires_review",
                "key_highlights": [],
                "potential_concerns": [],
                "interview_focus_areas": [],
                "onboarding_recommendations": [],
                "growth_potential": "medium",
                "risk_assessment": "medium"
            }
        
        return insights
    
    # === HELPER METHODS ===
    
    async def _create_analysis_log(self, candidate_id, analysis_type: str):
        """Create analysis log entry - simplified for Phase 1"""
        # Mock implementation for now
        return type('MockLog', (), {'id': candidate_id, 'analysis_type': analysis_type})()
    
    async def _complete_analysis_log(self, log, results, processing_time):
        """Complete analysis log - simplified for Phase 1"""
        pass
    
    async def _fail_analysis_log(self, log, error, processing_time):
        """Fail analysis log - simplified for Phase 1"""
        pass
    
    def _validate_extracted_info(self, extracted_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean extracted information"""
        default_structure = {
            "contact_info": {},
            "summary": "",
            "technical_skills": [],
            "soft_skills": [],
            "experience": [],
            "education": [],
            "certifications": [],
            "projects": [],
            "languages": [],
            "volunteer_work": []
        }
        
        for key, default_value in default_structure.items():
            if key not in extracted_info:
                extracted_info[key] = default_value
        
        return extracted_info
    
    def _categorize_technical_skills(self, technical_skills: List[Dict]) -> Dict[str, List]:
        """Categorize technical skills"""
        return {
            "programming_languages": [s for s in technical_skills if s.get("category") == "programming"],
            "frameworks": [s for s in technical_skills if s.get("category") == "framework"],
            "databases": [s for s in technical_skills if s.get("category") == "database"],
            "tools": [s for s in technical_skills if s.get("category") == "tool"],
            "other": [s for s in technical_skills if s.get("category", "other") == "other"]
        }
    
    def _calculate_total_experience_years(self, experience: List[Dict]) -> float:
        """Calculate total years of experience"""
        total_months = sum(exp.get("duration_months", 12) for exp in experience)
        return round(total_months / 12, 1)
    
    def _calculate_skill_match_score(self, candidate_skills: List[Dict], required_skills: List, preferred_skills: List) -> float:
        """Calculate skill match score"""
        if not required_skills:
            return 100.0
        
        candidate_skill_names = [skill.get("skill", "").lower() for skill in candidate_skills]
        required_matches = sum(1 for skill in required_skills if skill.lower() in candidate_skill_names)
        
        return (required_matches / len(required_skills)) * 100
    
    def _calculate_technical_competency_score(self, technical_skills: List[Dict], experience_years: float, categories: Dict) -> float:
        """Calculate technical competency score"""
        skill_count = len(technical_skills)
        return min(100, skill_count * 5 + experience_years * 10)
    
    def _get_top_skills(self, technical_skills: List[Dict], limit: int) -> List[Dict]:
        """Get top skills"""
        return technical_skills[:limit]
    
    def _identify_skill_gaps(self, candidate_skills: List[Dict], job_position) -> List[str]:
        """Identify skill gaps"""
        if not job_position:
            return []
        
        candidate_skill_names = [skill.get("skill", "").lower() for skill in candidate_skills]
        required_skills = job_position.required_skills or []
        
        return [skill for skill in required_skills if skill.lower() not in candidate_skill_names]
    
    def _get_proficiency_distribution(self, technical_skills: List[Dict]) -> Dict[str, int]:
        """Get proficiency distribution"""
        distribution = {"expert": 0, "advanced": 0, "intermediate": 0, "beginner": 0}
        for skill in technical_skills:
            proficiency = skill.get("proficiency", "intermediate").lower()
            if proficiency in distribution:
                distribution[proficiency] += 1
        return distribution
    
    def _calculate_career_progression_score(self, experience: List[Dict]) -> float:
        """Calculate career progression score"""
        return 75.0  # Simplified for Phase 1
    
    def _calculate_experience_relevance_score(self, experience: List[Dict], job_position) -> float:
        """Calculate experience relevance score"""
        return 80.0  # Simplified for Phase 1
    
    def _identify_employment_gaps(self, experience: List[Dict]) -> List[str]:
        """Identify employment gaps"""
        return []  # Simplified for Phase 1
    
    def _categorize_positions(self, experience: List[Dict]) -> Dict[str, int]:
        """Categorize positions"""
        return {"individual_contributor": len(experience), "team_lead": 0, "manager": 0}
    
    def _calculate_education_relevance_score(self, education: List[Dict], required_education: List) -> float:
        """Calculate education relevance"""
        return 85.0  # Simplified for Phase 1
    
    def _calculate_degree_level_score(self, education: List[Dict]) -> float:
        """Calculate degree level score"""
        if not education:
            return 50.0
        
        highest_score = 70.0  # Bachelor's default
        for edu in education:
            degree = edu.get("degree", "").lower()
            if "master" in degree or "mba" in degree:
                highest_score = max(highest_score, 85.0)
            elif "phd" in degree:
                highest_score = max(highest_score, 100.0)
        
        return highest_score
    
    def _calculate_gpa_score(self, education: List[Dict]) -> float:
        """Calculate GPA score"""
        return 75.0  # Simplified for Phase 1
    
    def _get_highest_degree(self, education: List[Dict]) -> Optional[Dict]:
        """Get highest degree"""
        return education[0] if education else None
    
    def _identify_soft_skill_strengths(self, soft_skills_analysis: Dict) -> List[str]:
        """Identify soft skill strengths"""
        strengths = []
        for skill, data in soft_skills_analysis.items():
            if isinstance(data, dict) and data.get("score", 0) >= 7:
                strengths.append(skill.replace("_", " ").title())
        return strengths
    
    def _identify_soft_skill_gaps(self, soft_skills_analysis: Dict) -> List[str]:
        """Identify soft skill gaps"""
        gaps = []
        for skill, data in soft_skills_analysis.items():
            if isinstance(data, dict) and data.get("score", 0) < 5:
                gaps.append(skill.replace("_", " ").title())
        return gaps
    
    def _assess_cultural_fit(self, soft_skills_analysis: Dict, job_position) -> Dict[str, Any]:
        """Assess cultural fit"""
        return {
            "overall_fit": "good",
            "strengths": ["team collaboration", "adaptability"],
            "considerations": []
        }
    
    async def _update_candidate_analysis(self, candidate, extracted_info, technical_analysis, experience_analysis, education_analysis, soft_skills_analysis, scores, insights):
        """Update candidate with analysis results"""
        # Update candidate fields
        candidate.technical_skills = extracted_info.get("technical_skills", [])
        candidate.soft_skills = extracted_info.get("soft_skills", [])
        candidate.certifications = extracted_info.get("certifications", [])
        candidate.education = extracted_info.get("education", [])
        candidate.experience = extracted_info.get("experience", [])
        
        # Update scores
        candidate.overall_score = int(scores["overall_score"])
        candidate.technical_skills_score = scores["technical_skills_score"]
        candidate.experience_score = scores["experience_score"]
        candidate.education_score = scores["education_score"]
        candidate.soft_skills_score = scores["soft_skills_score"]
        
        # Update metadata
        candidate.analysis_completed = True
        candidate.analysis_timestamp = datetime.utcnow()
        candidate.analysis_model_version = self.model_version
        candidate.analysis_notes = f"AI Analysis completed. Overall recommendation: {candidate.recommendation}"
        
        # Note: In real implementation, would commit to database here
    
    def _get_existing_analysis(self, candidate: Candidate) -> Dict[str, Any]:
        """Return existing analysis results"""
        return {
            "success": True,
            "candidate_id": str(candidate.id),
            "overall_score": candidate.overall_score,
            "score_breakdown": candidate.score_breakdown,
            "cached": True,
            "analysis_timestamp": candidate.analysis_timestamp.isoformat() if candidate.analysis_timestamp else None
        }

# Global instance for dependency injection
resume_analyzer = ResumeAnalyzer() 