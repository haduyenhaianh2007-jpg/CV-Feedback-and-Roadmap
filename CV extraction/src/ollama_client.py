"""
Ollama Client Wrapper - Local LLM integration
Qwen 2.5 7B Instruct for CV extraction
"""

import requests
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class OllamaConfig:
    """Ollama configuration"""
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b-instruct-q4_K_M"  # Q4 quantized (fast + memory efficient)
    timeout: int = 120  # seconds
    temperature: float = 0.3  # Low for deterministic JSON output
    top_p: float = 0.9
    top_k: int = 40


class OllamaClient:
    """Ollama API client wrapper"""
    
    def __init__(self, config: Optional[OllamaConfig] = None):
        """Initialize Ollama client"""
        self.config = config or OllamaConfig()
        self.base_url = self.config.base_url.rstrip('/')
        self.model = self.config.model
        
        # Test connection
        if not self.is_available():
            logger.warning(f"Ollama not available at {self.config.base_url}")
    
    def is_available(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            
            if response.status_code != 200:
                return False
            
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            
            # Check if our model is available
            is_available = any(self.model in name for name in model_names)
            
            if not is_available:
                logger.warning(f"Model {self.model} not found in Ollama. Available: {model_names}")
            
            return is_available
            
        except Exception as e:
            logger.error(f"Ollama connection error: {e}")
            return False
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        json_mode: bool = False,
    ) -> str:
        """
        Generate response from Qwen model
        
        Args:
            prompt: User prompt
            system: System prompt/instruction
            temperature: Override default temperature
            json_mode: If True, ensure JSON output
        
        Returns:
            Generated text
        """
        messages = []
        
        if system:
            messages.append({"role": "system", "content": system})
        
        messages.append({"role": "user", "content": prompt})
        
        temp = temperature if temperature is not None else self.config.temperature
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temp,
                    "top_p": self.config.top_p,
                    "top_k": self.config.top_k,
                    "stream": False,
                    "format": "json" if json_mode else None,
                },
                timeout=self.config.timeout,
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama error: {response.status_code} {response.text}")
            
            result = response.json()
            return result.get('message', {}).get('content', '').strip()
            
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Ollama request timed out after {self.config.timeout}s")
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise
    
    def extract_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_retries: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate and extract JSON from response
        
        Args:
            prompt: User prompt
            system: System instruction
            max_retries: Retry count if JSON parsing fails
        
        Returns:
            Parsed JSON or None if failed
        """
        for attempt in range(max_retries):
            try:
                response = self.generate(prompt, system=system, json_mode=True)
                
                # Try to parse JSON
                data = json.loads(response)
                return data
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    # Retry with repair prompt
                    repair_prompt = f"""Fix this invalid JSON and return ONLY valid JSON:

{response}

Rules:
- Output ONLY valid JSON
- No markdown, no explanation
- Fix missing commas, quotes, etc."""
                    
                    try:
                        response = self.generate(repair_prompt, temperature=0.1)
                        data = json.loads(response)
                        return data
                    except:
                        continue
                else:
                    logger.error(f"Failed to parse JSON after {max_retries} attempts")
                    return None
            
            except Exception as e:
                logger.error(f"Error: {e}")
                return None
        
        return None
    
    def stream_generate(self, prompt: str, system: Optional[str] = None):
        """
        Stream response from Qwen (useful for long outputs)
        
        Yields:
            Text chunks as they arrive
        """
        messages = []
        
        if system:
            messages.append({"role": "system", "content": system})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.config.temperature,
                    "stream": True,
                },
                timeout=self.config.timeout,
                stream=True,
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama error: {response.status_code}")
            
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if 'message' in chunk:
                        content = chunk['message'].get('content', '')
                        if content:
                            yield content
                    
                    # Stop if done
                    if chunk.get('done', False):
                        break
        
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text
        Note: This is approximate (Ollama doesn't have exact token count API)
        """
        # Rough estimation: 1 token ≈ 4 chars or 0.75 words
        words = len(text.split())
        return max(int(words * 1.3), int(len(text) / 4))


# System prompts for CV extraction tasks
SYSTEM_PROMPTS = {
    "cv_parser": """You are an expert CV/Resume parser for ATS (Applicant Tracking System).

Your task is to extract and structure CV information from text.

Requirements:
1. Extract ONLY information explicitly present in the text
2. Do NOT invent or hallucinate data
3. Return ONLY valid JSON
4. For bilingual fields, provide both Vietnamese and English versions
5. For missing information, use null
6. Preserve original wording when possible
7. Normalize dates to format: MM/YYYY or YYYY-MM
8. For "Currently working/studying", detect "Present", "Hiện tại", or ongoing (no end date)

Output format: Valid JSON only, no markdown, no explanation.""",
    
    "education_extractor": """You are an expert education information extractor.

Extract education entries from the text.

For each entry, extract:
- School/University name (bilingual if possible)
- Degree/Major
- GPA (if available)
- Start date (MM/YYYY format)
- End date (MM/YYYY or "Present")
- Currently studying (boolean)
- Description/Additional info

Return ONLY valid JSON array of education entries.""",
    
    "experience_extractor": """You are an expert work experience extractor.

Extract work experience entries from text.

For each entry, extract:
- Company name
- Position/Title (bilingual)
- Start date (MM/YYYY)
- End date (MM/YYYY or "Present")
- Currently working (boolean)
- Job description (as list of bullet points)
- Technologies used (as list)

Return ONLY valid JSON array of experiences.""",
    
    "project_extractor": """You are an expert project information extractor.

Extract project entries from text.

For each project, extract:
- Project name
- Role/Position (bilingual)
- Description (as bullet points list)
- Technologies used (as list)
- Project URL (if available)
- Duration (start_date, end_date in MM/YYYY format)

Return ONLY valid JSON array of projects.""",
    
    "skills_extractor": """You are an expert skills extractor.

Extract and categorize skills from text.

For each skill, include:
- Skill name
- Category (Programming, AI/ML, Tools, Languages, etc.)
- Proficiency level (if available)

Group skills by category when possible.

Return ONLY valid JSON with array of skills and optional category mapping.""",
}


def create_ollama_client(
    base_url: str = "http://localhost:11434",
    model: str = "qwen2.5:7b-instruct-q4_K_M"
) -> OllamaClient:
    """Factory function to create Ollama client"""
    config = OllamaConfig(base_url=base_url, model=model)
    return OllamaClient(config)


# Test function
def test_ollama_connection(base_url: str = "http://localhost:11434"):
    """Test Ollama connection"""
    try:
        client = OllamaClient(OllamaConfig(base_url=base_url))
        
        if not client.is_available():
            print("❌ Ollama not available or model not found")
            return False
        
        print("✓ Ollama connection successful")
        
        # Test generation
        response = client.generate("Say 'Hello from Qwen!'", temperature=0.1)
        print(f"✓ Model response: {response}")
        
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
