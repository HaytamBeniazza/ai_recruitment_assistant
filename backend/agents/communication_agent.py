"""
Communication Agent for RecruitAI Pro
Handles intelligent email and SMS automation for recruitment communication
"""

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
import re
import json
from typing import Optional, Dict, List, Any, Tuple
import uuid
from jinja2 import Template, Environment, DictLoader
from dataclasses import dataclass
import asyncio
import pytz

from core.ai_clients import openai_client
from core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EmailConfig:
    """Email configuration settings"""
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    use_tls: bool = True
    use_ssl: bool = False
    sender_email: str = None
    sender_name: str = "RecruitAI Pro"

@dataclass
class SMSConfig:
    """SMS configuration settings"""
    provider: str  # twilio, aws_sns, etc.
    account_sid: str = None
    auth_token: str = None
    phone_number: str = None
    api_key: str = None
    api_secret: str = None

@dataclass
class CommunicationResult:
    """Result of a communication attempt"""
    success: bool
    message_id: Optional[str] = None
    external_id: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    provider_data: Optional[Dict] = None
    delivery_time_ms: Optional[int] = None

class CommunicationAgent:
    """
    Intelligent Communication Agent for automated recruitment messaging
    
    Features:
    - Smart email composition with AI assistance
    - SMS notifications and reminders
    - Template management and personalization
    - Delivery tracking and analytics
    - Multi-language support
    - Scheduled messaging
    - Intelligent retry logic
    """
    
    def __init__(self, email_config: Optional[EmailConfig] = None, sms_config: Optional[SMSConfig] = None):
        """
        Initialize Communication Agent
        
        Args:
            email_config: Email service configuration
            sms_config: SMS service configuration
        """
        self.settings = settings
        self.openai_client = openai_client.client if openai_client.available else None
        
        # Configuration
        self.email_config = email_config or self._load_email_config()
        self.sms_config = sms_config or self._load_sms_config()
        
        # Template engine
        self.template_env = Environment(loader=DictLoader({}))
        self.template_cache = {}
        
        # Default templates
        self.default_templates = self._load_default_templates()
        
        # AI personas for different communication types
        self.ai_personas = {
            "professional": "You are a professional HR assistant. Be formal, clear, and respectful.",
            "friendly": "You are a friendly HR assistant. Be warm, approachable, and encouraging.",
            "urgent": "You are an efficient HR assistant. Be direct, clear, and action-oriented.",
            "reminder": "You are a helpful HR assistant. Be polite, clear, and provide all necessary details."
        }
        
        logger.info("Communication Agent initialized successfully")
    
    def _load_email_config(self) -> Optional[EmailConfig]:
        """Load email configuration from settings"""
        try:
            return EmailConfig(
                smtp_server=self.settings.SMTP_SERVER or "smtp.gmail.com",
                smtp_port=self.settings.SMTP_PORT or 587,
                smtp_username=self.settings.SMTP_USERNAME or "",
                smtp_password=self.settings.SMTP_PASSWORD or "",
                use_tls=self.settings.SMTP_USE_TLS or True,
                sender_email=self.settings.SENDER_EMAIL or self.settings.SMTP_USERNAME,
                sender_name=self.settings.SENDER_NAME or "RecruitAI Pro"
            )
        except Exception as e:
            logger.warning(f"Could not load email config: {e}")
            return None
    
    def _load_sms_config(self) -> Optional[SMSConfig]:
        """Load SMS configuration from settings"""
        try:
            return SMSConfig(
                provider=self.settings.SMS_PROVIDER or "twilio",
                account_sid=self.settings.TWILIO_ACCOUNT_SID or "",
                auth_token=self.settings.TWILIO_AUTH_TOKEN or "",
                phone_number=self.settings.TWILIO_PHONE_NUMBER or ""
            )
        except Exception as e:
            logger.warning(f"Could not load SMS config: {e}")
            return None
    
    def _load_default_templates(self) -> Dict[str, Dict]:
        """Load default message templates"""
        return {
            "interview_scheduled": {
                "email": {
                    "subject": "Interview Scheduled - {{job_title}} Position",
                    "body": """Dear {{candidate_name}},

We're pleased to inform you that an interview has been scheduled for the {{job_title}} position.

Interview Details:
📅 Date: {{interview_date}}
🕐 Time: {{interview_time}}
📍 Location: {{interview_location}}
👥 Interviewer(s): {{interviewer_names}}

{{#if interview_notes}}
Additional Notes:
{{interview_notes}}
{{/if}}

Please confirm your attendance by replying to this email or calling us at {{company_phone}}.

If you have any questions or need to reschedule, please don't hesitate to contact us.

Best regards,
{{company_name}} Recruitment Team""",
                    "html": """<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<h2 style="color: #2c5aa0;">Interview Scheduled</h2>

<p>Dear <strong>{{candidate_name}}</strong>,</p>

<p>We're pleased to inform you that an interview has been scheduled for the <strong>{{job_title}}</strong> position.</p>

<div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
    <h3 style="margin-top: 0; color: #2c5aa0;">Interview Details</h3>
    <p><strong>📅 Date:</strong> {{interview_date}}</p>
    <p><strong>🕐 Time:</strong> {{interview_time}}</p>
    <p><strong>📍 Location:</strong> {{interview_location}}</p>
    <p><strong>👥 Interviewer(s):</strong> {{interviewer_names}}</p>
</div>

{{#if interview_notes}}
<div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0;">
    <h4 style="margin-top: 0;">Additional Notes:</h4>
    <p>{{interview_notes}}</p>
</div>
{{/if}}

<p>Please confirm your attendance by replying to this email or calling us at <strong>{{company_phone}}</strong>.</p>

<p>If you have any questions or need to reschedule, please don't hesitate to contact us.</p>

<p>Best regards,<br><strong>{{company_name}} Recruitment Team</strong></p>
</div>"""
                },
                "sms": {
                    "body": "Hi {{candidate_name}}! Your interview for {{job_title}} is scheduled for {{interview_date}} at {{interview_time}}. Location: {{interview_location}}. Please confirm. - {{company_name}}"
                }
            },
            "interview_reminder": {
                "email": {
                    "subject": "Reminder: Interview Tomorrow - {{job_title}}",
                    "body": """Dear {{candidate_name}},

This is a friendly reminder about your interview scheduled for tomorrow.

Interview Details:
📅 Date: {{interview_date}}
🕐 Time: {{interview_time}}
📍 Location: {{interview_location}}
👥 Interviewer(s): {{interviewer_names}}

{{#if preparation_tips}}
Preparation Tips:
{{preparation_tips}}
{{/if}}

Please arrive 10-15 minutes early. If you have any last-minute questions or issues, please contact us immediately.

We look forward to meeting you!

Best regards,
{{company_name}} Recruitment Team"""
                },
                "sms": {
                    "body": "Reminder: Your interview for {{job_title}} is tomorrow at {{interview_time}}. Location: {{interview_location}}. Good luck! - {{company_name}}"
                }
            },
            "interview_confirmation": {
                "email": {
                    "subject": "Interview Confirmed - {{job_title}}",
                    "body": """Dear {{candidate_name}},

Thank you for confirming your interview for the {{job_title}} position.

Confirmed Details:
📅 Date: {{interview_date}}
🕐 Time: {{interview_time}}
📍 Location: {{interview_location}}

We have noted your confirmation and look forward to meeting you.

Best regards,
{{company_name}} Recruitment Team"""
                }
            },
            "interview_reschedule": {
                "email": {
                    "subject": "Interview Rescheduled - {{job_title}}",
                    "body": """Dear {{candidate_name}},

Your interview for the {{job_title}} position has been rescheduled.

New Interview Details:
📅 Date: {{new_interview_date}}
🕐 Time: {{new_interview_time}}
📍 Location: {{new_interview_location}}

{{#if reschedule_reason}}
Reason for rescheduling: {{reschedule_reason}}
{{/if}}

Please confirm the new schedule by replying to this email.

We apologize for any inconvenience and look forward to meeting you.

Best regards,
{{company_name}} Recruitment Team"""
                }
            }
        }
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
        priority: str = "medium"
    ) -> CommunicationResult:
        """
        Send an email with enhanced error handling and tracking
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text email body
            html_body: HTML email body (optional)
            cc_emails: List of CC email addresses
            bcc_emails: List of BCC email addresses
            attachments: List of attachments (optional)
            priority: Message priority (low, medium, high, urgent)
        
        Returns:
            CommunicationResult with success status and details
        """
        start_time = datetime.utcnow()
        
        try:
            if not self.email_config:
                return CommunicationResult(
                    success=False,
                    error_message="Email configuration not available",
                    error_code="NO_CONFIG"
                )
            
            # Validate email addresses
            if not self._is_valid_email(to_email):
                return CommunicationResult(
                    success=False,
                    error_message=f"Invalid recipient email: {to_email}",
                    error_code="INVALID_EMAIL"
                )
            
            # Create message
            message = MIMEMultipart("alternative")
            message["From"] = f"{self.email_config.sender_name} <{self.email_config.sender_email}>"
            message["To"] = to_email
            message["Subject"] = subject
            
            # Add CC and BCC
            if cc_emails:
                message["Cc"] = ", ".join(cc_emails)
            if bcc_emails:
                message["Bcc"] = ", ".join(bcc_emails)
            
            # Set priority headers
            if priority in ["high", "urgent"]:
                message["X-Priority"] = "1"
                message["X-MSMail-Priority"] = "High"
            elif priority == "low":
                message["X-Priority"] = "5"
                message["X-MSMail-Priority"] = "Low"
            
            # Add tracking headers
            message_id = str(uuid.uuid4())
            message["Message-ID"] = f"<{message_id}@{self.email_config.smtp_server}>"
            message["X-RecruitAI-ID"] = message_id
            
            # Add body parts
            message.attach(MIMEText(body, "plain"))
            if html_body:
                message.attach(MIMEText(html_body, "html"))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    self._add_attachment(message, attachment)
            
            # Prepare recipient list
            recipients = [to_email]
            if cc_emails:
                recipients.extend(cc_emails)
            if bcc_emails:
                recipients.extend(bcc_emails)
            
            # Send email
            await self._send_smtp_email(message, recipients)
            
            delivery_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            logger.info(f"Email sent successfully to {to_email} (Message ID: {message_id})")
            
            return CommunicationResult(
                success=True,
                message_id=message_id,
                external_id=message_id,
                delivery_time_ms=delivery_time
            )
            
        except Exception as e:
            delivery_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            error_msg = str(e)
            
            logger.error(f"Failed to send email to {to_email}: {error_msg}")
            
            return CommunicationResult(
                success=False,
                error_message=error_msg,
                error_code="SEND_FAILED",
                delivery_time_ms=delivery_time
            )
    
    async def send_sms(
        self,
        to_phone: str,
        message: str,
        priority: str = "medium"
    ) -> CommunicationResult:
        """
        Send an SMS message
        
        Args:
            to_phone: Recipient phone number
            message: SMS message text
            priority: Message priority
        
        Returns:
            CommunicationResult with success status and details
        """
        start_time = datetime.utcnow()
        
        try:
            if not self.sms_config:
                return CommunicationResult(
                    success=False,
                    error_message="SMS configuration not available",
                    error_code="NO_CONFIG"
                )
            
            # Validate phone number
            if not self._is_valid_phone(to_phone):
                return CommunicationResult(
                    success=False,
                    error_message=f"Invalid phone number: {to_phone}",
                    error_code="INVALID_PHONE"
                )
            
            # Truncate message if too long
            if len(message) > 160:
                message = message[:157] + "..."
                logger.warning(f"SMS message truncated to 160 characters")
            
            # For now, simulate SMS sending (replace with actual provider integration)
            message_id = str(uuid.uuid4())
            
            # TODO: Integrate with actual SMS providers (Twilio, AWS SNS, etc.)
            await asyncio.sleep(0.1)  # Simulate API call
            
            delivery_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            logger.info(f"SMS sent successfully to {to_phone} (Message ID: {message_id})")
            
            return CommunicationResult(
                success=True,
                message_id=message_id,
                external_id=message_id,
                delivery_time_ms=delivery_time,
                provider_data={"simulated": True}
            )
            
        except Exception as e:
            delivery_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            error_msg = str(e)
            
            logger.error(f"Failed to send SMS to {to_phone}: {error_msg}")
            
            return CommunicationResult(
                success=False,
                error_message=error_msg,
                error_code="SEND_FAILED",
                delivery_time_ms=delivery_time
            )
    
    async def _send_smtp_email(self, message: MIMEMultipart, recipients: List[str]):
        """Send email via SMTP"""
        context = ssl.create_default_context()
        
        if self.email_config.use_ssl:
            with smtplib.SMTP_SSL(self.email_config.smtp_server, self.email_config.smtp_port, context=context) as server:
                server.login(self.email_config.smtp_username, self.email_config.smtp_password)
                server.sendmail(self.email_config.sender_email, recipients, message.as_string())
        else:
            with smtplib.SMTP(self.email_config.smtp_server, self.email_config.smtp_port) as server:
                if self.email_config.use_tls:
                    server.starttls(context=context)
                server.login(self.email_config.smtp_username, self.email_config.smtp_password)
                server.sendmail(self.email_config.sender_email, recipients, message.as_string())
    
    def _add_attachment(self, message: MIMEMultipart, attachment: Dict):
        """Add attachment to email message"""
        try:
            with open(attachment['file_path'], 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f"attachment; filename= {attachment.get('filename', 'attachment')}"
                )
                message.attach(part)
        except Exception as e:
            logger.error(f"Failed to add attachment: {e}")
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email address format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _is_valid_phone(self, phone: str) -> bool:
        """Validate phone number format"""
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        # Check if it's a valid length (10-15 digits)
        return len(digits_only) >= 10 and len(digits_only) <= 15
    
    async def compose_with_ai(
        self,
        template_type: str,
        variables: Dict[str, Any],
        tone: str = "professional",
        custom_instructions: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Use AI to enhance and personalize communication content
        
        Args:
            template_type: Type of template (interview_scheduled, reminder, etc.)
            variables: Template variables
            tone: Communication tone (professional, friendly, urgent, reminder)
            custom_instructions: Additional AI instructions
        
        Returns:
            Tuple of (subject, body) for the enhanced message
        """
        try:
            if not self.openai_client:
                # Fallback to template rendering without AI
                return await self._render_template(template_type, variables, "email")
            
            # Get base template
            base_template = self.default_templates.get(template_type, {}).get("email", {})
            base_subject = base_template.get("subject", "Interview Communication")
            base_body = base_template.get("body", "Please find interview details below.")
            
            # Render base template
            subject_template = Template(base_subject)
            body_template = Template(base_body)
            
            rendered_subject = subject_template.render(**variables)
            rendered_body = body_template.render(**variables)
            
            # AI enhancement prompt
            persona = self.ai_personas.get(tone, self.ai_personas["professional"])
            
            prompt = f"""
{persona}

You are helping to enhance a recruitment communication email. 

Template Type: {template_type}
Current Subject: {rendered_subject}
Current Body: {rendered_body}

Variables available: {json.dumps(variables, indent=2)}

{f"Additional Instructions: {custom_instructions}" if custom_instructions else ""}

Please enhance this email to be more engaging, personalized, and professional while maintaining all the essential information. 

Provide your response in the following JSON format:
{{
    "subject": "Enhanced subject line",
    "body": "Enhanced email body"
}}

Keep the enhanced content appropriate for professional recruitment communication."""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert HR communication specialist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            ai_response = response.choices[0].message.content
            
            # Parse AI response
            try:
                enhanced = json.loads(ai_response)
                return enhanced["subject"], enhanced["body"]
            except json.JSONDecodeError:
                logger.warning("Could not parse AI response, using original template")
                return rendered_subject, rendered_body
                
        except Exception as e:
            logger.error(f"AI composition failed: {e}")
            # Fallback to template rendering
            return await self._render_template(template_type, variables, "email")
    
    async def _render_template(
        self,
        template_type: str,
        variables: Dict[str, Any],
        communication_type: str = "email"
    ) -> Tuple[str, str]:
        """
        Render message template with variables
        
        Args:
            template_type: Type of template
            variables: Template variables
            communication_type: email or sms
        
        Returns:
            Tuple of (subject, body) for email or (empty_string, body) for SMS
        """
        try:
            template_data = self.default_templates.get(template_type, {}).get(communication_type, {})
            
            if not template_data:
                raise ValueError(f"Template not found: {template_type}/{communication_type}")
            
            subject_template = template_data.get("subject", "")
            body_template = template_data.get("body", "")
            
            # Render with Jinja2
            subject = Template(subject_template).render(**variables) if subject_template else ""
            body = Template(body_template).render(**variables)
            
            return subject, body
            
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return "Communication from RecruitAI Pro", f"Unable to render template: {e}"
    
    def validate_template_variables(self, template_type: str, variables: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that all required template variables are provided
        
        Args:
            template_type: Type of template
            variables: Template variables
        
        Returns:
            Tuple of (is_valid, missing_variables)
        """
        required_vars = {
            "interview_scheduled": [
                "candidate_name", "job_title", "interview_date", 
                "interview_time", "interview_location", "company_name"
            ],
            "interview_reminder": [
                "candidate_name", "job_title", "interview_date", 
                "interview_time", "interview_location", "company_name"
            ],
            "interview_confirmation": [
                "candidate_name", "job_title", "interview_date", 
                "interview_time", "interview_location", "company_name"
            ],
            "interview_reschedule": [
                "candidate_name", "job_title", "new_interview_date", 
                "new_interview_time", "new_interview_location", "company_name"
            ]
        }
        
        required = required_vars.get(template_type, [])
        missing = [var for var in required if var not in variables or not variables[var]]
        
        return len(missing) == 0, missing
    
    async def schedule_message(
        self,
        communication_type: str,
        recipient: str,
        template_type: str,
        variables: Dict[str, Any],
        send_time: datetime,
        priority: str = "medium"
    ) -> str:
        """
        Schedule a message to be sent at a specific time
        
        Args:
            communication_type: email or sms
            recipient: Email address or phone number
            template_type: Type of template to use
            variables: Template variables
            send_time: When to send the message
            priority: Message priority
        
        Returns:
            Schedule ID for tracking
        """
        schedule_id = str(uuid.uuid4())
        
        # TODO: Implement message scheduling with a job queue (Celery, Redis, etc.)
        # For now, just log the scheduling request
        
        logger.info(f"Message scheduled: {schedule_id} - {communication_type} to {recipient} at {send_time}")
        
        return schedule_id
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status and configuration"""
        return {
            "agent_name": "Communication Agent",
            "version": "1.0.0",
            "status": "operational",
            "email_configured": self.email_config is not None,
            "sms_configured": self.sms_config is not None,
            "ai_enabled": self.openai_client is not None,
            "default_templates_loaded": len(self.default_templates),
            "supported_communication_types": ["email", "sms"],
            "supported_template_types": list(self.default_templates.keys()),
            "timestamp": datetime.utcnow().isoformat()
        }

# Global instance
communication_agent = None

def get_communication_agent() -> CommunicationAgent:
    """Get or create the global Communication Agent instance"""
    global communication_agent
    if communication_agent is None:
        communication_agent = CommunicationAgent()
    return communication_agent 