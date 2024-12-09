import requests
import json
import sqlite3
import hashlib
from typing import Optional, Dict, Any, Union
from datetime import datetime
import os

class GeminiClient:
    """
    A client for interacting with the Google Gemini API with built-in caching capabilities.
    """
    
    def __init__(self, api_key: str, cache_db_path: str = "gemini_cache.db"):
        """
        Initialize the Gemini client.
        
        Args:
            api_key: Your Gemini API key
            cache_db_path: Path to the SQLite cache database
        """
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1/models"
        self.cache_db_path = cache_db_path
        self._init_cache()
        
    def _init_cache(self):
        """Initialize the SQLite cache database."""
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prompt_cache (
                    prompt_hash TEXT PRIMARY KEY,
                    prompt TEXT,
                    response TEXT,
                    model TEXT,
                    timestamp DATETIME,
                    parameters TEXT
                )
            """)
    
    def _generate_cache_key(self, prompt: str, model: str, parameters: Dict) -> str:
        """Generate a unique hash for the prompt and its parameters."""
        cache_data = f"{prompt}|{model}|{json.dumps(parameters, sort_keys=True)}"
        return hashlib.sha256(cache_data.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """Retrieve a cached response if it exists."""
        with sqlite3.connect(self.cache_db_path) as conn:
            cursor = conn.execute(
                "SELECT response FROM prompt_cache WHERE prompt_hash = ?",
                (cache_key,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    
    def _cache_response(self, cache_key: str, prompt: str, response: str, 
                       model: str, parameters: Dict):
        """Cache a response in the SQLite database."""
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO prompt_cache 
                (prompt_hash, prompt, response, model, timestamp, parameters)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cache_key, prompt, response, model, 
                 datetime.now().isoformat(), json.dumps(parameters))
            )
    
    def generate_text(
        self,
        prompt: str,
        model: str = "gemini-pro",
        temperature: float = 0.7,
        top_p: float = 0.95,
        top_k: int = 40,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[list] = None,
        safety_settings: Optional[list] = None,
        structured_output: Optional[Dict] = None,
        system_instructions: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generate text using the Gemini API.
        
        Args:
            prompt: The input prompt
            model: The model to use (default: gemini-pro)
            temperature: Controls randomness (0.0 to 1.0)
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            max_tokens: Maximum number of tokens to generate
            stop_sequences: List of sequences that will stop generation
            safety_settings: List of safety setting configurations
            structured_output: Schema for structured JSON output
            system_instructions: System instructions for the model
            use_cache: Whether to use response caching
        
        Returns:
            Dict containing the response and additional information
        """
        parameters = {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_output_tokens": max_tokens,
            "stop_sequences": stop_sequences or [],
            "safety_settings": safety_settings or []
        }
        
        if structured_output:
            parameters["structured_output"] = structured_output
        
        # Prepare the request payload
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": parameters
        }
        
        if system_instructions:
            payload["contents"][0]["role"] = "user"
            payload.setdefault("safetySettings", [])
            payload["systemInstructions"] = {"content": system_instructions}
        
        # Check cache first if enabled
        cache_key = self._generate_cache_key(prompt, model, parameters)
        if use_cache:
            cached_response = self._get_cached_response(cache_key)
            if cached_response:
                return json.loads(cached_response)
        
        # Make API request
        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
        response = requests.post(url, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"API request failed: {response.text}")
        
        result = response.json()
        
        # Cache the response if caching is enabled
        if use_cache:
            self._cache_response(
                cache_key, prompt, json.dumps(result), 
                model, parameters
            )
        
        return result
    
    def clear_cache(self):
        """Clear all cached responses."""
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.execute("DELETE FROM prompt_cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache usage."""
        with sqlite3.connect(self.cache_db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_entries,
                    MIN(timestamp) as oldest_entry,
                    MAX(timestamp) as newest_entry
                FROM prompt_cache
            """)
            stats = cursor.fetchone()
            return {
                "total_entries": stats[0],
                "oldest_entry": stats[1],
                "newest_entry": stats[2]
            }
        