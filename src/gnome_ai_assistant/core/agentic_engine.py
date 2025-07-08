"""Agentic engine implementing Plan-Do-Check-Act (OODA) loop."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from ..utils.logger import get_logger
from ..llm.base import BaseLLM, Message, MessageRole
from ..tools.base import ToolRegistry, ToolResponse
from ..core.permissions import PermissionManager, PermissionLevel
from ..core.memory import MemoryManager

logger = get_logger("agentic_engine")


class TaskStatus(Enum):
    """Task execution status."""
    PLANNING = "planning"
    EXECUTING = "executing"
    CHECKING = "checking"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Step execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskStep:
    """Represents a single step in task execution."""
    id: str
    tool_name: str
    action: str
    parameters: Dict[str, Any]
    description: str
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            **asdict(self),
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class Task:
    """Represents a task with multiple steps."""
    id: str
    user_request: str
    description: str
    steps: List[TaskStep]
    status: TaskStatus = TaskStatus.PLANNING
    current_step: int = 0
    context: Optional[Dict[str, Any]] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    user_id: str = "default"
    session_id: str = "default"
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def get_current_step(self) -> Optional[TaskStep]:
        """Get current step."""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None
    
    def advance_step(self) -> bool:
        """Advance to next step."""
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            return True
        return False
    
    def get_progress(self) -> float:
        """Get task progress (0.0 to 1.0)."""
        if not self.steps:
            return 0.0
        
        completed_steps = sum(1 for step in self.steps if step.status == StepStatus.COMPLETED)
        return completed_steps / len(self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            **asdict(self),
            "status": self.status.value,
            "steps": [step.to_dict() for step in self.steps],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.get_progress()
        }


@dataclass
class AgenticResponse:
    """Response from agentic engine."""
    response: str
    function_calls: Optional[List[Dict[str, Any]]] = None
    context: Optional[Dict[str, Any]] = None
    task_id: Optional[str] = None
    task_status: Optional[str] = None
    progress: float = 0.0


class AgenticEngine:
    """Implements agentic behavior using Plan-Do-Check-Act (OODA) loop."""
    
    def __init__(self, llm_engine: BaseLLM, tool_registry: ToolRegistry, 
                 permission_manager: PermissionManager, memory_manager: MemoryManager):
        """
        Initialize agentic engine.
        
        Args:
            llm_engine: LLM provider
            tool_registry: Tool registry
            permission_manager: Permission manager
            memory_manager: Memory manager
        """
        self.llm_engine = llm_engine
        self.tool_registry = tool_registry
        self.permission_manager = permission_manager
        self.memory_manager = memory_manager
        
        # Active tasks
        self.active_tasks: Dict[str, Task] = {}
        
        # Task execution settings
        self.max_concurrent_tasks = 5
        self.task_timeout = timedelta(minutes=30)
        self.step_timeout = timedelta(minutes=5)
        
        # Progress callbacks
        self.progress_callbacks: List[Callable] = []
        
        # System prompts
        self.system_prompts = {
            "planner": """You are an AI task planner. Your job is to break down user requests into specific, actionable steps using available tools.

Available tools: {tools}

When planning:
1. Analyze the user request carefully
2. Break it down into logical steps
3. Use appropriate tools for each step
4. Consider dependencies between steps
5. Be specific about parameters needed

Respond with a JSON plan containing an array of steps, each with:
- tool_name: The tool to use
- action: The specific action
- parameters: Required parameters
- description: What this step accomplishes

Example:
{
  "plan": [
    {
      "tool_name": "file_manager",
      "action": "read",
      "parameters": {"path": "/home/user/document.txt"},
      "description": "Read the document to analyze its content"
    }
  ],
  "reasoning": "Explanation of the plan"
}""",
            
            "executor": """You are an AI task executor. You execute individual steps and handle results.

Current step: {step}
Previous results: {results}
Context: {context}

Execute this step and provide the result. If the step fails, suggest how to recover or modify the approach.""",
            
            "checker": """You are an AI quality checker. Review task execution results and determine if the task was completed successfully.

Task: {task}
Steps executed: {steps}
Results: {results}

Determine:
1. Was the task completed successfully?
2. Are there any issues that need addressing?
3. Should any steps be retried or modified?
4. What is the final result for the user?

Respond with JSON:
{
  "success": true/false,
  "issues": ["list of issues if any"],
  "retry_steps": [step_indices_to_retry],
  "final_result": "summary for user",
  "recommendations": ["suggestions for improvement"]
}"""
        }
    
    async def initialize(self) -> None:
        """Initialize the agentic engine."""
        try:
            # Start task monitoring
            asyncio.create_task(self._task_monitor())
            logger.info("Agentic engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize agentic engine: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup agentic engine resources."""
        try:
            # Cancel active tasks
            for task in self.active_tasks.values():
                if task.status in [TaskStatus.PLANNING, TaskStatus.EXECUTING]:
                    task.status = TaskStatus.CANCELLED
            
            logger.info("Agentic engine cleanup completed")
        except Exception as e:
            logger.error(f"Error during agentic engine cleanup: {e}")
    
    async def process_request(self, user_request: str, context: Dict[str, Any] = None, 
                            user_id: str = "default", session_id: str = "default") -> AgenticResponse:
        """
        Process user request through OODA loop.
        
        Args:
            user_request: User's request
            context: Additional context
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Agentic response
        """
        try:
            # Observe: Analyze the request and gather context
            enhanced_context = await self._observe(user_request, context, user_id, session_id)
            
            # Orient: Determine if this requires a multi-step task or simple response
            task_required = await self._orient(user_request, enhanced_context)
            
            if task_required:
                # Decide: Plan the task
                task = await self._decide(user_request, enhanced_context, user_id, session_id)
                
                # Act: Execute the task
                result = await self._act(task)
                
                return AgenticResponse(
                    response=result.get("response", "Task completed"),
                    function_calls=result.get("function_calls", []),
                    context=result.get("context", {}),
                    task_id=task.id,
                    task_status=task.status.value,
                    progress=task.get_progress()
                )
            else:
                # Simple response without task planning
                response = await self._simple_response(user_request, enhanced_context)
                
                return AgenticResponse(
                    response=response.content,
                    function_calls=response.function_calls,
                    context=enhanced_context
                )
        
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return AgenticResponse(
                response=f"I encountered an error processing your request: {str(e)}",
                context=context or {}
            )
    
    async def _observe(self, user_request: str, context: Dict[str, Any], 
                      user_id: str, session_id: str) -> Dict[str, Any]:
        """Observe and gather context (OODA: Observe)."""
        try:
            enhanced_context = context.copy() if context else {}
            
            # Get conversation history
            conversation_history = await self.memory_manager.get_conversation_context(
                session_id, max_messages=10
            )
            enhanced_context["conversation_history"] = [msg.to_dict() for msg in conversation_history]
            
            # Search relevant memories
            relevant_memories = await self.memory_manager.search_memory(user_request, limit=5)
            enhanced_context["relevant_memories"] = [memory.to_dict() for memory in relevant_memories]
            
            # Get available tools
            available_tools = self.tool_registry.get_tool_schemas()
            enhanced_context["available_tools"] = available_tools
            
            # Current time and environment
            enhanced_context["current_time"] = datetime.now().isoformat()
            enhanced_context["user_id"] = user_id
            enhanced_context["session_id"] = session_id
            
            return enhanced_context
        
        except Exception as e:
            logger.error(f"Error in observe phase: {e}")
            return context or {}
    
    async def _orient(self, user_request: str, context: Dict[str, Any]) -> bool:
        """Orient and determine approach (OODA: Orient)."""
        try:
            # Check if request requires tool usage or multi-step planning
            tool_keywords = ["file", "window", "open", "close", "search", "install", "run", "execute", "manage"]
            complex_keywords = ["and then", "after that", "first", "second", "next", "finally"]
            
            request_lower = user_request.lower()
            
            # Simple heuristics to determine if task planning is needed
            has_tool_keywords = any(keyword in request_lower for keyword in tool_keywords)
            has_complex_structure = any(keyword in request_lower for keyword in complex_keywords)
            is_long_request = len(user_request.split()) > 20
            
            return has_tool_keywords or has_complex_structure or is_long_request
        
        except Exception as e:
            logger.error(f"Error in orient phase: {e}")
            return False
    
    async def _decide(self, user_request: str, context: Dict[str, Any], 
                     user_id: str, session_id: str) -> Task:
        """Decide and plan the task (OODA: Decide)."""
        try:
            # Generate task plan using LLM
            plan_prompt = self.system_prompts["planner"].format(
                tools=json.dumps(context["available_tools"], indent=2)
            )
            
            messages = [
                Message(MessageRole.SYSTEM, plan_prompt),
                Message(MessageRole.USER, f"Plan this request: {user_request}")
            ]
            
            # Add context if available
            if context.get("conversation_history"):
                context_msg = f"Previous conversation: {json.dumps(context['conversation_history'][-3:])}"
                messages.append(Message(MessageRole.USER, context_msg))
            
            response = await self.llm_engine.generate_response(messages)
            
            # Parse the plan
            try:
                plan_data = json.loads(response.content)
                steps_data = plan_data.get("plan", [])
            except json.JSONDecodeError:
                # Fallback: create a simple single-step plan
                steps_data = [{
                    "tool_name": "general",
                    "action": "respond",
                    "parameters": {"query": user_request},
                    "description": "Provide a response to the user"
                }]
            
            # Create task steps
            steps = []
            for i, step_data in enumerate(steps_data):
                step = TaskStep(
                    id=f"step_{i}",
                    tool_name=step_data.get("tool_name", "general"),
                    action=step_data.get("action", "execute"),
                    parameters=step_data.get("parameters", {}),
                    description=step_data.get("description", f"Step {i+1}")
                )
                steps.append(step)
            
            # Create task
            task = Task(
                id=str(uuid.uuid4()),
                user_request=user_request,
                description=plan_data.get("reasoning", f"Execute user request: {user_request}"),
                steps=steps,
                context=context,
                user_id=user_id,
                session_id=session_id
            )
            
            # Store task
            self.active_tasks[task.id] = task
            
            logger.info(f"Created task {task.id} with {len(steps)} steps")
            return task
        
        except Exception as e:
            logger.error(f"Error in decide phase: {e}")
            # Create fallback task
            fallback_task = Task(
                id=str(uuid.uuid4()),
                user_request=user_request,
                description="Fallback task",
                steps=[],
                context=context,
                user_id=user_id,
                session_id=session_id
            )
            self.active_tasks[fallback_task.id] = fallback_task
            return fallback_task
    
    async def _act(self, task: Task) -> Dict[str, Any]:
        """Act and execute the task (OODA: Act)."""
        try:
            task.status = TaskStatus.EXECUTING
            task.started_at = datetime.now()
            
            results = []
            
            # Execute each step
            for i, step in enumerate(task.steps):
                task.current_step = i
                
                # Notify progress
                await self._notify_progress(task)
                
                # Execute step
                step_result = await self._execute_step(task, step)
                results.append(step_result)
                
                # Check if step failed and decide whether to continue
                if step.status == StepStatus.FAILED:
                    if step.retry_count < step.max_retries:
                        # Retry the step
                        step.retry_count += 1
                        step.status = StepStatus.PENDING
                        i -= 1  # Retry current step
                        continue
                    else:
                        # Step failed permanently
                        task.status = TaskStatus.FAILED
                        break
                
                # Check if we should continue
                if step.status != StepStatus.COMPLETED:
                    break
            
            # Check results and determine final status
            task.completed_at = datetime.now()
            final_result = await self._check_results(task, results)
            
            if task.status != TaskStatus.FAILED:
                task.status = TaskStatus.COMPLETED if final_result.get("success", True) else TaskStatus.FAILED
            
            # Save conversation context
            if task.session_id:
                await self.memory_manager.add_message(
                    task.session_id,
                    Message(MessageRole.USER, task.user_request)
                )
                await self.memory_manager.add_message(
                    task.session_id,
                    Message(MessageRole.ASSISTANT, final_result.get("response", "Task completed"))
                )
            
            # Final progress notification
            await self._notify_progress(task)
            
            return final_result
        
        except Exception as e:
            logger.error(f"Error in act phase: {e}")
            task.status = TaskStatus.FAILED
            return {
                "success": False,
                "response": f"Task execution failed: {str(e)}",
                "context": task.context or {}
            }
    
    async def _execute_step(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """Execute a single task step."""
        try:
            step.status = StepStatus.IN_PROGRESS
            step.started_at = datetime.now()
            
            logger.info(f"Executing step {step.id}: {step.description}")
            
            # Execute tool
            if step.tool_name in self.tool_registry.tools:
                result = await self.tool_registry.execute_tool(
                    step.tool_name,
                    permission_manager=self.permission_manager,
                    **step.parameters
                )
                
                if result.success:
                    step.status = StepStatus.COMPLETED
                    step.result = result.result
                else:
                    step.status = StepStatus.FAILED
                    step.error = result.error
            else:
                # Handle unknown tools or general responses
                response = await self._handle_general_step(task, step)
                step.status = StepStatus.COMPLETED
                step.result = response
            
            step.completed_at = datetime.now()
            
            return {
                "step_id": step.id,
                "success": step.status == StepStatus.COMPLETED,
                "result": step.result,
                "error": step.error
            }
        
        except Exception as e:
            logger.error(f"Error executing step {step.id}: {e}")
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.completed_at = datetime.now()
            
            return {
                "step_id": step.id,
                "success": False,
                "error": str(e)
            }
    
    async def _handle_general_step(self, task: Task, step: TaskStep) -> str:
        """Handle general steps that don't use specific tools."""
        try:
            # Use LLM to generate response for general steps
            messages = [
                Message(MessageRole.SYSTEM, "You are a helpful AI assistant."),
                Message(MessageRole.USER, f"Task: {task.user_request}\nStep: {step.description}\nParameters: {step.parameters}")
            ]
            
            response = await self.llm_engine.generate_response(messages)
            return response.content
        
        except Exception as e:
            logger.error(f"Error handling general step: {e}")
            return f"Unable to complete step: {str(e)}"
    
    async def _check_results(self, task: Task, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check task results and generate final response."""
        try:
            # Use LLM to analyze results and generate final response
            check_prompt = self.system_prompts["checker"].format(
                task=task.user_request,
                steps=[step.to_dict() for step in task.steps],
                results=results
            )
            
            messages = [
                Message(MessageRole.SYSTEM, check_prompt),
                Message(MessageRole.USER, "Analyze the task execution and provide final assessment.")
            ]
            
            response = await self.llm_engine.generate_response(messages)
            
            try:
                result_data = json.loads(response.content)
            except json.JSONDecodeError:
                # Fallback response
                success = all(result.get("success", False) for result in results)
                result_data = {
                    "success": success,
                    "final_result": response.content if success else "Task execution encountered issues",
                    "issues": [] if success else ["Failed to parse detailed results"]
                }
            
            return {
                "success": result_data.get("success", True),
                "response": result_data.get("final_result", "Task completed"),
                "issues": result_data.get("issues", []),
                "context": task.context or {},
                "function_calls": []
            }
        
        except Exception as e:
            logger.error(f"Error checking results: {e}")
            return {
                "success": False,
                "response": f"Task completed with errors: {str(e)}",
                "context": task.context or {}
            }
    
    async def _simple_response(self, user_request: str, context: Dict[str, Any]) -> Any:
        """Generate simple response without task planning."""
        try:
            # Build context message
            context_parts = []
            if context.get("conversation_history"):
                context_parts.append("Previous conversation context available.")
            if context.get("relevant_memories"):
                context_parts.append("Relevant memories found.")
            
            messages = [
                Message(MessageRole.SYSTEM, "You are a helpful AI assistant for GNOME desktop."),
                Message(MessageRole.USER, user_request)
            ]
            
            if context_parts:
                context_msg = f"Additional context: {' '.join(context_parts)}"
                messages.append(Message(MessageRole.SYSTEM, context_msg))
            
            # Get available tools for function calling
            available_tools = context.get("available_tools", [])
            
            return await self.llm_engine.generate_response(messages, functions=available_tools)
        
        except Exception as e:
            logger.error(f"Error generating simple response: {e}")
            return AgenticResponse(
                response=f"I apologize, but I encountered an error: {str(e)}",
                context=context
            )
    
    async def _notify_progress(self, task: Task) -> None:
        """Notify progress callbacks about task status."""
        try:
            progress_data = {
                "task_id": task.id,
                "status": task.status.value,
                "progress": task.get_progress(),
                "current_step": task.current_step,
                "total_steps": len(task.steps)
            }
            
            for callback in self.progress_callbacks:
                try:
                    await callback(progress_data)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
        
        except Exception as e:
            logger.error(f"Error notifying progress: {e}")
    
    async def _task_monitor(self) -> None:
        """Background task to monitor and cleanup tasks."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.now()
                expired_tasks = []
                
                for task_id, task in self.active_tasks.items():
                    # Check for timeout
                    if (task.status in [TaskStatus.EXECUTING, TaskStatus.PLANNING] and 
                        task.created_at and 
                        current_time - task.created_at > self.task_timeout):
                        
                        task.status = TaskStatus.FAILED
                        expired_tasks.append(task_id)
                
                # Remove expired tasks
                for task_id in expired_tasks:
                    del self.active_tasks[task_id]
                    logger.info(f"Removed expired task: {task_id}")
                
                # Cleanup completed tasks older than 1 hour
                old_tasks = [
                    task_id for task_id, task in self.active_tasks.items()
                    if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] and
                        task.completed_at and
                        current_time - task.completed_at > timedelta(hours=1))
                ]
                
                for task_id in old_tasks:
                    del self.active_tasks[task_id]
                
                if old_tasks:
                    logger.info(f"Cleaned up {len(old_tasks)} old tasks")
            
            except Exception as e:
                logger.error(f"Error in task monitor: {e}")
    
    def add_progress_callback(self, callback: Callable) -> None:
        """Add progress callback function."""
        self.progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable) -> None:
        """Remove progress callback function."""
        if callback in self.progress_callbacks:
            self.progress_callbacks.remove(callback)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status."""
        if task_id in self.active_tasks:
            return self.active_tasks[task_id].to_dict()
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if task.status in [TaskStatus.PLANNING, TaskStatus.EXECUTING]:
                task.status = TaskStatus.CANCELLED
                return True
        return False
    
    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """List all active tasks."""
        return [task.to_dict() for task in self.active_tasks.values()]
