"""
Claude LLM Client - Anthropic API wrapper for structured CV extraction
"""

import json
import os
from typing import Dict, Optional, Any
import anthropic


class ClaudeLLMClient:
    """Wrapper for Anthropic Claude API"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-opus-4-8"):
        """
        Initialize Claude client
        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env)
            model: Model to use (default: claude-opus-4-8)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model
    
    def extract_personal_info(self, text: str) -> Dict[str, Any]:
        """Extract personal information from CV header"""
        prompt = f"""Extract personal information from this CV header text.

Return ONLY valid JSON, no explanation.
If information is missing, use null.

Schema:
{{
  "name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "location": "string or null",
  "linkedin": "string or null",
  "github": "string or null"
}}

Text:
{text}
"""
        return self._call_llm_json(prompt)
    
    def extract_education(self, text: str) -> Dict[str, Any]:
        """Extract education section"""
        prompt = f"""Extract education entries from this CV section.

Return ONLY valid JSON, no explanation.
For each education entry, extract all available fields.

Schema:
{{
  "entries": [
    {{
      "school": "university/school name or null",
      "degree": "degree type or null",
      "major": "field of study or null",
      "location": "city/country or null",
      "gpa": "GPA value like 3.47/4.0 or null",
      "start_date": "preserve original format or null",
      "end_date": "preserve original format or null",
      "currently_studying": true/false/null,
      "description": ["bullet points as array"]
    }}
  ]
}}

Text:
{text}
"""
        result = self._call_llm_json(prompt)
        return result.get("entries", []) if result else []
    
    def extract_experience(self, text: str) -> Dict[str, Any]:
        """Extract experience section"""
        prompt = f"""Extract work experience entries from this CV section.

Return ONLY valid JSON, no explanation.

Schema:
{{
  "entries": [
    {{
      "company": "company name or null",
      "position": "job title or null",
      "start_date": "preserve original format or null",
      "end_date": "preserve original format or null",
      "currently_working": true/false/null,
      "description": ["bullet points"],
      "location": "work location or null"
    }}
  ]
}}

Text:
{text}
"""
        result = self._call_llm_json(prompt)
        return result.get("entries", []) if result else []
    
    def extract_projects(self, text: str) -> Dict[str, Any]:
        """Extract projects section"""
        prompt = f"""Extract projects from this CV section.

Return ONLY valid JSON, no explanation.
For technologies, extract as array of strings.

Schema:
{{
  "entries": [
    {{
      "name": "project name or null",
      "role": "your role or null",
      "technologies": ["tech1", "tech2"],
      "description": ["bullet points"],
      "url": "github/project URL or null",
      "start_date": "date or null",
      "end_date": "date or null"
    }}
  ]
}}

Text:
{text}
"""
        result = self._call_llm_json(prompt)
        return result.get("entries", []) if result else []
    
    def extract_skills(self, text: str) -> Dict[str, Any]:
        """Extract skills section"""
        prompt = f"""Extract skills from this CV section.
Organize by category if possible.

Return ONLY valid JSON, no explanation.

Schema:
{{
  "entries": [
    {{
      "category": "skill category or null",
      "skills": ["skill1", "skill2", "skill3"]
    }}
  ]
}}

Text:
{text}
"""
        result = self._call_llm_json(prompt)
        return result.get("entries", []) if result else []
    
    def extract_certifications(self, text: str) -> Dict[str, Any]:
        """Extract certifications section"""
        prompt = f"""Extract certifications from this CV section.

Return ONLY valid JSON, no explanation.

Schema:
{{
  "entries": [
    {{
      "name": "certification name",
      "issuer": "issuing organization or null",
      "date": "date obtained or null"
    }}
  ]
}}

Text:
{text}
"""
        result = self._call_llm_json(prompt)
        return result.get("entries", []) if result else []
    
    def extract_awards(self, text: str) -> Dict[str, Any]:
        """Extract awards section"""
        prompt = f"""Extract awards and achievements from this CV section.

Return ONLY valid JSON, no explanation.

Schema:
{{
  "entries": [
    {{
      "title": "award title",
      "organization": "organization or null",
      "date": "date or null"
    }}
  ]
}}

Text:
{text}
"""
        result = self._call_llm_json(prompt)
        return result.get("entries", []) if result else []
    
    def extract_summary(self, text: str) -> Optional[str]:
        """Extract professional summary"""
        prompt = f"""Extract the professional summary from this CV text.

Return ONLY the summary text (2-3 sentences), no JSON, no explanation.
If no clear summary exists, return empty string.

Text:
{text}
"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        summary = response.content[0].text.strip()
        return summary if summary else None
    
    def _call_llm_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Call Claude and parse JSON response
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = response.content[0].text.strip()
            
            # Extract JSON from response (might have markdown code block)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            response_text = response_text.strip()
            data = json.loads(response_text)
            return data
        
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Response was: {response_text}")
            return None
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return None


# Test
if __name__ == '__main__':
    client = ClaudeLLMClient()
    
    test_education = """
    Hanoi University of Science and Technology – HUST
    Ha Noi, Viet Nam
    Major: Computer Science – CPA: 3.47/4.0
    09/2025 – Present
    """
    
    result = client.extract_education(test_education)
    print(json.dumps(result, indent=2, ensure_ascii=False))
