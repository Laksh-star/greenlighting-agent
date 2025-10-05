"""
Base Agent class for all subagents in the Greenlighting system.
Provides common functionality and interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY, MODEL_NAME, MAX_TOKENS


class BaseAgent(ABC):
    """Base class for all agents in the system."""
    
    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str,
        tools: Optional[List[Dict]] = None
    ):
        """
        Initialize the base agent.
        
        Args:
            name: Agent name
            role: Agent's role/responsibility
            system_prompt: System prompt defining agent behavior
            tools: Optional list of tools this agent can use
        """
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.conversation_history: List[Dict] = []
        
    @abstractmethod
    async def analyze(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main analysis method - must be implemented by subagents.
        
        Args:
            project_data: Dictionary containing project information
            
        Returns:
            Dictionary with analysis results
        """
        pass
    
    def _call_claude(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        temperature: float = 1.0,
        stream: bool = False
    ) -> Any:
        """
        Call Claude API with messages.
        
        Args:
            messages: List of message dictionaries
            system: Optional system prompt override
            temperature: Sampling temperature
            stream: Whether to stream the response
            
        Returns:
            API response
        """
        try:
            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system=system or self.system_prompt,
                messages=messages,
                temperature=temperature,
                stream=stream
            )
            return response
        except Exception as e:
            raise Exception(f"Error calling Claude API: {str(e)}")
    
    def add_to_history(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content
        })
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
    
    def get_summary(self) -> str:
        """Get a summary of this agent's purpose."""
        return f"**{self.name}**\nRole: {self.role}"
    
    def format_result(
        self,
        findings: str,
        confidence: float,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Format analysis result in standard structure.
        
        Args:
            findings: Main analysis findings
            confidence: Confidence score (0-1)
            metadata: Additional metadata
            
        Returns:
            Formatted result dictionary
        """
        return {
            "agent": self.name,
            "role": self.role,
            "findings": findings,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
    
    async def _execute_tool(self, tool_name: str, tool_input: Dict) -> Any:
        """
        Execute a tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            
        Returns:
            Tool execution result
        """
        # This will be implemented when we add MCP integration
        # For now, it's a placeholder
        raise NotImplementedError(f"Tool execution not yet implemented: {tool_name}")
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', role='{self.role}')>"
