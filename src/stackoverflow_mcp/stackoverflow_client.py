"""
StackOverflow API client for MCP server.
"""

import asyncio
import time
import hashlib
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from urllib.parse import urlencode
from dataclasses import dataclass, field
from enum import Enum
import httpx
from .config import ServerConfig
from .logging import get_logger
import re
import html


logger = get_logger(__name__)


class RequestPriority(Enum):
    """Request priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class AccessMode(Enum):
    """API access modes."""
    AUTO = "auto"  # Automatically choose best mode
    AUTHENTICATED = "authenticated"  # Force authenticated access
    UNAUTHENTICATED = "unauthenticated"  # Force unauthenticated access


@dataclass
class QueuedRequest:
    """Represents a queued API request."""
    id: str
    endpoint: str
    params: Dict[str, Any]
    priority: RequestPriority
    created_at: float
    max_retries: int = 3
    retry_count: int = 0
    future: asyncio.Future = field(default_factory=lambda: asyncio.Future())
    access_mode: AccessMode = AccessMode.AUTO
    
    def __post_init__(self):
        if not self.future:
            self.future = asyncio.Future()
    
    def get_cache_key(self) -> str:
        """Generate cache key for this request."""
        # Create deterministic key from endpoint and sorted params
        cache_params = {k: v for k, v in sorted(self.params.items()) if k != "key"}
        cache_data = f"{self.endpoint}:{json.dumps(cache_params, sort_keys=True)}"
        return hashlib.md5(cache_data.encode()).hexdigest()


class RequestCache:
    """Simple in-memory cache for API responses."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return None
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set cached value."""
        # Simple LRU eviction when cache is full
        if len(self._cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        
        self._cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        valid_entries = sum(1 for _, timestamp in self._cache.values() 
                          if current_time - timestamp <= self.ttl_seconds)
        
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds
        }


class RequestQueue:
    """Manages API request queue with priority and concurrency control."""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self._queue: List[QueuedRequest] = []
        self._processing: Dict[str, QueuedRequest] = {}
        self._completed: Dict[str, QueuedRequest] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None
        self._shutdown = False
    
    async def enqueue(self, request: QueuedRequest) -> asyncio.Future:
        """Add request to queue."""
        async with self._queue_lock:
            # Check for duplicate requests
            duplicate = self._find_duplicate(request)
            if duplicate:
                logger.debug(f"Duplicate request found, returning existing future: {request.id}")
                return duplicate.future
            
            # Insert request in priority order
            self._insert_by_priority(request)
            logger.debug(f"Enqueued request {request.id} with priority {request.priority}")
        
        # Start worker if not running
        if not self._worker_task or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())
        
        return request.future
    
    def _find_duplicate(self, request: QueuedRequest) -> Optional[QueuedRequest]:
        """Find duplicate request in queue or processing."""
        cache_key = request.get_cache_key()
        
        # Check queue
        for queued_req in self._queue:
            if queued_req.get_cache_key() == cache_key:
                return queued_req
        
        # Check currently processing
        for proc_req in self._processing.values():
            if proc_req.get_cache_key() == cache_key:
                return proc_req
        
        return None
    
    def _insert_by_priority(self, request: QueuedRequest) -> None:
        """Insert request in queue maintaining priority order."""
        # Insert in priority order (higher priority first)
        for i, queued_req in enumerate(self._queue):
            if request.priority.value > queued_req.priority.value:
                self._queue.insert(i, request)
                return
        
        # Add to end if lowest priority
        self._queue.append(request)
    
    async def _worker(self) -> None:
        """Process requests from queue."""
        while not self._shutdown:
            try:
                async with self._queue_lock:
                    if not self._queue:
                        break
                    
                    request = self._queue.pop(0)
                    self._processing[request.id] = request
                
                logger.debug(f"Processing request {request.id}")
                
                # Process request with semaphore
                async with self._semaphore:
                    await self._process_request(request)
                
                # Move to completed
                async with self._queue_lock:
                    self._processing.pop(request.id, None)
                    self._completed[request.id] = request
                
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)
    
    async def _process_request(self, request: QueuedRequest) -> None:
        """Process a single request."""
        try:
            # This will be implemented by the client
            result = await self._execute_request(request)
            request.future.set_result(result)
        except Exception as e:
            if request.retry_count < request.max_retries:
                request.retry_count += 1
                logger.warning(f"Request {request.id} failed, retrying ({request.retry_count}/{request.max_retries}): {e}")
                
                # Re-queue with exponential backoff
                await asyncio.sleep(2 ** request.retry_count)
                async with self._queue_lock:
                    self._insert_by_priority(request)
            else:
                logger.error(f"Request {request.id} failed after {request.max_retries} retries: {e}")
                request.future.set_exception(e)
    
    async def _execute_request(self, request: QueuedRequest) -> Any:
        """Execute request - to be implemented by client."""
        raise NotImplementedError("Must be implemented by client")
    
    def get_status(self) -> Dict[str, Any]:
        """Get queue status."""
        return {
            "queued": len(self._queue),
            "processing": len(self._processing),
            "completed": len(self._completed),
            "max_concurrent": self.max_concurrent,
            "worker_running": self._worker_task and not self._worker_task.done()
        }
    
    async def shutdown(self) -> None:
        """Shutdown queue and cancel pending requests."""
        self._shutdown = True
        
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all pending requests
        async with self._queue_lock:
            for request in self._queue:
                if not request.future.done():
                    request.future.cancel()
            
            for request in self._processing.values():
                if not request.future.done():
                    request.future.cancel()


class RateLimitState:
    """Track rate limiting state and quotas."""
    
    def __init__(self):
        self.is_rate_limited = False
        self.backoff_until = 0.0
        self.current_backoff = 1.0
        self.max_backoff = 300.0  # 5 minutes max
        self.quotas = {}
        self.reset_time = None
        self.remaining_requests = None
        
    def update_from_headers(self, headers: Dict[str, str]) -> None:
        """Update state from HTTP response headers."""
        # StackOverflow API headers
        if 'x-ratelimit-remaining' in headers:
            try:
                self.remaining_requests = int(headers['x-ratelimit-remaining'])
                logger.debug(f"Rate limit remaining: {self.remaining_requests}")
            except ValueError:
                pass
                
        if 'x-ratelimit-reset' in headers:
            try:
                self.reset_time = int(headers['x-ratelimit-reset'])
                logger.debug(f"Rate limit resets at: {self.reset_time}")
            except ValueError:
                pass
                
        # Check if we're approaching limits
        if self.remaining_requests is not None and self.remaining_requests < 5:
            logger.warning(f"Approaching rate limit: {self.remaining_requests} requests remaining")
    
    def set_rate_limited(self, backoff_seconds: Optional[float] = None) -> None:
        """Mark as rate limited with optional backoff time."""
        self.is_rate_limited = True
        if backoff_seconds:
            self.backoff_until = time.time() + backoff_seconds
            self.current_backoff = backoff_seconds
        else:
            # Use current backoff, then double it for next time
            self.backoff_until = time.time() + self.current_backoff
            current_for_this_time = self.current_backoff
            self.current_backoff = min(self.current_backoff * 2, self.max_backoff)
        
        logger.warning(f"Rate limited until {self.backoff_until}, backoff: {self.current_backoff}s")
    
    def check_recovery(self) -> bool:
        """Check if rate limiting has been recovered."""
        if self.is_rate_limited and time.time() >= self.backoff_until:
            self.is_rate_limited = False
            self.current_backoff = max(1.0, self.current_backoff / 2)  # Reduce backoff
            logger.info("Rate limit recovered, resuming normal operation")
            return True
        return False


class AuthenticationState:
    """Track API authentication state and capabilities."""
    
    def __init__(self):
        self.is_authenticated = False
        self.api_key_valid = None  # None = unknown, True = valid, False = invalid
        self.authentication_tested = False
        self.daily_quota = None
        self.daily_quota_remaining = None
        self.last_validation_time = None
        self.authentication_error = None
    
    def set_authentication_status(self, is_valid: bool, error_message: Optional[str] = None) -> None:
        """Update authentication status."""
        self.api_key_valid = is_valid
        self.is_authenticated = is_valid
        self.authentication_tested = True
        self.last_validation_time = time.time()
        self.authentication_error = error_message
        
        if is_valid:
            logger.info("API authentication successful")
        else:
            logger.warning(f"API authentication failed: {error_message}")
    
    def update_quota_info(self, quota_max: Optional[int], quota_remaining: Optional[int]) -> None:
        """Update quota information from API responses."""
        if quota_max is not None:
            self.daily_quota = quota_max
        if quota_remaining is not None:
            self.daily_quota_remaining = quota_remaining


class ContentFormatter:
    """Advanced content formatting and validation utilities."""
    
    def __init__(self, max_content_length: int = 50000):
        """
        Initialize content formatter.
        
        Args:
            max_content_length: Maximum allowed content length before truncation
        """
        self.max_content_length = max_content_length
        
    def convert_html_to_markdown(self, html_content: str, preserve_code_blocks: bool = True) -> str:
        """
        Enhanced HTML to Markdown conversion with code block preservation.
        
        Args:
            html_content: HTML content to convert
            preserve_code_blocks: Whether to preserve code blocks and syntax highlighting
            
        Returns:
            High-quality Markdown formatted content
        """
        if not html_content or not html_content.strip():
            return ""
            
        try:
            from markdownify import markdownify as md
            
            # Pre-process: preserve code blocks and syntax highlighting
            processed_html = self._preprocess_html_for_markdown(html_content, preserve_code_blocks)
            
            # Convert HTML to markdown with enhanced settings
            markdown = md(
                processed_html,
                heading_style="ATX",  # Use # for headings
                bullets="-",  # Use - for bullet points
                strip=['script', 'style'],  # Remove script and style tags
                convert=['b', 'strong', 'i', 'em', 'code', 'pre'],  # Ensure important tags are converted
                wrap=True,  # Wrap long lines
                wrap_width=100,  # Line wrap width
            )
            
            # Post-process: clean up and enhance markdown
            markdown = self._postprocess_markdown(markdown)
            
            # Truncate if needed
            markdown = self.truncate_content(markdown, "markdown")
            
            return markdown
            
        except ImportError:
            logger.warning("markdownify not available, using fallback HTML processing")
            return self._fallback_html_processing(html_content)
        except Exception as e:
            logger.warning(f"Failed to convert HTML to markdown: {e}")
            return self._fallback_html_processing(html_content)
    
    def _preprocess_html_for_markdown(self, html_content: str, preserve_code_blocks: bool) -> str:
        """Pre-process HTML to improve markdown conversion quality."""
        if not preserve_code_blocks:
            return html_content
            
        # Preserve inline code with better formatting
        html_content = re.sub(r'<code>(.*?)</code>', r'`\1`', html_content, flags=re.DOTALL)
        
        # Enhance pre blocks with language detection
        def enhance_pre_block(match):
            content = match.group(1)
            # Try to detect language from common patterns
            language = self._detect_code_language(content)
            if language:
                return f'\n```{language}\n{content.strip()}\n```\n'
            else:
                return f'\n```\n{content.strip()}\n```\n'
        
        html_content = re.sub(r'<pre[^>]*>(.*?)</pre>', enhance_pre_block, html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Improve blockquote formatting
        html_content = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', r'\n> \1\n', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        return html_content
    
    def _detect_code_language(self, code_content: str) -> Optional[str]:
        """Simple code language detection based on content patterns."""
        code_content = code_content.lower().strip()
        
        # SQL patterns (check first as they're most specific)
        if any(pattern in code_content for pattern in ['select ', 'from ', 'where ', 'insert ', 'update ']):
            return 'sql'
        
        # Java patterns (check before Python to avoid conflicts)
        if any(pattern in code_content for pattern in ['public class', 'public static void', 'system.out']):
            return 'java'
        
        # Python patterns
        if any(pattern in code_content for pattern in ['def ', 'import ', 'from ', 'class ', 'if __name__']):
            return 'python'
        
        # JavaScript patterns  
        if any(pattern in code_content for pattern in ['function ', 'var ', 'let ', 'const ', '=>']):
            return 'javascript'
        
        # C/C++ patterns
        if any(pattern in code_content for pattern in ['#include', 'int main', 'printf(', 'cout <<']):
            return 'cpp'
        
        # Shell patterns
        if any(pattern in code_content for pattern in ['#!/bin/', 'echo ', 'grep ', 'awk ', 'sed ']):
            return 'bash'
        
        return None
    
    def _postprocess_markdown(self, markdown: str) -> str:
        """Clean up and enhance markdown output."""
        # Remove excessive whitespace but preserve intentional spacing
        markdown = re.sub(r'\n\s*\n\s*\n+', '\n\n', markdown)
        
        # Fix spacing around code blocks - ensure proper spacing but not excessive
        markdown = re.sub(r'\n+```', '\n\n```', markdown)
        markdown = re.sub(r'```\n\n+', '```\n', markdown)  # Remove extra newlines after opening
        
        # Improve list formatting
        markdown = re.sub(r'\n-\s*\n', '\n- ', markdown)
        
        # Clean up HTML entities that might have been missed
        markdown = html.unescape(markdown)
        
        # Remove trailing whitespace
        lines = [line.rstrip() for line in markdown.split('\n')]
        markdown = '\n'.join(lines).strip()
        
        return markdown
    
    def _fallback_html_processing(self, html_content: str) -> str:
        """Fallback HTML processing when markdownify is not available."""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Convert common elements
            for tag in soup.find_all(['strong', 'b']):
                tag.string = f"**{tag.get_text()}**"
                tag.unwrap()
            
            for tag in soup.find_all(['em', 'i']):
                tag.string = f"*{tag.get_text()}*"
                tag.unwrap()
            
            for tag in soup.find_all('code'):
                tag.string = f"`{tag.get_text()}`"
                tag.unwrap()
            
            for tag in soup.find_all('pre'):
                content = tag.get_text()
                tag.string = f"\n```\n{content}\n```\n"
                tag.unwrap()
            
            # Remove remaining HTML tags and get text
            text = soup.get_text()
            
            # Clean up spacing
            text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
            text = text.strip()
            
            return self.truncate_content(text, "text")
            
        except ImportError:
            logger.warning("BeautifulSoup not available, returning cleaned HTML")
            # Last resort: basic HTML tag removal
            text = re.sub(r'<[^>]+>', '', html_content)
            text = html.unescape(text)
            return self.truncate_content(text, "text")
    
    def truncate_content(self, content: str, content_type: str = "text") -> str:
        """
        Truncate content to maximum length with smart truncation.
        
        Args:
            content: Content to truncate
            content_type: Type of content (text, markdown, html)
            
        Returns:
            Truncated content with appropriate suffix
        """
        if len(content) <= self.max_content_length:
            return content
        
        # Smart truncation: try to break at paragraph boundaries
        truncated = content[:self.max_content_length]
        
        # Find the last complete paragraph/sentence
        if content_type == "markdown":
            # Try to break at paragraph boundary
            last_paragraph = truncated.rfind('\n\n')
            if last_paragraph > self.max_content_length * 0.8:  # If we can save 80%+ of content
                truncated = truncated[:last_paragraph]
        
        # Try to break at sentence boundary
        last_sentence = max(
            truncated.rfind('. '),
            truncated.rfind('.\n'),
            truncated.rfind('! '),
            truncated.rfind('? ')
        )
        
        if last_sentence > self.max_content_length * 0.9:  # If we can save 90%+ of content
            truncated = truncated[:last_sentence + 1]
        
        # Add truncation indicator
        if content_type == "markdown":
            truncated += "\n\n*[Content truncated...]*"
        else:
            truncated += "\n\n[Content truncated...]"
        
        return truncated
    
    def validate_and_clean_response(self, response_data: dict) -> dict:
        """
        Validate and clean API response data.
        
        Args:
            response_data: Raw API response data
            
        Returns:
            Cleaned and validated response data
        """
        if not isinstance(response_data, dict):
            raise ValueError("Response data must be a dictionary")
        
        cleaned = {}
        
        # Standard fields with validation
        if "items" in response_data:
            items = response_data["items"]
            if isinstance(items, list):
                cleaned["items"] = [self._clean_item(item) for item in items if item]
            else:
                cleaned["items"] = []
        
        # Numeric fields with validation
        for field in ["total", "quota_max", "quota_remaining", "page", "pagesize"]:
            if field in response_data:
                try:
                    value = int(response_data[field])
                    cleaned[field] = max(0, value)  # Ensure non-negative
                except (ValueError, TypeError):
                    cleaned[field] = 0
        
        # Boolean fields
        for field in ["has_more"]:
            if field in response_data:
                cleaned[field] = bool(response_data[field])
        
        # Copy other valid fields
        for field in ["backoff", "error_id", "error_message", "error_name"]:
            if field in response_data:
                cleaned[field] = response_data[field]
        
        return cleaned
    
    def _clean_item(self, item: dict) -> dict:
        """Clean individual item from API response."""
        if not isinstance(item, dict):
            return {}
        
        cleaned = {}
        
        # Required fields
        for field in ["question_id", "answer_id", "title", "body"]:
            if field in item:
                cleaned[field] = str(item[field]) if item[field] is not None else ""
        
        # Numeric fields
        for field in ["score", "view_count", "answer_count", "creation_date", "last_activity_date"]:
            if field in item:
                try:
                    cleaned[field] = int(item[field])
                except (ValueError, TypeError):
                    cleaned[field] = 0
        
        # Boolean fields
        for field in ["is_accepted", "has_more"]:
            if field in item:
                cleaned[field] = bool(item[field])
        
        # Array fields
        if "tags" in item:
            tags = item["tags"]
            if isinstance(tags, list):
                cleaned["tags"] = [str(tag) for tag in tags if tag]
            else:
                cleaned["tags"] = []
        
        # Nested objects
        if "owner" in item and isinstance(item["owner"], dict):
            owner = item["owner"]
            cleaned["owner"] = {
                "display_name": str(owner.get("display_name", "Unknown")),
                "user_id": owner.get("user_id"),
                "reputation": owner.get("reputation", 0)
            }
        
        # URLs and links
        for field in ["link", "share_link"]:
            if field in item:
                link = item[field]
                if isinstance(link, str) and (link.startswith("http://") or link.startswith("https://")):
                    cleaned[field] = link
        
        return cleaned


class MCPErrorHandler:
    """Standardized error handling for MCP responses."""
    
    ERROR_CATEGORIES = {
        "validation": "Input validation error",
        "authentication": "Authentication error", 
        "rate_limit": "Rate limit error",
        "network": "Network error",
        "api": "StackOverflow API error",
        "internal": "Internal server error",
        "not_found": "Resource not found"
    }
    
    @classmethod
    def create_error_response(cls, 
                            error: Union[str, Exception], 
                            category: str = "internal",
                            details: Optional[dict] = None,
                            user_friendly: bool = True) -> dict:
        """
        Create standardized MCP error response.
        
        Args:
            error: Error message or exception
            category: Error category from ERROR_CATEGORIES
            details: Additional error details
            user_friendly: Whether to include user-friendly error message
            
        Returns:
            Standardized MCP error response
        """
        error_msg = str(error)
        
        # Create base error response
        response = {
            "content": [
                {
                    "type": "text",
                    "text": cls._format_error_message(error_msg, category, user_friendly)
                }
            ]
        }
        
        # Add error metadata if details provided
        if details:
            response["_error_details"] = {
                "category": category,
                "message": error_msg,
                "details": details,
                "timestamp": time.time()
            }
        
        # Log error for debugging
        logger.error(f"MCP Error [{category}]: {error_msg}", extra=details or {})
        
        return response
    
    @classmethod
    def _format_error_message(cls, error_msg: str, category: str, user_friendly: bool) -> str:
        """Format error message for user display."""
        category_desc = cls.ERROR_CATEGORIES.get(category, "Unknown error")
        
        if user_friendly:
            if category == "validation":
                return f"❌ **Input Error:** {error_msg}"
            elif category == "authentication":
                return f"🔐 **Authentication Error:** {error_msg}\n\n*Check your API key configuration.*"
            elif category == "rate_limit":
                return f"⏱️ **Rate Limit:** {error_msg}\n\n*Please wait before making more requests.*"
            elif category == "network":
                return f"🌐 **Network Error:** {error_msg}\n\n*Check your internet connection.*"
            elif category == "api":
                return f"📡 **API Error:** {error_msg}\n\n*StackOverflow API returned an error.*"
            elif category == "not_found":
                return f"🔍 **Not Found:** {error_msg}"
            else:
                return f"⚠️ **Error:** {error_msg}"
        else:
            return f"Error [{category}]: {error_msg}"
    
    @classmethod
    def handle_api_error(cls, response_data: dict) -> Optional[dict]:
        """
        Check for API errors in response and return error response if found.
        
        Args:
            response_data: API response data
            
        Returns:
            Error response dict if error found, None otherwise
        """
        if not isinstance(response_data, dict):
            return None
        
        # Check for explicit API errors
        if "error_id" in response_data or "error_message" in response_data:
            error_id = response_data.get("error_id", "unknown")
            error_msg = response_data.get("error_message", "Unknown API error")
            error_name = response_data.get("error_name", "api_error")
            
            # Categorize the error
            if error_id in [400, 401, 403]:
                category = "authentication"
            elif error_id == 429:
                category = "rate_limit"
            elif error_id == 404:
                category = "not_found"
            else:
                category = "api"
            
            return cls.create_error_response(
                error_msg, 
                category=category,
                details={
                    "error_id": error_id,
                    "error_name": error_name,
                    "api_response": response_data
                }
            )
        
        return None


class StackOverflowClient:
    """Client for interacting with StackOverflow API."""
    
    def __init__(self, config: ServerConfig):
        """Initialize the StackOverflow API client."""
        self.config = config
        self.base_url = config.stackoverflow_base_url.rstrip('/')
        self.api_key = config.stackoverflow_api_key
        self.session = httpx.AsyncClient(timeout=30.0)
        
        # Rate limiting and authentication state
        self.rate_limit_state = RateLimitState()
        self.auth_state = AuthenticationState()
        
        # Request queue system for auto-switching and caching
        self.request_queue = RequestQueue()
        
        # Initialize request cache
        self.cache = RequestCache()
        
        # Content formatter for enhanced output
        self.content_formatter = ContentFormatter(max_content_length=config.max_content_length)
        
        # Error handler for standardized responses
        self.error_handler = MCPErrorHandler()
        
        # Request interval management for rate limiting
        self.min_request_interval = 60.0 / config.max_requests_per_minute
        self.current_request_interval = self.min_request_interval
        self.last_request_time = 0.0
        
        # Auto-switching configuration
        self.auto_switch_enabled = True
        self.current_access_mode = AccessMode.AUTO
        self._request_id_counter = 0
        
        # Override the queue's _execute_request method
        self.request_queue._execute_request = self._execute_queued_request
        
    async def __aenter__(self):
        """Async context manager entry."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.session.aclose()
        await self.request_queue.shutdown()
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        self._request_id_counter += 1
        return f"req_{int(time.time())}_{self._request_id_counter}"
    
    def _should_use_authenticated_access(self, access_mode: AccessMode) -> bool:
        """Determine whether to use authenticated access."""
        if access_mode == AccessMode.AUTHENTICATED:
            return True
        elif access_mode == AccessMode.UNAUTHENTICATED:
            return False
        elif access_mode == AccessMode.AUTO:
            # Auto-switching logic
            if not self.api_key or not self.auth_state.is_authenticated:
                return False
            
            # Check if we're approaching API rate limits
            if self.auth_state.daily_quota_remaining is not None:
                if self.auth_state.daily_quota_remaining < 50:  # Save API quota when low
                    logger.info("API quota low, switching to unauthenticated access")
                    return False
            
            # Check if authenticated API is rate limited but we can try unauthenticated
            if self.rate_limit_state.is_rate_limited:
                logger.info("Authenticated API rate limited, trying unauthenticated access")
                return False
            
            # Default to authenticated if available
            return True
        
        return False
    
    async def _execute_queued_request(self, request: QueuedRequest) -> Dict[str, Any]:
        """Execute a queued request with caching and auto-switching."""
        # Check cache first
        cache_key = request.get_cache_key()
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for request {request.id}")
            return cached_result
        
        # Determine access mode
        use_auth = self._should_use_authenticated_access(request.access_mode)
        
        # Prepare parameters
        params = request.params.copy()
        if use_auth and self.api_key:
            params["key"] = self.api_key
        else:
            # Remove key if switching to unauthenticated
            params.pop("key", None)
        
        logger.debug(f"Executing request {request.id} with {'authenticated' if use_auth else 'unauthenticated'} access")
        
        try:
            # Execute the actual HTTP request
            result = await self._make_raw_request(request.endpoint, params, use_auth)
            
            # Cache successful results
            self.cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            # Try fallback access mode if auto-switching is enabled
            if (request.access_mode == AccessMode.AUTO and 
                self.auto_switch_enabled and 
                use_auth and 
                "rate limit" in str(e).lower()):
                
                logger.warning(f"Authenticated request failed, trying unauthenticated fallback for {request.id}")
                
                # Remove API key and retry
                params.pop("key", None)
                try:
                    result = await self._make_raw_request(request.endpoint, params, False)
                    self.cache.set(cache_key, result)
                    return result
                except Exception as fallback_error:
                    logger.error(f"Fallback request also failed for {request.id}: {fallback_error}")
                    raise
            
            raise
    
    async def _queue_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        priority: RequestPriority = RequestPriority.NORMAL,
        access_mode: AccessMode = AccessMode.AUTO,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Queue a request and wait for result."""
        
        request = QueuedRequest(
            id=self._generate_request_id(),
            endpoint=endpoint,
            params=params,
            priority=priority,
            created_at=time.time(),
            max_retries=max_retries,
            access_mode=access_mode
        )
        
        logger.debug(f"Queueing request {request.id} for {endpoint}")
        
        try:
            future = await self.request_queue.enqueue(request)
            result = await future
            return result
        except Exception as e:
            logger.error(f"Request {request.id} failed: {e}")
            raise
    
    async def validate_api_key(self) -> bool:
        """
        Validate the configured API key by making a test request.
        Returns True if valid, False if invalid or not configured.
        """
        if not self.api_key:
            self.auth_state.set_authentication_status(False, "No API key configured")
            return False
        
        logger.info("Validating StackOverflow API key...")
        
        try:
            # Make a simple request to test the API key
            params = {
                "key": self.api_key,
                "site": "stackoverflow",
                "pagesize": 1,
                "filter": "default"
            }
            
            url = f"{self.base_url}/questions"
            response = await self.session.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for API errors
                if "error_id" in data:
                    error_msg = data.get("error_message", "Unknown API error")
                    self.auth_state.set_authentication_status(False, f"API key invalid: {error_msg}")
                    return False
                
                # Extract quota information if available
                quota_max = data.get("quota_max")
                quota_remaining = data.get("quota_remaining")
                
                if quota_max is not None or quota_remaining is not None:
                    self.auth_state.update_quota_info(quota_max, quota_remaining)
                    logger.info(f"API quota: {quota_remaining}/{quota_max} remaining")
                
                self.auth_state.set_authentication_status(True)
                logger.info("API key validation successful")
                return True
                
            elif response.status_code == 400:
                # Try to parse error response
                try:
                    data = response.json()
                    error_msg = data.get("error_message", f"HTTP {response.status_code}")
                except:
                    error_msg = f"HTTP {response.status_code}"
                
                self.auth_state.set_authentication_status(False, f"API key validation failed: {error_msg}")
                return False
                
            else:
                self.auth_state.set_authentication_status(False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"API key validation error: {e}")
            self.auth_state.set_authentication_status(False, f"Validation error: {str(e)}")
            return False
    
    def get_authentication_status(self) -> Dict[str, Any]:
        """Get current authentication status for monitoring."""
        return {
            "api_key_configured": bool(self.api_key),
            "is_authenticated": self.auth_state.is_authenticated,
            "api_key_valid": self.auth_state.api_key_valid,
            "authentication_tested": self.auth_state.authentication_tested,
            "authentication_error": self.auth_state.authentication_error,
            "daily_quota": self.auth_state.daily_quota,
            "daily_quota_remaining": self.auth_state.daily_quota_remaining,
            "last_validation_time": self.auth_state.last_validation_time
        }
    
    async def _advanced_rate_limit_check(self) -> None:
        """Enhanced rate limit checking with dynamic adjustment."""
        # Check for rate limit recovery
        self.rate_limit_state.check_recovery()
        
        # If currently rate limited, wait
        if self.rate_limit_state.is_rate_limited:
            wait_time = self.rate_limit_state.backoff_until - time.time()
            if wait_time > 0:
                logger.info(f"Rate limited, waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
                self.rate_limit_state.check_recovery()
        
        # Dynamic request interval based on remaining quota
        if self.rate_limit_state.remaining_requests is not None:
            if self.rate_limit_state.remaining_requests < 10:
                # Slow down when approaching limits
                extra_delay = (10 - self.rate_limit_state.remaining_requests) * 0.5
                logger.debug(f"Applying extra delay: {extra_delay}s due to low quota")
                await asyncio.sleep(extra_delay)
    
    async def _rate_limit_check(self) -> None:
        """Check and enforce rate limiting."""
        # First run enhanced rate limit check
        await self._advanced_rate_limit_check()
        
        current_time = time.time()
        
        # Reset window if more than 60 seconds have passed
        if current_time - self.last_request_time >= self.min_request_interval:
            self.current_request_interval = self.min_request_interval
            self.last_request_time = current_time
        
        # Check if we've exceeded the rate limit
        if current_time - self.last_request_time < self.current_request_interval:
            sleep_time = self.current_request_interval - (current_time - self.last_request_time)
            if sleep_time > 0:
                logger.warning(f"Client rate limit reached, sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
                self.current_request_interval = self.min_request_interval
                self.last_request_time = time.time()
        
        # Ensure minimum delay between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.current_request_interval:
            await asyncio.sleep(self.current_request_interval - time_since_last)
        
        self.last_request_time = time.time()
    
    async def _make_raw_request(self, endpoint: str, params: Dict[str, Any], use_auth: bool = True) -> Dict[str, Any]:
        """Make a raw request to the StackOverflow API with enhanced rate limiting."""
        await self._rate_limit_check()
        
        # Add common parameters
        params.setdefault("site", "stackoverflow")
        
        url = f"{self.base_url}/{endpoint}"
        
        logger.info(f"Making request to {url} with params: {params}")
        
        try:
            response = await self.session.get(url, params=params)
            
            # Update rate limit state from headers
            self.rate_limit_state.update_from_headers(dict(response.headers))
            
            # Handle rate limiting responses
            if response.status_code == 429:
                logger.warning(f"Received 429 Too Many Requests from StackOverflow API")
                
                # Try to get retry-after header
                retry_after = response.headers.get('retry-after')
                if retry_after:
                    try:
                        backoff_seconds = float(retry_after)
                        logger.info(f"API provided retry-after: {backoff_seconds}s")
                        self.rate_limit_state.set_rate_limited(backoff_seconds)
                    except ValueError:
                        self.rate_limit_state.set_rate_limited()
                else:
                    self.rate_limit_state.set_rate_limited()
                
                # Return friendly error
                raise Exception(f"StackOverflow API rate limit exceeded. Please wait {self.rate_limit_state.current_backoff:.0f} seconds before retrying.")
            
            response.raise_for_status()
            
            data = response.json()
            
            # Update authentication state from successful API response
            if use_auth and self.api_key and not self.auth_state.authentication_tested:
                # If we have an API key and haven't tested it yet, mark as valid
                quota_max = data.get("quota_max")
                quota_remaining = data.get("quota_remaining")
                
                if quota_max is not None or quota_remaining is not None:
                    self.auth_state.update_quota_info(quota_max, quota_remaining)
                    self.auth_state.set_authentication_status(True)
                    logger.info(f"API key validated through successful request. Quota: {quota_remaining}/{quota_max}")
                else:
                    # Even without quota info, successful authenticated request means valid key
                    self.auth_state.set_authentication_status(True)
                    logger.info("API key validated through successful request")
            elif use_auth and self.api_key:
                # Update quota info on subsequent requests
                quota_max = data.get("quota_max")
                quota_remaining = data.get("quota_remaining")
                if quota_max is not None or quota_remaining is not None:
                    self.auth_state.update_quota_info(quota_max, quota_remaining)
            
            # Check for API errors
            if "error_id" in data:
                error_msg = data.get("error_message", "Unknown API error")
                logger.error(f"StackOverflow API error: {error_msg}")
                
                # Check if it's an authentication error
                if "key" in error_msg.lower() or "authentication" in error_msg.lower() or "unauthorized" in error_msg.lower():
                    logger.warning("API error indicates authentication failure")
                    self.auth_state.set_authentication_status(False, f"Authentication error: {error_msg}")
                
                # Check if it's a rate limit error
                if "throttle" in error_msg.lower() or "quota" in error_msg.lower():
                    logger.warning("API error indicates rate limiting")
                    self.rate_limit_state.set_rate_limited()
                
                raise Exception(f"StackOverflow API error: {error_msg}")
            
            # Log successful request
            if self.rate_limit_state.remaining_requests is not None:
                logger.debug(f"Request successful, {self.rate_limit_state.remaining_requests} requests remaining")
            
            return data
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            
            # Handle other rate limiting status codes
            if e.response.status_code in [502, 503, 504]:
                logger.warning(f"Server error {e.response.status_code}, might be overloaded")
                self.rate_limit_state.set_rate_limited(30.0)  # 30 second backoff for server errors
            
            raise Exception(f"HTTP error {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise Exception(f"Request error: {e}")
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limiting status for monitoring."""
        return {
            "is_rate_limited": self.rate_limit_state.is_rate_limited,
            "backoff_until": self.rate_limit_state.backoff_until,
            "current_backoff": self.rate_limit_state.current_backoff,
            "remaining_requests": self.rate_limit_state.remaining_requests,
            "reset_time": self.rate_limit_state.reset_time,
            "requests_this_window": self.current_request_interval,
            "window_start": self.last_request_time
        }
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get request queue status."""
        queue_status = self.request_queue.get_status()
        cache_stats = self.cache.get_stats()
        
        return {
            "queue": queue_status,
            "cache": cache_stats,
            "auto_switch_enabled": self.auto_switch_enabled,
            "current_access_mode": self.current_access_mode.value
        }
    
    async def search_questions(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
        sort: str = "relevance",
        order: str = "desc",
        site: str = "stackoverflow",
        priority: RequestPriority = RequestPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Search for questions using the StackOverflow API.
        
        Args:
            query: Search query string
            page: Page number (1-based)
            page_size: Number of results per page (max 100)
            sort: Sort order (relevance, activity, votes, creation)
            order: Sort direction (desc, asc)
            site: Site name to search in (default: stackoverflow)
            priority: Request priority for queue management
            
        Returns:
            Dictionary containing search results
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")
        
        # Validate parameters
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        
        valid_sorts = ["relevance", "activity", "votes", "creation"]
        if sort not in valid_sorts:
            sort = "relevance"
        
        valid_orders = ["desc", "asc"]
        if order not in valid_orders:
            order = "desc"
        
        # Use search/advanced endpoint with q parameter for keyword search
        params = {
            "q": query.strip(),  # Search query using q parameter
            "site": site.strip(),  # Search on specific site
            "page": page,
            "pagesize": page_size,
            "sort": sort,
            "order": order,
            "filter": "default"  # Include basic question data
        }
        
        logger.info(f"Searching questions with query: '{query}', page: {page}, size: {page_size}")
        
        try:
            result = await self._queue_request("search/advanced", params, priority)
            
            # Log search statistics
            total = result.get("total", 0)
            returned = len(result.get("items", []))
            logger.info(f"Search returned {returned} results out of {total} total")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to search questions: {e}")
            raise
    
    async def search_by_tags(
        self,
        tags: List[str],
        page: int = 1,
        page_size: int = 10,
        sort: str = "activity",
        order: str = "desc",
        site: str = "stackoverflow",
        priority: RequestPriority = RequestPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Search for questions by tags using the StackOverflow API.
        
        Args:
            tags: List of tags to search for
            page: Page number (1-based)
            page_size: Number of results per page (max 100)
            sort: Sort order (activity, votes, creation, relevance)
            order: Sort direction (desc, asc)
            site: Site name to search in (default: stackoverflow)
            priority: Request priority for queue management
            
        Returns:
            Dictionary containing search results
        """
        if not tags:
            raise ValueError("At least one tag is required")
        
        # Validate parameters
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        
        valid_sorts = ["activity", "votes", "creation", "relevance"]
        if sort not in valid_sorts:
            sort = "activity"
        
        valid_orders = ["desc", "asc"]
        if order not in valid_orders:
            order = "desc"
        
        # Join tags with semicolon as required by API
        tagged = ";".join(tag.strip() for tag in tags if tag.strip())
        
        if not tagged:
            raise ValueError("At least one tag is required")
        
        params = {
            "tagged": tagged,
            "site": site.strip(),  # Search on specific site
            "page": page,
            "pagesize": page_size,
            "sort": sort,
            "order": order,
            "filter": "default"
        }
        
        logger.info(f"Searching questions with tags: {tagged}, page: {page}, size: {page_size}")
        
        try:
            result = await self._queue_request("search/advanced", params, priority)
            
            # Log search statistics
            total = result.get("total", 0)
            returned = len(result.get("items", []))
            logger.info(f"Tag search returned {returned} results out of {total} total")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to search questions by tags: {e}")
            raise
    
    async def get_question_details(
        self, 
        question_id: int, 
        include_answers: bool = True,
        priority: RequestPriority = RequestPriority.HIGH
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific question.
        
        Args:
            question_id: The question ID
            include_answers: Whether to include answers (default: True)
            priority: Request priority for queue management
            
        Returns:
            Dictionary containing question details and optionally answers
        """
        # Use default filter to get basic details with body
        params = {
            "filter": "withbody"  # Standard filter that includes question body
        }
        
        logger.info(f"Getting details for question {question_id} (include_answers: {include_answers})")
        
        try:
            result = await self._queue_request(f"questions/{question_id}", params, priority)
            
            if not result.get("items"):
                raise Exception(f"Question {question_id} not found")
            
            question = result["items"][0]
            
            # Get answers if requested
            if include_answers:
                try:
                    answers_params = {
                        "filter": "withbody",  # Standard filter for answers
                        "sort": "votes",
                        "order": "desc"
                    }
                    answers_result = await self._queue_request(
                        f"questions/{question_id}/answers", 
                        answers_params,
                        priority
                    )
                    question["answers"] = answers_result.get("items", [])
                    logger.info(f"Retrieved {len(question['answers'])} answers for question {question_id}")
                except Exception as e:
                    logger.warning(f"Failed to get answers for question {question_id}: {e}")
                    question["answers"] = []
            
            return question
            
        except Exception as e:
            logger.error(f"Failed to get question details: {e}")
            raise
    
    def _convert_html_to_markdown(self, html_content: str) -> str:
        """
        Convert HTML content to Markdown format using enhanced formatter.
        
        Args:
            html_content: HTML content to convert
            
        Returns:
            Markdown formatted content
        """
        return self.content_formatter.convert_html_to_markdown(html_content) 