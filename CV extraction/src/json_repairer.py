"""
JSON Repairer - Fix common JSON errors from LLM outputs
Handles: unescaped newlines, missing quotes, trailing commas, etc.
"""

import json
import re
from typing import Optional, Dict, Any, Union


class JSONRepairer:
    """Repair malformed JSON from LLM outputs"""
    
    @staticmethod
    def repair(text: str, max_attempts: int = 3) -> Optional[Dict[str, Any]]:
        """
        Attempt to repair and parse JSON
        
        Args:
            text: JSON text (possibly malformed)
            max_attempts: Number of repair attempts
        
        Returns:
            Parsed JSON dict or None
        """
        # Try to parse as-is first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Apply repairs
        for attempt in range(max_attempts):
            try:
                repaired = JSONRepairer._apply_repairs(text, attempt)
                return json.loads(repaired)
            except json.JSONDecodeError as e:
                if attempt == max_attempts - 1:
                    raise
        
        return None
    
    @staticmethod
    def _apply_repairs(text: str, pass_num: int = 0) -> str:
        """
        Apply progressive repairs to malformed JSON
        
        Args:
            text: JSON text
            pass_num: Which repair pass (0=aggressive, 1=conservative)
        
        Returns:
            Repaired JSON text
        """
        # Remove markdown code blocks
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        if pass_num == 0:
            # Aggressive repairs
            
            # Fix unescaped newlines in strings
            # Pattern: "text\nmore text" -> "text\\nmore text"
            # But don't break valid JSON structure
            text = JSONRepairer._fix_unescaped_newlines(text)
            
            # Fix trailing commas before ] or }
            text = re.sub(r',(\s*[}\]])', r'\1', text)
            
            # Fix missing commas between object properties
            text = JSONRepairer._fix_missing_commas(text)
            
            # Fix single quotes to double quotes (in values)
            text = JSONRepairer._fix_single_quotes(text)
            
            # Fix unquoted strings in certain contexts
            text = JSONRepairer._fix_unquoted_values(text)
        
        elif pass_num == 1:
            # Conservative repairs for when aggressive didn't work
            
            # Try to find and fix common patterns
            text = JSONRepairer._fix_common_patterns(text)
        
        return text
    
    @staticmethod
    def _fix_unescaped_newlines(text: str) -> str:
        """
        Fix unescaped newlines within JSON strings
        
        Challenges:
        - Don't escape newlines that are part of JSON structure
        - Only escape newlines within quoted strings
        """
        result = []
        in_string = False
        escape_next = False
        i = 0
        
        while i < len(text):
            char = text[i]
            
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                escape_next = True
                result.append(char)
                i += 1
                continue
            
            if char == '"':
                in_string = not in_string
                result.append(char)
                i += 1
                continue
            
            # If in string and we find unescaped newline
            if in_string and char == '\n':
                result.append('\\n')
                i += 1
                continue
            
            result.append(char)
            i += 1
        
        return ''.join(result)
    
    @staticmethod
    def _fix_missing_commas(text: str) -> str:
        """
        Fix missing commas between JSON properties
        
        Pattern: "key": value"key": value -> "key": value, "key": value
        """
        # Simple approach: add comma before " if preceded by "
        pattern = r'([\]}\'])\s*"'
        replacement = r'\1, "'
        return re.sub(pattern, replacement, text)
    
    @staticmethod
    def _fix_single_quotes(text: str) -> str:
        """
        Convert single quotes to double quotes in values
        But be careful with apostrophes in words
        """
        # This is tricky - only convert if it looks like a quoted value
        # Pattern: 'value' not in contractions
        
        # Find all single-quoted strings
        pattern = r"'([^']*?)'"
        
        def replace_quotes(match):
            content = match.group(1)
            # Don't convert if contains apostrophe (likely contraction)
            if "'" in content or content.count("'") > 0:
                return match.group(0)
            # Convert to double quotes
            return '"' + content + '"'
        
        return re.sub(pattern, replace_quotes, text)
    
    @staticmethod
    def _fix_unquoted_values(text: str) -> str:
        """
        Fix common unquoted values in JSON
        Patterns: : True -> : "True", : None -> : null
        """
        # Python True/False -> JSON true/false
        text = re.sub(r'\bTrue\b', 'true', text)
        text = re.sub(r'\bFalse\b', 'false', text)
        
        # Python None -> JSON null
        text = re.sub(r'\bNone\b', 'null', text)
        
        return text
    
    @staticmethod
    def _fix_common_patterns(text: str) -> str:
        """
        Fix patterns that aggressive repairs missed
        """
        # If starts with { but missing closing }
        if text.count('{') > text.count('}'):
            text += '}' * (text.count('{') - text.count('}'))
        
        # If starts with [ but missing closing ]
        if text.count('[') > text.count(']'):
            text += ']' * (text.count('[') - text.count(']'))
        
        return text


def repair_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to repair JSON
    
    Args:
        text: JSON text (possibly malformed)
    
    Returns:
        Parsed JSON or None
    """
    try:
        return JSONRepairer.repair(text)
    except Exception as e:
        print(f"Failed to repair JSON: {e}")
        return None


if __name__ == "__main__":
    # Test cases
    test_cases = [
        # Valid JSON
        '{"name": "John", "age": 30}',
        
        # Unescaped newlines
        '{"name": "John", "description": "Line 1\nLine 2"}',
        
        # Trailing comma
        '{"name": "John", "age": 30,}',
        
        # Single quotes
        "{'name': 'John', 'age': 30}",
        
        # Python True/None
        '{"name": "John", "active": True, "email": None}',
        
        # Markdown wrapper
        '```json\n{"name": "John", "age": 30}\n```',
    ]
    
    for i, test in enumerate(test_cases):
        print(f"\nTest {i+1}:")
        print(f"Input: {test[:50]}...")
        result = repair_json(test)
        print(f"Result: {result}")
