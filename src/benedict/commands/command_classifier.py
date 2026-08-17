"""Command Classifier

Classifies user input into command intents using declarative command definitions.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from .command_definitions import (
    CommandDefinition, 
    CommandType, 
    CommandIntent, 
    COMMAND_DEFINITIONS
)

logger = logging.getLogger(__name__)


class CommandClassifier:
    """Classifies user input into command intents."""
    
    def __init__(self, command_definitions: Optional[List[CommandDefinition]] = None):
        """Initialize command classifier.
        
        Args:
            command_definitions: Optional list of command definitions.
                               If None, uses default COMMAND_DEFINITIONS.
        """
        self.command_definitions = command_definitions or COMMAND_DEFINITIONS
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        for cmd_def in self.command_definitions:
            cmd_def.compiled_patterns = []
            for pattern in cmd_def.patterns:
                try:
                    cmd_def.compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{pattern}' for command {cmd_def.name}: {e}")
                    # Fallback to simple string matching
                    cmd_def.compiled_patterns.append(pattern)
    
    def classify(self, text: str) -> Optional[CommandIntent]:
        """Classify user input into a command intent.
        
        Args:
            text: User input text
            
        Returns:
            CommandIntent if a command is detected, None otherwise (treat as query)
        """
        text_lower = text.lower().strip()
        
        # Try each command definition
        best_match: Optional[CommandIntent] = None
        best_confidence = 0.0
        
        for cmd_def in self.command_definitions:
            intent = self._match_command(cmd_def, text_lower, text)
            if intent and intent.confidence > best_confidence:
                best_match = intent
                best_confidence = intent.confidence
        
        # Only return if confidence is above threshold
        if best_match and best_confidence >= 0.5:
            logger.debug(f"Classified '{text}' as {best_match.command_type.value} (confidence: {best_confidence:.2f})")
            return best_match
        
        # No command detected - treat as query
        logger.debug(f"No command detected for '{text}', treating as query")
        return None
    
    def _match_command(
        self, 
        cmd_def: CommandDefinition, 
        text_lower: str, 
        text_original: str
    ) -> Optional[CommandIntent]:
        """Match text against a command definition.
        
        Args:
            cmd_def: Command definition to match against
            text_lower: Lowercase version of user text
            text_original: Original user text (for parameter extraction)
            
        Returns:
            CommandIntent if matched, None otherwise
        """
        parameters = {}
        matched_pattern = None
        
        # Try each pattern
        for i, pattern in enumerate(cmd_def.compiled_patterns):
            if isinstance(pattern, re.Pattern):
                # Regex pattern
                match = pattern.search(text_lower)
                if match:
                    matched_pattern = cmd_def.patterns[i]
                    # Extract parameters from groups
                    groups = match.groups()
                    if groups:
                        # Map groups to parameters based on command type
                        parameters.update(self._extract_parameters(cmd_def, groups, text_original))
                    break
            else:
                # Simple string pattern (fallback)
                if pattern.lower() in text_lower:
                    matched_pattern = pattern
                    break
        
        if not matched_pattern:
            return None
        
        # Calculate confidence based on pattern match quality
        confidence = self._calculate_confidence(cmd_def, text_lower, matched_pattern)
        
        return CommandIntent(
            command_type=cmd_def.command_type,
            confidence=confidence,
            parameters=parameters,
            matched_pattern=matched_pattern,
        )
    
    def _extract_parameters(
        self, 
        cmd_def: CommandDefinition, 
        groups: tuple, 
        text_original: str
    ) -> Dict[str, Any]:
        """Extract parameters from matched groups.
        
        Args:
            cmd_def: Command definition
            groups: Matched regex groups
            text_original: Original text for additional extraction
            
        Returns:
            Dictionary of extracted parameters
        """
        params = {}
        
        # Map groups to parameter names based on command type
        if cmd_def.command_type == CommandType.ONBOARD:
            if groups:
                params["repo"] = groups[0].strip()
        
        elif cmd_def.command_type == CommandType.READ_FILE:
            if groups:
                file_path = groups[0].strip()
                # Clean up file path
                file_path = file_path.rstrip('.,!?;:')
                params["file_path"] = file_path
        
        elif cmd_def.command_type == CommandType.LIST_FILES:
            if groups:
                params["path"] = groups[0].strip()
        
        return params
    
    def _calculate_confidence(
        self, 
        cmd_def: CommandDefinition, 
        text_lower: str, 
        matched_pattern: str
    ) -> float:
        """Calculate confidence score for a match.
        
        Args:
            cmd_def: Command definition
            text_lower: Lowercase user text
            matched_pattern: Pattern that matched
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.7  # Base confidence for pattern match
        
        # Boost confidence if exact command name is present
        if cmd_def.name.lower() in text_lower:
            confidence += 0.2
        
        # Reduce confidence if it's too generic
        if len(text_lower.split()) < 2:
            confidence -= 0.2
        
        return min(1.0, max(0.0, confidence))
    
    def get_available_commands(self) -> List[CommandDefinition]:
        """Get list of all available command definitions.
        
        Returns:
            List of command definitions
        """
        return self.command_definitions.copy()
