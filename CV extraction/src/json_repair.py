"""
JSON Repair & Validation
Fix common JSON errors and validate against schema
"""

import json
import re
from typing import Any, Dict, Optional


class JSONRepair:
    """Repair malformed JSON from LLM responses"""
    
    @staticmethod
    def fix_newlines_in_strings(text: str) -> str:
        """
        Fix unescaped newlines inside JSON strings
        Common issue from LLM responses
        """
        # Strategy: Find all quoted strings with unescaped newlines
        # and escape them
        
        # First, extract JSON to understand structure
        in_string = False
        in_escape = False
        result = []
        
        for i, char in enumerate(text):
            if in_escape:
                result.append(char)
                in_escape = False
                continue
            
            if char == '\\':
                result.append(char)
                in_escape = True
                continue
            
            if char == '"' and not in_escape:
                in_string = not in_string
                result.append(char)
                continue
            
            if char == '\n' and in_string:
                result.append('\\n')
                continue
            
            if char == '\r' and in_string:
                result.append('\\r')
                continue
            
            result.append(char)
        
        return ''.join(result)
    
    @staticmethod
    def fix_trailing_commas(text: str) -> str:
        """Remove trailing commas in arrays/objects"""
        # Remove comma before ] or }
        text = re.sub(r',\s*([}\]])', r'\1', text)
        return text
    
    @staticmethod
    def fix_missing_quotes(text: str) -> str:
        """
        Fix missing quotes around keys/values
        (Limited fix, only for obvious cases)
        """
        # Fix: {key: value} -> {"key": value}
        # Only for simple identifiers
        pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*):'
        text = re.sub(pattern, r'{"\1":', text)
        
        return text
    
    @staticmethod
    def fix_single_quotes(text: str) -> str:
        """Replace single quotes with double quotes"""
        # Be careful not to replace apostrophes
        # Simple approach: replace ' at start/end of values
        text = re.sub(r":\s*'([^']*)'", r': "\1"', text)
        text = re.sub(r"'\s*,", '",', text)
        return text
    
    @staticmethod
    def extract_json_block(text: str) -> str:
        """Extract JSON from text that might have markdown wrapper"""
        # Try to find JSON code block
        if "```json" in text:
            match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
            if match:
                return match.group(1)
        
        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                return parts[1]
        
        # Try to extract {...} or [...]
        if "{" in text:
            start = text.index("{")
            # Find matching }
            count = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    count += 1
                elif text[i] == "}":
                    count -= 1
                    if count == 0:
                        return text[start:i+1]
        
        if "[" in text:
            start = text.index("[")
            count = 0
            for i in range(start, len(text)):
                if text[i] == "[":
                    count += 1
                elif text[i] == "]":
                    count -= 1
                    if count == 0:
                        return text[start:i+1]
        
        return text
    
    @staticmethod
    def repair(text: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to repair and parse JSON
        """
        if not text or not isinstance(text, str):
            return None
        
        # Step 1: Extract JSON if wrapped
        text = JSONRepair.extract_json_block(text)
        
        # Step 2: Fix newlines
        text = JSONRepair.fix_newlines_in_strings(text)
        
        # Step 3: Fix trailing commas
        text = JSONRepair.fix_trailing_commas(text)
        
        # Step 4: Fix single quotes
        text = JSONRepair.fix_single_quotes(text)
        
        # Step 5: Try to parse
        try:
            data = json.loads(text)
            return data
        except json.JSONDecodeError as e:
            print(f"JSON repair failed: {e}")
            print(f"Attempted text: {text[:200]}...")
            return None
    
    @staticmethod
    def repair_and_validate(text: str, schema_validator=None) -> Optional[Dict[str, Any]]:
        """
        Repair JSON and optionally validate against Pydantic schema
        """
        data = JSONRepair.repair(text)
        
        if data is None:
            return None
        
        # If schema provided, validate
        if schema_validator:
            try:
                validated = schema_validator.model_validate(data)
                return validated.model_dump()
            except Exception as e:
                print(f"Schema validation error: {e}")
                return data  # Return unvalidated but valid JSON
        
        return data


class JSONValidator:
    """Validate JSON against expected structure"""
    
    @staticmethod
    def is_valid_json(text: str) -> bool:
        """Check if text is valid JSON"""
        try:
            json.loads(text)
            return True
        except:
            return False
    
    @staticmethod
    def ensure_ascii_false_dump(data: Dict[str, Any]) -> str:
        """
        Dump dict to JSON string with Vietnamese support
        """
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    @staticmethod
    def safe_write(filepath: str, data: Dict[str, Any]) -> bool:
        """
        Safely write data to JSON file
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json_str = JSONValidator.ensure_ascii_false_dump(data)
                f.write(json_str)
            return True
        except Exception as e:
            print(f"Error writing JSON to {filepath}: {e}")
            return False


# Test
if __name__ == '__main__':
    # Test broken JSON
    broken_json = '''
    {
        "name": "Ha Duyen Hai Anh
        multiple lines here",
        "email": "test@gmail.com",
        "skills": ["Python", "Java",]
    }
    '''
    
    result = JSONRepair.repair(broken_json)
    print("Repaired:", result)
