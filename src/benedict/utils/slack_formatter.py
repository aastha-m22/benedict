"""Slack Message Formatting Utilities

Converts markdown to Slack mrkdwn format and formats messages using Block Kit.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Slack API limits
MAX_MESSAGE_LENGTH = 4000
MAX_BLOCKS_PER_MESSAGE = 50
MAX_TEXT_IN_BLOCK = 3000
CHUNK_THRESHOLD = 2000  # Use Block Kit for messages longer than this


class SlackFormatter:
    """Converts markdown to Slack mrkdwn format."""

    # Slack API limits (expose module constants as class attributes)
    MAX_MESSAGE_LENGTH = 4000

    @staticmethod
    def markdown_to_mrkdwn(text: str) -> str:
        """Convert markdown to Slack mrkdwn format.

        Args:
            text: Markdown text

        Returns:
            Slack mrkdwn formatted text
        """
        if not text:
            return ""

        # First, protect code blocks from conversion
        code_blocks = []
        code_block_pattern = r"```[\s\S]*?```"

        def replace_code_block(match):
            code_blocks.append(match.group(0))
            return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

        # Temporarily replace code blocks
        text_with_placeholders = re.sub(code_block_pattern, replace_code_block, text)

        # Protect inline code
        inline_code_pattern = r"`([^`]+)`"
        inline_codes = []

        def replace_inline_code(match):
            inline_codes.append(match.group(0))
            return f"__INLINE_CODE_{len(inline_codes) - 1}__"

        text_with_placeholders = re.sub(
            inline_code_pattern, replace_inline_code, text_with_placeholders
        )

        # Convert headings to bold (process in reverse order to avoid double conversion)
        text_with_placeholders = re.sub(
            r"^### (.+)$", r"*\1*", text_with_placeholders, flags=re.MULTILINE
        )
        text_with_placeholders = re.sub(
            r"^## (.+)$", r"*\1*", text_with_placeholders, flags=re.MULTILINE
        )
        text_with_placeholders = re.sub(
            r"^# (.+)$", r"*\1*", text_with_placeholders, flags=re.MULTILINE
        )

        # Convert **bold** to *bold* (Slack uses single asterisk)
        text_with_placeholders = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text_with_placeholders)

        # Convert *italic* to _italic_ (but avoid converting already converted bold)
        # Only convert single asterisks that aren't part of bold
        text_with_placeholders = re.sub(
            r"(?<!\*)\*([^*]+?)\*(?!\*)", r"_\1_", text_with_placeholders
        )

        # Convert links: [text](url) to <url|text>
        text_with_placeholders = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text_with_placeholders
        )

        # Convert strikethrough: ~~text~~ to ~text~
        text_with_placeholders = re.sub(r"~~(.+?)~~", r"~\1~", text_with_placeholders)

        # Restore inline code
        for i, code in enumerate(inline_codes):
            text_with_placeholders = text_with_placeholders.replace(f"__INLINE_CODE_{i}__", code)

        # Restore code blocks
        for i, code_block in enumerate(code_blocks):
            text_with_placeholders = text_with_placeholders.replace(
                f"__CODE_BLOCK_{i}__", code_block
            )

        return text_with_placeholders

    @staticmethod
    def extract_code_blocks(text: str) -> List[Tuple[str, Optional[str], str]]:
        """Extract code blocks from text.

        Args:
            text: Text containing code blocks

        Returns:
            List of tuples: (full_match, language, code_content)
        """
        code_blocks = []
        pattern = r"```(\w+)?\n?([\s\S]*?)```"

        for match in re.finditer(pattern, text):
            language = match.group(1) if match.group(1) else None
            code_content = match.group(2).strip()
            code_blocks.append((match.group(0), language, code_content))

        return code_blocks

    @staticmethod
    def should_use_block_kit(text: str) -> bool:
        """Determine if message should use Block Kit formatting.

        Args:
            text: Message text

        Returns:
            True if Block Kit should be used
        """
        # Use Block Kit if:
        # - Message is longer than threshold
        # - Contains code blocks
        # - Contains multiple sections (headings)
        if len(text) > CHUNK_THRESHOLD:
            return True

        if re.search(r"```[\s\S]*?```", text):
            return True

        if len(re.findall(r"^#{1,3}\s+", text, re.MULTILINE)) > 1:
            return True

        return False

    @staticmethod
    def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH - 200) -> List[str]:
        """Split long message into chunks.

        Args:
            text: Message text to split
            max_length: Maximum length per chunk (default: leave buffer for Slack)

        Returns:
            List of message chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by paragraphs first
        paragraphs = text.split("\n\n")

        for paragraph in paragraphs:
            # If adding this paragraph would exceed limit, start new chunk
            if current_chunk and len(current_chunk) + len(paragraph) + 2 > max_length:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph

        # Add remaining chunk
        if current_chunk:
            chunks.append(current_chunk.strip())

        # If any chunk is still too long, split by lines
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= max_length:
                final_chunks.append(chunk)
            else:
                # Split by lines, preserving code blocks
                lines = chunk.split("\n")
                current_subchunk = ""

                for line in lines:
                    if current_subchunk and len(current_subchunk) + len(line) + 1 > max_length:
                        final_chunks.append(current_subchunk.strip())
                        current_subchunk = line
                    else:
                        if current_subchunk:
                            current_subchunk += "\n" + line
                        else:
                            current_subchunk = line

                if current_subchunk:
                    final_chunks.append(current_subchunk.strip())

        return final_chunks


class BlockKitFormatter:
    """Formats messages using Slack Block Kit."""

    @staticmethod
    def create_section(text: str, fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Create section block(s). Splits into multiple blocks if text exceeds limit.

        Args:
            text: Section text (mrkdwn)
            fields: Optional list of field texts for two-column layout

        Returns:
            List of section block dictionaries (may be multiple if text is long)
        """
        blocks: List[Dict[str, Any]] = []
        
        if fields:
            # Handle fields - split if any field is too long
            processed_fields = []
            for field in fields[:10]:  # Max 10 fields
                if len(field) > MAX_TEXT_IN_BLOCK:
                    # Split long field into multiple fields
                    chunks = SlackFormatter.split_message(field, max_length=MAX_TEXT_IN_BLOCK - 50)
                    processed_fields.extend(chunks)
                else:
                    processed_fields.append(field)
            
            # Group fields into pairs for two-column layout
            for i in range(0, len(processed_fields), 2):
                field_pair = processed_fields[i : i + 2]
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text[:MAX_TEXT_IN_BLOCK] if text else ""},
                    "fields": [
                        {"type": "mrkdwn", "text": field[:MAX_TEXT_IN_BLOCK]}
                        for field in field_pair
                    ]
                })
        else:
            # Handle text - split if too long
            if len(text) <= MAX_TEXT_IN_BLOCK:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text}
                })
            else:
                # Split text into multiple sections
                chunks = SlackFormatter.split_message(text, max_length=MAX_TEXT_IN_BLOCK - 50)
                for i, chunk in enumerate(chunks):
                    chunk_text = chunk
                    if i < len(chunks) - 1:
                        chunk_text += "\n_...continued..._"
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": chunk_text[:MAX_TEXT_IN_BLOCK]}
                    })

        return blocks

    @staticmethod
    def create_divider() -> Dict[str, Any]:
        """Create a divider block.

        Returns:
            Divider block dictionary
        """
        return {"type": "divider"}

    @staticmethod
    def create_header(text: str) -> Dict[str, Any]:
        """Create a header block.

        Args:
            text: Header text (plain text, max 150 chars)

        Returns:
            Header block dictionary
        """
        return {"type": "header", "text": {"type": "plain_text", "text": text[:150]}}  # Slack limit

    @staticmethod
    def create_code_block(code: str, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Create code block section(s). Splits into multiple blocks if code is too long.

        Note: Slack doesn't have a native code block type in Block Kit.
        We use a section block with pre-formatted text.

        Args:
            code: Code content
            language: Optional language for syntax highlighting hint

        Returns:
            List of section blocks with code formatted as mrkdwn (may be multiple)
        """
        blocks: List[Dict[str, Any]] = []
        
        # Calculate overhead for code block formatting
        language_hint = f"{language}\n" if language else ""
        overhead = len(f"```{language_hint}```") + 20  # Buffer for continuation markers
        max_code_length = MAX_TEXT_IN_BLOCK - overhead
        
        if len(code) <= max_code_length:
            # Single code block
            code_text = f"```{language_hint}{code}```"
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": code_text[:MAX_TEXT_IN_BLOCK]},
            })
        else:
            # Split code into multiple blocks
            # Try to split at line boundaries
            lines = code.split("\n")
            current_chunk = []
            current_length = 0
            
            for line in lines:
                line_length = len(line) + 1  # +1 for newline
                if current_length + line_length > max_code_length and current_chunk:
                    # Create block with current chunk
                    chunk_code = "\n".join(current_chunk)
                    code_text = f"```{language_hint}{chunk_code}\n...```"
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": code_text[:MAX_TEXT_IN_BLOCK]},
                    })
                    # Add continuation header
                    blocks.append(BlockKitFormatter.create_context(f"_Code block continued ({language or 'code'})..._"))
                    current_chunk = [line]
                    current_length = line_length
                else:
                    current_chunk.append(line)
                    current_length += line_length
            
            # Add final chunk
            if current_chunk:
                chunk_code = "\n".join(current_chunk)
                code_text = f"```{language_hint}{chunk_code}```"
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": code_text[:MAX_TEXT_IN_BLOCK]},
                })
        
        return blocks

    @staticmethod
    def create_context(text: str) -> Dict[str, Any]:
        """Create a context block for metadata.

        Args:
            text: Context text (mrkdwn)

        Returns:
            Context block dictionary
        """
        return {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": text[:MAX_TEXT_IN_BLOCK]}],
        }

    @staticmethod
    def format_message(
        text: str, use_block_kit: Optional[bool] = None, include_code_blocks: bool = True
    ) -> Dict[str, Any]:
        """Format a message using Block Kit.

        Args:
            text: Message text (may contain markdown)
            use_block_kit: Force Block Kit usage (auto-detect if None)
            include_code_blocks: Whether to extract and format code blocks separately

        Returns:
            Dictionary with 'text' (for simple) or 'blocks' (for Block Kit)
        """
        # Convert markdown to mrkdwn
        formatted_text = SlackFormatter.markdown_to_mrkdwn(text)

        # Auto-detect if Block Kit should be used
        if use_block_kit is None:
            use_block_kit = SlackFormatter.should_use_block_kit(text)

        # Simple text message
        if not use_block_kit:
            if len(formatted_text) > MAX_MESSAGE_LENGTH:
                # Truncate with indicator
                truncated = formatted_text[:MAX_MESSAGE_LENGTH - 50]
                return {"text": f"{truncated}\n\n_...message truncated (too long)_"}
            return {"text": formatted_text}

        # Block Kit message
        blocks: List[Dict[str, Any]] = []

        # Extract code blocks if requested
        if include_code_blocks:
            code_blocks = SlackFormatter.extract_code_blocks(text)
            remaining_text = text

            # Remove code blocks from remaining text
            for full_match, _, _ in code_blocks:
                remaining_text = remaining_text.replace(full_match, "", 1)

            # Process remaining text
            remaining_formatted = SlackFormatter.markdown_to_mrkdwn(remaining_text.strip())

            # Split by headings to create sections
            sections = re.split(r"\n(?=#{1,3}\s+)", remaining_formatted)

            for section in sections:
                section = section.strip()
                if not section:
                    continue

                # Check if section starts with a heading
                heading_match = re.match(r"^\*{2}(.+?)\*{2}", section)
                if heading_match:
                    # Add header block
                    header_text = heading_match.group(1).strip()
                    blocks.append(BlockKitFormatter.create_header(header_text))
                    # Remove heading from section text
                    section = re.sub(r"^\*{2}.+?\*{2}\s*\n?", "", section)

                # Add section content (may return multiple blocks)
                if section:
                    section_blocks = BlockKitFormatter.create_section(section)
                    blocks.extend(section_blocks)

                # Add divider between sections (except after last)
                if section != sections[-1]:
                    blocks.append(BlockKitFormatter.create_divider())

            # Add code blocks at the end
            for full_match, language, code_content in code_blocks:
                if blocks:  # Add divider before code block if there are other blocks
                    blocks.append(BlockKitFormatter.create_divider())
                code_blocks_list = BlockKitFormatter.create_code_block(code_content, language)
                blocks.extend(code_blocks_list)
        else:
            # Simple Block Kit: just format the text as sections
            # Split by double newlines (paragraphs)
            paragraphs = formatted_text.split("\n\n")

            for i, paragraph in enumerate(paragraphs):
                paragraph = paragraph.strip()
                if not paragraph:
                    continue

                paragraph_blocks = BlockKitFormatter.create_section(paragraph)
                blocks.extend(paragraph_blocks)

                # Add divider between paragraphs (except after last)
                if i < len(paragraphs) - 1:
                    blocks.append(BlockKitFormatter.create_divider())

        # Enforce block limit
        if len(blocks) > MAX_BLOCKS_PER_MESSAGE:
            blocks = blocks[:MAX_BLOCKS_PER_MESSAGE]
            blocks.append(BlockKitFormatter.create_context("_Message truncated..._"))

        return {"blocks": blocks}

    @staticmethod
    def format_status_message(
        title: str, fields: Dict[str, str], emoji: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format a status message with structured fields.

        Args:
            title: Message title
            fields: Dictionary of field_name -> field_value
            emoji: Optional emoji prefix

        Returns:
            Block Kit message dictionary
        """
        blocks: List[Dict[str, Any]] = []

        # Header
        header_text = f"{emoji} {title}" if emoji else title
        blocks.append(BlockKitFormatter.create_header(header_text))
        blocks.append(BlockKitFormatter.create_divider())

        # Fields section
        field_texts = []
        for key, value in fields.items():
            field_texts.append(f"*{key}:*\n{value}")

        # Split fields into groups of 2 for two-column layout
        for i in range(0, len(field_texts), 2):
            field_pair = field_texts[i : i + 2]
            section_blocks = BlockKitFormatter.create_section(
                text="", fields=field_pair  # Empty text, using fields only
            )
            blocks.extend(section_blocks)

        return {"blocks": blocks}

    @staticmethod
    def format_error_message(
        error_type: str, message: str, next_steps: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Format an error message.

        Args:
            error_type: Type of error (e.g., "Validation Error")
            message: Error message
            next_steps: Optional list of actionable next steps

        Returns:
            Block Kit message dictionary
        """
        blocks: List[Dict[str, Any]] = []

        # Error header
        blocks.append(BlockKitFormatter.create_header(f"⚠️ {error_type}"))
        blocks.append(BlockKitFormatter.create_divider())

        # Error message
        message_blocks = BlockKitFormatter.create_section(message)
        blocks.extend(message_blocks)

        # Next steps if provided
        if next_steps:
            blocks.append(BlockKitFormatter.create_divider())
            steps_text = "\n".join([f"• {step}" for step in next_steps])
            steps_blocks = BlockKitFormatter.create_section(f"*Next steps:*\n{steps_text}")
            blocks.extend(steps_blocks)

        return {"blocks": blocks}
