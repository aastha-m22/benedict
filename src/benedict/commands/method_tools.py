"""Method File Tools

Tools for operating on method files.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from .tool_framework import Tool, ToolResult

logger = logging.getLogger(__name__)


class UpdatePCTool(Tool):
    """Tool for updating program counter."""
    
    def __init__(self, method_reader=None, method_writer=None):
        """Initialize tool.
        
        Args:
            method_reader: MethodReader instance
            method_writer: MethodWriter instance
        """
        super().__init__(
            name="update_pc",
            description="Update program counter (current phase, iteration, step). The program counter tracks where the project is in its methodology."
        )
        self.method_reader = method_reader
        self.method_writer = method_writer
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "description": "Phase name (e.g., conception, design, sprint, review)"
                    },
                    "iteration": {
                        "type": "integer",
                        "description": "Iteration number (e.g., 1, 2, 3)"
                    },
                    "step": {
                        "type": "string",
                        "description": "Step name within the phase"
                    }
                }
            }
        }
    
    def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute tool."""
        if not self.method_writer or not context:
            return ToolResult(
                success=False,
                error="Method writer or context not available"
            )
        
        workspace_path = context.get("workspace_path")
        if not workspace_path:
            return ToolResult(
                success=False,
                error="workspace_path not provided in context"
            )
        
        try:
            self.method_writer.update_pc(
                Path(workspace_path),
                phase=arguments.get("phase"),
                iteration=arguments.get("iteration"),
                step=arguments.get("step")
            )
            
            result_parts = ["Updated program counter"]
            if arguments.get("phase"):
                result_parts.append(f"Phase: {arguments['phase']}")
            if arguments.get("iteration"):
                result_parts.append(f"Iteration: {arguments['iteration']}")
            if arguments.get("step"):
                result_parts.append(f"Step: {arguments['step']}")
            
            return ToolResult(
                success=True,
                message=" - ".join(result_parts)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )


class UpdateConcernTool(Tool):
    """Tool for updating concern state."""
    
    def __init__(self, method_reader=None, method_writer=None):
        """Initialize tool.
        
        Args:
            method_reader: MethodReader instance
            method_writer: MethodWriter instance
        """
        super().__init__(
            name="update_concern",
            description="Update a concern's current state. Concerns track different aspects of the project (scope, documentation, development, etc.)."
        )
        self.method_reader = method_reader
        self.method_writer = method_writer
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "concern": {
                        "type": "string",
                        "description": "Concern name (e.g., scope, documentation, development, communication, operations, feedback)"
                    },
                    "state": {
                        "type": "string",
                        "description": "New state value (must be valid for the concern type)"
                    }
                },
                "required": ["concern", "state"]
            }
        }
    
    def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute tool."""
        if not self.method_writer or not context:
            return ToolResult(
                success=False,
                error="Method writer or context not available"
            )
        
        workspace_path = context.get("workspace_path")
        if not workspace_path:
            return ToolResult(
                success=False,
                error="workspace_path not provided in context"
            )
        
        concern = arguments.get("concern")
        state = arguments.get("state")
        
        if not concern or not state:
            return ToolResult(
                success=False,
                error="Missing required parameters: concern, state"
            )
        
        try:
            self.method_writer.update_concern(Path(workspace_path), concern, state)
            return ToolResult(
                success=True,
                message=f"Updated concern '{concern}' to state '{state}'"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )


class GetMethodStateTool(Tool):
    """Tool for getting current method file state."""
    
    def __init__(self, method_reader=None):
        """Initialize tool.
        
        Args:
            method_reader: MethodReader instance
        """
        super().__init__(
            name="get_method_state",
            description="Get current method file state including phase, iteration, step, and all concern states. "
                        "The method file (.benedict.method.yaml) is the SECOND MOST VALUABLE file in the repository (after state.json). "
                        "ALWAYS use this tool when asked about project state, phases, concerns, or methodology. "
                        "This is your primary source of truth for understanding the project's current methodology state."
        )
        self.method_reader = method_reader
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {}
            }
        }
    
    def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute tool."""
        if not self.method_reader or not context:
            return ToolResult(
                success=False,
                error="Method reader or context not available"
            )
        
        workspace_path = context.get("workspace_path")
        if not workspace_path:
            return ToolResult(
                success=False,
                error="workspace_path not provided in context"
            )
        
        try:
            method_data = self.method_reader.read_method(Path(workspace_path))
            if not method_data:
                return ToolResult(
                    success=False,
                    error="Method file not found"
                )
            
            method = method_data.get("method", {})
            pc = method.get("pc", {})
            concerns = method.get("concerns", {})
            sequence = method.get("sequence", {})
            
            # Build a clear, structured summary
            phase = pc.get("phase", "unknown")
            iteration = pc.get("iteration", "?")
            step = pc.get("step", "?")
            
            # Find active concerns (those with active states)
            active_concerns = {k: v for k, v in concerns.items() if v in ["active", "in_progress", "drafting"]}
            
            summary = {
                "phase": phase,
                "iteration": iteration,
                "step": step,
                "all_concerns": concerns,
                "active_concerns": active_concerns,
                "sequence_phases": {k: {"status": v.get("status"), "iteration": v.get("iteration")} for k, v in sequence.items()}
            }
            
            # Return both structured data and a clear message
            message_parts = [f"Phase: {phase} (iteration {iteration}, step: {step})"]
            if active_concerns:
                concern_list = ", ".join([f"{k}: {v}" for k, v in active_concerns.items()])
                message_parts.append(f"Active concerns: {concern_list}")
            else:
                message_parts.append("No active concerns")
            
            return ToolResult(
                success=True,
                data=method_data,  # Return full method data for reference
                message="\n".join(message_parts)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )


class CreateMethodTool(Tool):
    """Tool for creating a new method file."""
    
    def __init__(self, method_writer=None):
        """Initialize tool.
        
        Args:
            method_writer: MethodWriter instance
        """
        super().__init__(
            name="create_method",
            description="Create a new method file (.benedict.method.yaml) for the repository. "
                        "This initializes the methodology tracking system with default values. "
                        "Use this when the method file doesn't exist yet."
        )
        self.method_writer = method_writer
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {}
            }
        }
    
    def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute tool."""
        if not self.method_writer or not context:
            return ToolResult(
                success=False,
                error="Method writer or context not available"
            )
        
        workspace_path = context.get("workspace_path")
        if not workspace_path:
            return ToolResult(
                success=False,
                error="workspace_path not provided in context"
            )
        
        try:
            repo_path = Path(workspace_path)
            
            # Check if method file already exists
            method_file = repo_path / ".benedict.method.yaml"
            if method_file.exists():
                return ToolResult(
                    success=False,
                    error="Method file already exists. Use update tools to modify it."
                )
            
            # Create default method file structure
            method_data = {
                "method": {
                    "pc": {
                        "phase": "conception",
                        "iteration": 1,
                        "step": "define",
                    },
                    "concern_definitions": {
                        "scope": {
                            "description": "the boundary of what the project does and does not do",
                            "states": ["fluid", "narrowing", "locked", "reconsidering"],
                            "rules": [
                                "scope must be explicitly stated in every project",
                                "scope changes are only permitted during conception and review phases",
                                "during sprint, scope is locked — new ideas go to BACKLOG.md",
                                "scope must be defined in terms of what is IN and what is OUT",
                            ],
                        },
                        "documentation": {
                            "description": "all written artifacts that make the project understandable, usable, and maintainable",
                            "states": ["not_started", "drafting", "in_progress", "complete", "stale"],
                            "rules": [
                                "only documented software should be delivered",
                                "documentation gates development — no feature ships without docs",
                                "each project must have at minimum WHY.md, README.md, ROADMAP.md",
                                "documentation must be reviewed for staleness at every review phase",
                                "documentation is a first-class deliverable, not an afterthought",
                            ],
                        },
                        "development": {
                            "description": "all code, configuration, and infrastructure work",
                            "states": ["blocked", "not_started", "prototyping", "active", "stabilising", "complete"],
                            "rules": [
                                "development is not allowed in conception phase",
                                "development in design phase is limited to throwaway prototypes",
                                "development in sprint phase must follow the roadmap — no unplanned work",
                                "development must produce deployable output at the end of each sprint",
                                "development is gated by documentation — build it, then document it, then communicate it",
                            ],
                        },
                        "communication": {
                            "description": "all external-facing announcements, posts, updates, and promotion of the project",
                            "states": ["not_applicable", "pending", "drafting", "published"],
                            "rules": [
                                "every delivered and documented feature must be communicated",
                                "communication is the final step in the sprint loop — it cannot be skipped",
                                "communication is not marketing fluff — it is a factual account of what changed and why",
                                "no communication without documentation — you cannot announce what is not written down",
                                "communication debt is project debt — uncommunicated features are invisible features",
                            ],
                        },
                        "operations": {
                            "description": "all work related to deploying, running, monitoring, and maintaining the project",
                            "states": ["not_applicable", "not_started", "defining", "active", "reviewing"],
                            "rules": [
                                "operations strategy must be defined during design phase",
                                "the project must be in a deployable state at the end of every sprint",
                                "operational health must be assessed during every review phase",
                                "operations includes CI/CD, monitoring, hosting, incident response",
                                "if the project cannot be operated, it cannot be delivered",
                            ],
                        },
                        "feedback": {
                            "description": "all signals — internal or external — about how the project is performing against its goals",
                            "states": ["not_applicable", "not_started", "collecting", "synthesising", "actioned"],
                            "rules": [
                                "feedback must be actively sought, not passively received",
                                "feedback is collected during sprint, synthesised during review",
                                "feedback that challenges scope must be logged and deferred to review phase",
                                "feedback drives the decision at the end of review — next sprint, harden, expand, or kill",
                                "absence of feedback is itself feedback — it means no one is using it",
                            ],
                        },
                    },
                    "concerns": {
                        "scope": "fluid",
                        "documentation": "not_started",
                        "development": "not_started",
                        "communication": "not_applicable",
                        "operations": "not_applicable",
                        "feedback": "not_started",
                    },
                    "sequence": {
                        "conception": {
                            "status": "active",
                            "iteration": 1,
                            "loop": "define → challenge → refine",
                            "exit": "motivation, problem, and scope are stable enough to design against",
                            "addresses": ["motivation", "problem_definition", "scope"],
                            "artifacts": ["WHY.md", "README.md"],
                        },
                        "design": {
                            "status": "pending",
                            "iteration": 0,
                            "loop": "sketch → evaluate → revise",
                            "exit": "technical design and roadmap are concrete enough to build against",
                            "addresses": ["technical_design", "roadmap"],
                            "artifacts": ["SYSTEM_SPEC.md", "ROADMAP.md"],
                        },
                        "sprint": {
                            "status": "pending",
                            "iteration": 0,
                            "loop": "build → document → communicate",
                            "exit": "feature is delivered, documented, and communicated",
                            "addresses": ["development", "documentation", "communication"],
                            "artifacts": ["CHANGELOG.md"],
                        },
                        "review": {
                            "status": "pending",
                            "iteration": 0,
                            "loop": "measure → assess → decide",
                            "exit": "decision made — next sprint, hardening, or expansion",
                            "addresses": ["feedback", "operations"],
                            "artifacts": [],
                        },
                    },
                }
            }
            
            # Write the method file
            self.method_writer.write_method(repo_path, method_data)
            
            return ToolResult(
                success=True,
                message=(
                    "✅ Method file created!\n\n"
                    "I've created a `.benedict.method.yaml` file for the repository.\n\n"
                    "*Initial setup:*\n"
                    "• Phase: `conception` (iteration 1, step: define)\n"
                    "• All concern definitions included\n"
                    "• Sequence phases defined (conception, design, sprint, review)\n\n"
                    "You can now use update tools to modify the method file."
                )
            )
        except Exception as e:
            logger.error(f"Error creating method file: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"Error creating method file: {str(e)}"
            )


class UpdateSequencePhaseTool(Tool):
    """Tool for updating sequence phase status."""
    
    def __init__(self, method_reader=None, method_writer=None):
        """Initialize tool.
        
        Args:
            method_reader: MethodReader instance
            method_writer: MethodWriter instance
        """
        super().__init__(
            name="update_sequence_phase",
            description="Update a sequence phase's status and iteration. Sequence phases are the main stages of the methodology (conception, design, sprint, review)."
        )
        self.method_reader = method_reader
        self.method_writer = method_writer
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "description": "Phase name (e.g., conception, design, sprint, review)"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["complete", "active", "pending"],
                        "description": "Status of the phase"
                    },
                    "iteration": {
                        "type": "integer",
                        "description": "Iteration number for this phase"
                    }
                },
                "required": ["phase", "status"]
            }
        }
    
    def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute tool."""
        if not self.method_writer or not context:
            return ToolResult(
                success=False,
                error="Method writer or context not available"
            )
        
        workspace_path = context.get("workspace_path")
        if not workspace_path:
            return ToolResult(
                success=False,
                error="workspace_path not provided in context"
            )
        
        phase = arguments.get("phase")
        status = arguments.get("status")
        iteration = arguments.get("iteration")
        
        if not phase or not status:
            return ToolResult(
                success=False,
                error="Missing required parameters: phase, status"
            )
        
        try:
            self.method_writer.update_sequence_phase_status(
                Path(workspace_path),
                phase,
                status,
                iteration=iteration
            )
            
            result = f"Updated sequence phase '{phase}' to status '{status}'"
            if iteration:
                result += f", iteration {iteration}"
            
            return ToolResult(
                success=True,
                message=result
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )
