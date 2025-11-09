"""
LLM-based Trading Signal Validation Service

This service uses Large Language Models to validate trading signals before execution,
providing an additional layer of analysis and risk management.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# Optional third-party LLM clients; import lazily/defensively to avoid hard dependency at startup
try:
    from openai import AsyncOpenAI  # type: ignore
except Exception:  # ImportError or any env issue
    AsyncOpenAI = None  # type: ignore

try:
    from anthropic import AsyncAnthropic  # type: ignore
except Exception:
    AsyncAnthropic = None  # type: ignore
import aiohttp

from config.settings import get_settings
from services.logging_service import trading_logger

class ValidationResult(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    CAUTION = "caution"
    INSUFFICIENT_DATA = "insufficient_data"

class LLMProvider(Enum):
    OPENAI = "openai"
    PERPLEXITY = "perplexity"
    ANTHROPIC = "anthropic"
    GROQ = "groq"

@dataclass
class ValidationResponse:
    result: ValidationResult
    confidence: float  # 0.0 to 1.0
    reasoning: str
    risk_factors: List[str]
    suggestions: List[str]
    market_context: str
    execution_priority: str  # "high", "medium", "low"
    recommended_position_size: Optional[float] = None
    
class SignalValidationService:
    """
    LLM-based signal validation service that analyzes trading signals
    against market context, risk factors, and trading logic.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = trading_logger
        
        # Initialize LLM clients
        self.openai_client = None
        self.anthropic_client = None
        self.perplexity_session = None
        
        # Configuration
        self.validation_enabled = getattr(self.settings, 'LLM_VALIDATION_ENABLED', False)
        self.primary_provider = getattr(self.settings, 'LLM_PRIMARY_PROVIDER', 'openai')
        self.validation_timeout = getattr(self.settings, 'LLM_VALIDATION_TIMEOUT', 10)
        self.min_confidence_threshold = getattr(self.settings, 'LLM_MIN_CONFIDENCE', 0.7)
        
        # Initialize clients if enabled
        if self.validation_enabled:
            self._initialize_llm_clients()
    
    def _initialize_llm_clients(self):
        """Initialize LLM API clients"""
        try:
            # OpenAI
            openai_key = getattr(self.settings, 'OPENAI_API_KEY', None)
            if openai_key and AsyncOpenAI is not None:
                self.openai_client = AsyncOpenAI(api_key=openai_key)
            elif openai_key and AsyncOpenAI is None:
                self.logger.warning("OpenAI key provided but openai client not installed; skipping OpenAI initialization")
                
            # Anthropic
            anthropic_key = getattr(self.settings, 'ANTHROPIC_API_KEY', None)
            if anthropic_key and AsyncAnthropic is not None:
                self.anthropic_client = AsyncAnthropic(api_key=anthropic_key)
            elif anthropic_key and AsyncAnthropic is None:
                self.logger.warning("Anthropic key provided but anthropic client not installed; skipping Anthropic initialization")
            
            # Perplexity
            perplexity_key = getattr(self.settings, 'PERPLEXITY_API_KEY', None)
            if perplexity_key:
                self.perplexity_session = aiohttp.ClientSession(
                    headers={
                        'Authorization': f'Bearer {perplexity_key}',
                        'Content-Type': 'application/json'
                    }
                )
                
            self.logger.info(f"LLM Signal Validation initialized with {self.primary_provider}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM clients: {e}")
            self.validation_enabled = False
    
    async def validate_signal(self, signal_data: Dict[str, Any], 
                            market_context: Optional[Dict] = None) -> ValidationResponse:
        """
        Validate a trading signal using LLM analysis
        
        Args:
            signal_data: Dictionary containing signal information
            market_context: Optional market context data
            
        Returns:
            ValidationResponse with analysis results
        """
        if not self.validation_enabled:
            return ValidationResponse(
                result=ValidationResult.APPROVE,
                confidence=0.5,
                reasoning="LLM validation disabled",
                risk_factors=[],
                suggestions=[],
                market_context="N/A",
                execution_priority="medium"
            )
        
        try:
            # Build validation prompt
            prompt = self._build_validation_prompt(signal_data, market_context)
            
            # Get LLM analysis
            if self.primary_provider == "openai" and self.openai_client:
                response = await self._validate_with_openai(prompt)
            elif self.primary_provider == "anthropic" and self.anthropic_client:
                response = await self._validate_with_anthropic(prompt)
            elif self.primary_provider == "perplexity" and self.perplexity_session:
                response = await self._validate_with_perplexity(prompt)
            else:
                # Fallback to rule-based validation
                response = self._fallback_validation(signal_data)
            
            # Log validation result
            self.logger.info(f"Signal validation completed: {signal_data.get('symbol')} - {response.result.value}")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Signal validation failed: {e}")
            return ValidationResponse(
                result=ValidationResult.INSUFFICIENT_DATA,
                confidence=0.0,
                reasoning=f"Validation error: {str(e)}",
                risk_factors=["Validation system error"],
                suggestions=["Manual review recommended"],
                market_context="Error occurred",
                execution_priority="low"
            )
    
    def _build_validation_prompt(self, signal_data: Dict[str, Any], 
                               market_context: Optional[Dict] = None) -> str:
        """Build the validation prompt for LLM"""
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        prompt = f"""
As an expert trading analyst, please validate this trading signal:

SIGNAL DETAILS:
- Symbol: {signal_data.get('symbol', 'N/A')}
- Signal Type: {signal_data.get('signal_type', 'N/A')}
- Entry Price: ₹{signal_data.get('price', 0):.2f}
- Stop Loss: ₹{signal_data.get('stop_loss', 0):.2f}
- Take Profit: ₹{signal_data.get('take_profit', 0):.2f}
- Quantity: {signal_data.get('quantity', 0)}
- Confidence: {signal_data.get('confidence', 0):.2f}
- Strategy: {signal_data.get('strategy_name', 'N/A')}
- Reasoning: {signal_data.get('reason', 'N/A')}
- Generated At: {signal_data.get('generated_at', current_time)}

RISK METRICS:
- Risk per Trade: {((signal_data.get('price', 0) - signal_data.get('stop_loss', 0)) / signal_data.get('price', 1) * 100):.2f}%
- Reward to Risk Ratio: {((signal_data.get('take_profit', 0) - signal_data.get('price', 0)) / max(signal_data.get('price', 0) - signal_data.get('stop_loss', 0), 0.01)):.2f}:1
- Position Size: ₹{signal_data.get('quantity', 0) * signal_data.get('price', 0):,.0f}

MARKET CONTEXT:
{self._format_market_context(market_context)}

Please analyze this signal and provide:

1. VALIDATION RESULT: One of [APPROVE, REJECT, CAUTION, INSUFFICIENT_DATA]
2. CONFIDENCE LEVEL: 0.0 to 1.0
3. REASONING: Detailed explanation of your decision
4. RISK FACTORS: Key risks identified
5. SUGGESTIONS: Recommendations for improvement
6. MARKET CONTEXT: Your assessment of current market conditions
7. EXECUTION PRIORITY: [high, medium, low]
8. RECOMMENDED POSITION SIZE: Percentage of suggested position size (0.0 to 1.0)

Consider:
- Technical analysis validity
- Risk-reward ratio appropriateness
- Market timing and conditions
- Position sizing relative to risk
- Signal quality and confidence
- Sector and broader market trends

Respond in JSON format:
{{
    "result": "APPROVE|REJECT|CAUTION|INSUFFICIENT_DATA",
    "confidence": 0.0-1.0,
    "reasoning": "detailed explanation",
    "risk_factors": ["factor1", "factor2"],
    "suggestions": ["suggestion1", "suggestion2"],
    "market_context": "market assessment",
    "execution_priority": "high|medium|low",
    "recommended_position_size": 0.0-1.0
}}
"""
        
        return prompt.strip()
    
    def _format_market_context(self, market_context: Optional[Dict]) -> str:
        """Format market context for the prompt"""
        if not market_context:
            return "- No market context data available"
        
        context_str = ""
        if "market_trend" in market_context:
            context_str += f"- Market Trend: {market_context['market_trend']}\n"
        if "volatility" in market_context:
            context_str += f"- Volatility: {market_context['volatility']}\n"
        if "sector_performance" in market_context:
            context_str += f"- Sector Performance: {market_context['sector_performance']}\n"
        if "news_sentiment" in market_context:
            context_str += f"- News Sentiment: {market_context['news_sentiment']}\n"
        
        return context_str if context_str else "- Limited market context available"
    
    async def _validate_with_openai(self, prompt: str) -> ValidationResponse:
        """Validate signal using OpenAI GPT"""
        try:
            response = await asyncio.wait_for(
                self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert trading analyst with deep knowledge of Indian stock markets, technical analysis, and risk management."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.3
                ),
                timeout=self.validation_timeout
            )
            
            content = response.choices[0].message.content
            return self._parse_llm_response(content)
            
        except asyncio.TimeoutError:
            raise Exception("OpenAI API timeout")
        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")
    
    async def _validate_with_anthropic(self, prompt: str) -> ValidationResponse:
        """Validate signal using Anthropic Claude"""
        try:
            response = await asyncio.wait_for(
                self.anthropic_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=1000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                ),
                timeout=self.validation_timeout
            )
            
            content = response.content[0].text
            return self._parse_llm_response(content)
            
        except asyncio.TimeoutError:
            raise Exception("Anthropic API timeout")
        except Exception as e:
            raise Exception(f"Anthropic API error: {e}")
    
    async def _validate_with_perplexity(self, prompt: str) -> ValidationResponse:
        """Validate signal using Perplexity AI"""
        try:
            payload = {
                "model": "llama-3.1-sonar-small-128k-online",  # Perplexity's latest model with web search
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional trading signal analyst with access to current market data. Analyze the trading signal and provide validation with real-time market context."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 1000,
                "return_citations": True,
                "search_domain_filter": ["finance.yahoo.com", "marketwatch.com", "bloomberg.com"]
            }
            
            async with self.perplexity_session.post(
                "https://api.perplexity.ai/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.validation_timeout)
            ) as response:
                if response.status != 200:
                    raise Exception(f"Perplexity API returned status {response.status}")
                
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Log citations if available
                if "citations" in data:
                    self.logger.info(f"Perplexity validation used sources: {data['citations']}")
                
                return self._parse_llm_response(content)
                
        except asyncio.TimeoutError:
            raise Exception("Perplexity API timeout")
        except Exception as e:
            raise Exception(f"Perplexity API error: {e}")
    
    def _parse_llm_response(self, content: str) -> ValidationResponse:
        """Parse LLM response into ValidationResponse"""
        try:
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_content = content[json_start:json_end]
            data = json.loads(json_content)
            
            # Map result string to enum
            result_mapping = {
                "APPROVE": ValidationResult.APPROVE,
                "REJECT": ValidationResult.REJECT,
                "CAUTION": ValidationResult.CAUTION,
                "INSUFFICIENT_DATA": ValidationResult.INSUFFICIENT_DATA
            }
            
            result = result_mapping.get(data.get("result", "INSUFFICIENT_DATA"))
            
            return ValidationResponse(
                result=result,
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", "No reasoning provided"),
                risk_factors=data.get("risk_factors", []),
                suggestions=data.get("suggestions", []),
                market_context=data.get("market_context", "N/A"),
                execution_priority=data.get("execution_priority", "medium"),
                recommended_position_size=data.get("recommended_position_size")
            )
            
        except Exception as e:
            raise Exception(f"Failed to parse LLM response: {e}")
    
    def _fallback_validation(self, signal_data: Dict[str, Any]) -> ValidationResponse:
        """Fallback rule-based validation when LLM is unavailable"""
        
        # Basic rule-based validation logic
        confidence = signal_data.get('confidence', 0.0)
        price = signal_data.get('price', 0)
        stop_loss = signal_data.get('stop_loss', 0)
        take_profit = signal_data.get('take_profit', 0)
        
        # Calculate risk-reward ratio
        risk = abs(price - stop_loss) if stop_loss > 0 else price * 0.02
        reward = abs(take_profit - price) if take_profit > 0 else price * 0.03
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # Validation logic
        if confidence < 0.6:
            result = ValidationResult.REJECT
            reasoning = "Low signal confidence"
        elif risk_reward_ratio < 1.5:
            result = ValidationResult.CAUTION
            reasoning = "Poor risk-reward ratio"
        elif confidence > 0.8 and risk_reward_ratio > 2.0:
            result = ValidationResult.APPROVE
            reasoning = "High confidence with good risk-reward ratio"
        else:
            result = ValidationResult.CAUTION
            reasoning = "Moderate signal quality"
        
        return ValidationResponse(
            result=result,
            confidence=confidence,
            reasoning=reasoning,
            risk_factors=["Rule-based validation only"],
            suggestions=["Consider manual review"],
            market_context="Limited context available",
            execution_priority="medium"
        )
    
    async def validate_multiple_signals(self, signals: List[Dict[str, Any]], 
                                      market_context: Optional[Dict] = None) -> List[ValidationResponse]:
        """Validate multiple signals concurrently"""
        
        if not signals:
            return []
        
        # Create validation tasks
        tasks = [
            self.validate_signal(signal, market_context)
            for signal in signals
        ]
        
        # Execute validations concurrently with limited concurrency
        semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent validations
        
        async def validate_with_semaphore(task):
            async with semaphore:
                return await task
        
        limited_tasks = [validate_with_semaphore(task) for task in tasks]
        results = await asyncio.gather(*limited_tasks, return_exceptions=True)
        
        # Handle exceptions
        validated_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Validation failed for signal {i}: {result}")
                validated_results.append(
                    ValidationResponse(
                        result=ValidationResult.INSUFFICIENT_DATA,
                        confidence=0.0,
                        reasoning=f"Validation error: {str(result)}",
                        risk_factors=["Validation failed"],
                        suggestions=["Manual review required"],
                        market_context="Error",
                        execution_priority="low"
                    )
                )
            else:
                validated_results.append(result)
        
        return validated_results
    
    def should_execute_signal(self, validation: ValidationResponse) -> bool:
        """Determine if signal should be executed based on validation"""
        
        if validation.result == ValidationResult.APPROVE:
            return validation.confidence >= self.min_confidence_threshold
        elif validation.result == ValidationResult.CAUTION:
            # Execute cautious signals only with high confidence
            return validation.confidence >= 0.8
        else:
            return False
    
    def get_execution_metadata(self, validation: ValidationResponse) -> Dict[str, Any]:
        """Get execution metadata based on validation"""
        
        position_size_multiplier = 1.0
        
        if validation.result == ValidationResult.CAUTION:
            position_size_multiplier = 0.7  # Reduce position size for cautious signals
        elif validation.recommended_position_size:
            position_size_multiplier = validation.recommended_position_size
        
        return {
            "llm_validation_result": validation.result.value,
            "llm_confidence": validation.confidence,
            "llm_reasoning": validation.reasoning,
            "position_size_multiplier": position_size_multiplier,
            "execution_priority": validation.execution_priority,
            "risk_factors": validation.risk_factors,
            "suggestions": validation.suggestions
        }
    
    async def cleanup(self):
        """Clean up resources"""
        if self.perplexity_session:
            await self.perplexity_session.close()

# Global service instance
_signal_validator = None

def get_signal_validator() -> SignalValidationService:
    """Get the global signal validation service instance"""
    global _signal_validator
    if _signal_validator is None:
        _signal_validator = SignalValidationService()
    return _signal_validator