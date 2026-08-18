"""
AWS Bedrock client for Llama 3 70B Instruct.
Handles communication with the AI model for conversation generation.
With fallback responses when Bedrock is unavailable.
"""

import json
from typing import Optional, AsyncGenerator
import structlog

from config import settings

logger = structlog.get_logger()


class BedrockClient:
    """
    Client for AWS Bedrock with Meta Llama 3 70B Instruct.
    Provides both synchronous and streaming response generation.
    Falls back to intelligent scripted responses if Bedrock is unavailable.
    """

    def __init__(self):
        """Initialize the Bedrock client."""
        self.model_id = settings.bedrock_model_id
        self.region = settings.aws_region
        self.max_tokens = settings.bedrock_max_tokens
        self.temperature = settings.bedrock_temperature
        self.top_p = settings.bedrock_top_p
        self.client = None
        self.runtime_client = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the Bedrock runtime client."""
        try:
            import boto3
            session = boto3.Session(
                region_name=self.region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key
            )
            self.runtime_client = session.client("bedrock-runtime")
            self._initialized = True
            logger.info(
                "Bedrock client initialized",
                model=self.model_id,
                region=self.region
            )
        except Exception as e:
            logger.error("Failed to initialize Bedrock client", error=str(e))
            logger.info("⚠️  AI will use fallback responses until Bedrock is available")
            self._initialized = False

    def _get_fallback_response(self, prompt: str) -> str:
        """Generate an intelligent fallback response when Bedrock is unavailable."""
        prompt_lower = prompt.lower()

        # Greeting/new visitor
        if "new" in prompt_lower and ("visitor" in prompt_lower or "person" in prompt_lower):
            return "Hello! Welcome to Code Origin.AI. I don't think we've met before. May I know your name?"

        # Returning visitor - multiple detection patterns
        if "returning" in prompt_lower or "recognized" in prompt_lower or "welcome back" in prompt_lower:
            import re
            # Try to extract name from prompt
            name_match = re.search(r'name[:\s]+(\w+)', prompt_lower)
            if name_match:
                name = name_match.group(1).capitalize()
                return f"Hi {name}! Welcome back to Code Origin.AI. How can I help you today?"
            # Check for name in quotes
            quote_match = re.search(r'["\'](\w+)["\']', prompt)
            if quote_match:
                return f"Hi {quote_match.group(1)}! Welcome back. How can I help you today?"
            return "Welcome back! Great to see you again. How can I help you today?"

        # Check if visitor name is mentioned in context (for ongoing conversation)
        import re
        visitor_name_match = re.search(r'visitor[:\s]*\n*name[:\s]+(\w+)', prompt_lower)
        if not visitor_name_match:
            visitor_name_match = re.search(r'name:\s*(\w+)', prompt_lower)
        
        # Name extraction
        if "extract" in prompt_lower and "name" in prompt_lower:
            # Simple name extraction from quoted speech
            import re
            match = re.search(r'"([^"]+)"', prompt)
            if match:
                speech = match.group(1)
                # Common patterns: "My name is X", "I'm X", "It's X", just "X"
                name_patterns = [
                    r"(?:my name is|i'm|i am|it's|call me)\s+(\w+)",
                    r"^(\w+)$",
                ]
                for pattern in name_patterns:
                    name_match = re.search(pattern, speech, re.IGNORECASE)
                    if name_match:
                        return name_match.group(1).capitalize()
            return "UNKNOWN"

        # Meeting request
        if "meet" in prompt_lower or "appointment" in prompt_lower:
            return "I'd be happy to help you find the right person. Let me check their availability."

        # Goodbye
        if "bye" in prompt_lower or "thank" in prompt_lower or "leaving" in prompt_lower:
            return "Thank you for visiting Code Origin.AI! Have a wonderful day. See you next time!"

        # Help/questions
        if "help" in prompt_lower or "?" in prompt:
            return "Of course! I'm here to help. You can ask me about meeting someone, office directions, or general information about Code Origin.AI."

        # Default conversational response
        return "Thank you! Is there anything else I can help you with today?"

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None
    ) -> str:
        """
        Generate a response from Llama 3 70B.
        Falls back to intelligent scripted responses if Bedrock unavailable.
        """
        if not self._initialized:
            logger.debug("Using fallback response (Bedrock not available)")
            return self._get_fallback_response(prompt)

        # Build the Llama 3 prompt format
        formatted_prompt = self._format_llama_prompt(prompt, system_prompt)

        body = json.dumps({
            "prompt": formatted_prompt,
            "max_gen_len": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
            "top_p": top_p or self.top_p,
        })

        try:
            response = self.runtime_client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json"
            )

            response_body = json.loads(response["body"].read())
            generated_text = response_body.get("generation", "")

            logger.info(
                "Bedrock response generated",
                prompt_length=len(prompt),
                response_length=len(generated_text)
            )

            return generated_text.strip()

        except Exception as e:
            logger.error("Error generating Bedrock response", error=str(e))
            # Fall back to scripted response
            return self._get_fallback_response(prompt)

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from Llama 3 70B.
        Falls back to full response if streaming unavailable.
        """
        if not self._initialized:
            yield self._get_fallback_response(prompt)
            return

        formatted_prompt = self._format_llama_prompt(prompt, system_prompt)

        body = json.dumps({
            "prompt": formatted_prompt,
            "max_gen_len": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
            "top_p": self.top_p,
        })

        try:
            response = self.runtime_client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json"
            )

            stream = response.get("body")
            if stream:
                for event in stream:
                    chunk = event.get("chunk")
                    if chunk:
                        data = json.loads(chunk.get("bytes", b"{}").decode())
                        text = data.get("generation", "")
                        if text:
                            yield text

        except Exception as e:
            logger.error("Error in streaming response", error=str(e))
            yield self._get_fallback_response(prompt)

    def _format_llama_prompt(
        self,
        user_message: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Format the prompt for Llama 3 Instruct model.

        Llama 3 uses the following format:
        <|begin_of_text|><|start_header_id|>system<|end_header_id|>
        {system_message}<|eot_id|>
        <|start_header_id|>user<|end_header_id|>
        {user_message}<|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>
        """
        parts = ["<|begin_of_text|>"]

        if system_prompt:
            parts.append(
                f"<|start_header_id|>system<|end_header_id|>\n\n"
                f"{system_prompt}<|eot_id|>"
            )

        parts.append(
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_message}<|eot_id|>"
        )

        parts.append(
            "<|start_header_id|>assistant<|end_header_id|>\n\n"
        )

        return "".join(parts)

    async def health_check(self) -> bool:
        """Check if Bedrock is accessible."""
        try:
            response = await self.generate_response(
                "Say 'OK' in one word.",
                max_tokens=10
            )
            return len(response) > 0
        except Exception:
            return False
