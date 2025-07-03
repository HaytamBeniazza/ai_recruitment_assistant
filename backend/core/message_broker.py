"""
Redis Message Broker for RecruitAI Pro
Handles inter-agent communication and task queuing
"""

import redis
import json
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime

# Import settings
from .config import settings

class MessageBroker:
    """Redis-based message broker for agent communication"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True
        )
        self.subscribers = {}
        print(f"🔗 Connected to Redis: {settings.redis_host}:{settings.redis_port}")
    
    def publish_message(self, channel: str, message: Dict[str, Any]) -> bool:
        """
        Publish a message to a channel
        
        Args:
            channel: Channel name (e.g., 'resume_analysis', 'scheduling', 'communication')
            message: Message data as dictionary
            
        Returns:
            bool: True if message published successfully
        """
        try:
            # Add metadata to message
            enriched_message = {
                "timestamp": datetime.utcnow().isoformat(),
                "channel": channel,
                "data": message
            }
            
            # Publish to Redis
            result = self.redis_client.publish(channel, json.dumps(enriched_message))
            print(f"📤 Published to '{channel}': {message.get('type', 'unknown')}")
            return result > 0
            
        except Exception as e:
            print(f"❌ Error publishing message to '{channel}': {e}")
            return False
    
    def subscribe_to_channel(self, channel: str, callback: Callable) -> None:
        """
        Subscribe to a channel with callback function
        
        Args:
            channel: Channel name to subscribe to
            callback: Function to call when message received
        """
        try:
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe(channel)
            
            self.subscribers[channel] = {
                "pubsub": pubsub,
                "callback": callback
            }
            
            print(f"📥 Subscribed to channel: '{channel}'")
            
            # Start listening in background
            self._start_listening(channel)
            
        except Exception as e:
            print(f"❌ Error subscribing to '{channel}': {e}")
    
    def _start_listening(self, channel: str) -> None:
        """Start listening for messages on a channel"""
        async def listen():
            pubsub = self.subscribers[channel]["pubsub"]
            callback = self.subscribers[channel]["callback"]
            
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        # Parse message
                        data = json.loads(message['data'])
                        
                        # Call callback function
                        await callback(data)
                        
                    except Exception as e:
                        print(f"❌ Error processing message on '{channel}': {e}")
        
        # Run listener in background
        asyncio.create_task(listen())
    
    def send_to_agent(self, agent_name: str, message_type: str, data: Dict[str, Any]) -> bool:
        """
        Send a message to a specific agent
        
        Args:
            agent_name: Target agent ('resume_analyzer', 'scheduler', 'communication')
            message_type: Type of message ('task', 'response', 'status')
            data: Message payload
            
        Returns:
            bool: True if message sent successfully
        """
        message = {
            "type": message_type,
            "target_agent": agent_name,
            "payload": data
        }
        
        channel = f"agent_{agent_name}"
        return self.publish_message(channel, message)
    
    def broadcast_status(self, agent_name: str, status: str, details: Dict[str, Any] = None) -> bool:
        """
        Broadcast agent status update
        
        Args:
            agent_name: Name of the agent
            status: Status ('active', 'busy', 'error', 'idle')
            details: Additional status information
            
        Returns:
            bool: True if status broadcasted successfully
        """
        message = {
            "type": "status_update",
            "agent": agent_name,
            "status": status,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return self.publish_message("agent_status", message)
    
    def get_agent_queue_size(self, agent_name: str) -> int:
        """Get the number of pending tasks for an agent"""
        try:
            queue_name = f"queue_{agent_name}"
            return self.redis_client.llen(queue_name)
        except Exception as e:
            print(f"❌ Error getting queue size for '{agent_name}': {e}")
            return 0
    
    def add_to_queue(self, agent_name: str, task: Dict[str, Any]) -> bool:
        """
        Add a task to an agent's queue
        
        Args:
            agent_name: Target agent name
            task: Task data
            
        Returns:
            bool: True if task added successfully
        """
        try:
            queue_name = f"queue_{agent_name}"
            
            # Add metadata to task
            enriched_task = {
                "id": f"{agent_name}_{datetime.utcnow().timestamp()}",
                "timestamp": datetime.utcnow().isoformat(),
                "agent": agent_name,
                "task": task
            }
            
            # Add to Redis list (queue)
            self.redis_client.lpush(queue_name, json.dumps(enriched_task))
            print(f"📋 Added task to {agent_name} queue")
            return True
            
        except Exception as e:
            print(f"❌ Error adding task to '{agent_name}' queue: {e}")
            return False
    
    def get_next_task(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the next task from an agent's queue
        
        Args:
            agent_name: Agent name
            
        Returns:
            Dict containing task data or None if queue empty
        """
        try:
            queue_name = f"queue_{agent_name}"
            
            # Pop from right (FIFO queue)
            task_data = self.redis_client.rpop(queue_name)
            
            if task_data:
                return json.loads(task_data)
            return None
            
        except Exception as e:
            print(f"❌ Error getting task from '{agent_name}' queue: {e}")
            return None
    
    def check_connection(self) -> bool:
        """Check if Redis connection is working"""
        try:
            self.redis_client.ping()
            print("✅ Redis connection successful")
            return True
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Redis and message broker statistics"""
        try:
            info = self.redis_client.info()
            
            # Get queue sizes for all agents
            agent_queues = {}
            for agent in ['resume_analyzer', 'scheduler', 'communication']:
                agent_queues[agent] = self.get_agent_queue_size(agent)
            
            return {
                "connection": "active",
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "agent_queues": agent_queues,
                "total_pending_tasks": sum(agent_queues.values())
            }
            
        except Exception as e:
            return {
                "connection": "failed",
                "error": str(e)
            }

# Create global message broker instance
message_broker = MessageBroker()

# Check connection on import
message_broker.check_connection()

print(f"📨 Message Broker initialized")
print(f"   Redis: {settings.redis_host}:{settings.redis_port}")
print(f"   Database: {settings.redis_db}")
print(f"   Status: Ready for inter-agent communication") 