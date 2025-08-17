import functools
import json
import os
import traceback
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional, Set
import uuid
import asyncio
import inspect
from langfuse import Langfuse
import threading
import time
from collections import deque
import logging

import dotenv
dotenv.load_dotenv()

logger = logging.getLogger(__name__)

LANG_DISABLE_TRACING = os.getenv("LANG_DISABLE_TRACING", "true").lower() == "true"
LANGFUSE_BATCH_SIZE = int(os.getenv("LANGFUSE_BATCH_SIZE", "50"))
LANGFUSE_FLUSH_INTERVAL = int(os.getenv("LANGFUSE_FLUSH_INTERVAL", "5"))

# Context variables for managing tracing context
langfuse_span: ContextVar[Optional[Any]] = ContextVar("langfuse_span", default=None)
langfuse_metadata: ContextVar[Optional[Dict]] = ContextVar(
    "langfuse_metadata", default=None
)

# Module-level singleton pattern for asyncio
_langfuse_client: Optional[Langfuse] = None
_client_lock = threading.Lock()
_auth_checked = False

# Batch processing for spans
_span_queue = deque()
_flush_task: Optional[asyncio.Task] = None
_flush_lock = threading.Lock()

# Cache for serializable type checks
_serializable_types = {str, int, float, bool, type(None), list, dict, tuple}
_known_serializable: Set[type] = set()
_known_non_serializable: Set[type] = set()


def get_langfuse_client() -> Langfuse:
    """Initialize and return the Langfuse client. Optimized with caching."""
    global _langfuse_client, _auth_checked
    
    if _langfuse_client is None:
        with _client_lock:
            if _langfuse_client is None:
                _langfuse_client = Langfuse()
    
    # Only check auth once, not on every access
    if not _auth_checked:
        with _client_lock:
            if not _auth_checked:
                try:
                    _langfuse_client.auth_check()
                    _auth_checked = True
                except Exception as e:
                    logger.warning(f"Langfuse auth check failed: {e}")
                    # Continue without failing - tracing will be disabled
    
    return _langfuse_client


def get_langfuse_context() -> Dict[str, Any]:
    """Get the current Langfuse context including span and metadata."""
    return {
        "span": langfuse_span.get(),
        "metadata": langfuse_metadata.get(),
    }


def generate_trace_id() -> str:
    """Generate a random unique trace ID suitable for use with Langfuse."""
    return str(uuid.uuid4())


def update_langfuse_context(
    span: Optional[Any] = None, metadata: Optional[Dict] = None
) -> None:
    """Update the current Langfuse context with new values."""
    if span is not None:
        langfuse_span.set(span)
    if metadata is not None:
        langfuse_metadata.set(metadata)


def is_json_serializable_fast(obj: Any) -> bool:
    """Fast check if an object is JSON serializable using type caching."""
    obj_type = type(obj)
    
    # Check cache first
    if obj_type in _known_serializable:
        return True
    if obj_type in _known_non_serializable:
        return False
    
    # Quick check for basic types
    if obj_type in _serializable_types:
        _known_serializable.add(obj_type)
        return True
    
    # For complex objects, do a limited check
    try:
        # Only check a small sample for performance
        if hasattr(obj, '__dict__') and len(str(obj)) > 1000:
            # Skip very large objects to avoid performance hit
            _known_non_serializable.add(obj_type)
            return False
        
        # Fast serialization test for smaller objects
        json.dumps(obj, default=str)
        _known_serializable.add(obj_type)
        return True
    except (TypeError, ValueError, OverflowError):
        _known_non_serializable.add(obj_type)
        return False


def _filter_serializable_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Filter out non-JSON-serializable inputs with performance optimization."""
    result = {}
    for k, v in inputs.items():
        if is_json_serializable_fast(v):
            result[k] = v
        else:
            # Keep a simple representation for debugging
            result[k] = f"<{type(v).__name__}: non-serializable>"
    return result


async def _flush_spans():
    """Background task to flush spans in batches."""
    while True:
        try:
            await asyncio.sleep(LANGFUSE_FLUSH_INTERVAL)
            
            if _span_queue:
                with _flush_lock:
                    # Process up to BATCH_SIZE spans
                    batch = []
                    for _ in range(min(LANGFUSE_BATCH_SIZE, len(_span_queue))):
                        if _span_queue:
                            batch.append(_span_queue.popleft())
                
                # Flush batch asynchronously
                if batch:
                    await asyncio.get_event_loop().run_in_executor(
                        None, _flush_span_batch, batch
                    )
        except Exception as e:
            logger.error(f"Error in span flushing: {e}")


def _flush_span_batch(spans):
    """Flush a batch of spans synchronously."""
    for span_data in spans:
        try:
            span = span_data['span']
            if span_data.get('result') is not None:
                span.update(output=span_data['result'])
            if span_data.get('error'):
                span.update(
                    status_message=span_data['error'], 
                    level="ERROR"
                )
            span.end()
        except Exception as e:
            logger.error(f"Error flushing span: {e}")


def _ensure_flush_task():
    """Ensure the background flush task is running."""
    global _flush_task
    if _flush_task is None or _flush_task.done():
        try:
            loop = asyncio.get_event_loop()
            _flush_task = loop.create_task(_flush_spans())
        except RuntimeError:
            # No event loop running, skip background flushing
            pass


def _create_trace_and_span_async(
    langfuse: Langfuse, inputs: Dict[str, Any], name: str, file_name: str, trace_id: str
) -> Any:
    """Create a new trace and span with minimal blocking."""
    try:
        trace = langfuse.trace(id=trace_id, name=file_name)
        return trace.span(name=name, input=inputs)
    except Exception as e:
        logger.error(f"Error creating trace/span: {e}")
        return None


def trace(func: Callable) -> Callable:
    """Optimized decorator to trace function execution with Langfuse observability."""
    
    # Check if the function is async
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            if LANG_DISABLE_TRACING:
                return await func(*args, **kwargs)
            
            # Fast path: minimal overhead when tracing is enabled
            trace_id = kwargs.get("trace_id")
            if not trace_id:
                return await func(*args, **kwargs)
            
            # Ensure flush task is running
            _ensure_flush_task()
            
            # Use executor to avoid blocking the event loop
            langfuse = get_langfuse_client()
            if not langfuse:
                return await func(*args, **kwargs)
            
            # Filter inputs efficiently
            func_inputs = _filter_serializable_inputs(kwargs)
            func_file_name = func.__code__.co_filename
            
            # Create span asynchronously
            span = await asyncio.get_event_loop().run_in_executor(
                None, 
                _create_trace_and_span_async,
                langfuse, func_inputs, func.__name__, func_file_name, trace_id
            )
            
            if not span:
                return await func(*args, **kwargs)
            
            update_langfuse_context(span=span)
            
            result = None
            error = None
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                stacktrace = traceback.format_exc()
                error = f"{type(e).__name__}: {str(e)}\n{stacktrace}"
                raise
            finally:
                # Queue span for batch processing instead of immediate flush
                span_data = {
                    'span': span,
                    'result': result,
                    'error': error
                }
                
                with _flush_lock:
                    _span_queue.append(span_data)
                
                update_langfuse_context(span=None)

        return async_wrapper
    else:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if LANG_DISABLE_TRACING:
                return func(*args, **kwargs)
            
            trace_id = kwargs.get("trace_id")
            if not trace_id:
                return func(*args, **kwargs)
            
            langfuse = get_langfuse_client()
            if not langfuse:
                return func(*args, **kwargs)
            
            # Filter inputs efficiently
            func_inputs = _filter_serializable_inputs(kwargs)
            func_file_name = func.__code__.co_filename
            
            # Create span
            span = _create_trace_and_span_async(
                langfuse, func_inputs, func.__name__, func_file_name, trace_id
            )
            
            if not span:
                return func(*args, **kwargs)
            
            update_langfuse_context(span=span)
            
            result = None
            error = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                stacktrace = traceback.format_exc()
                error = f"{type(e).__name__}: {str(e)}\n{stacktrace}"
                raise
            finally:
                # For sync functions, end span immediately
                try:
                    if result is not None:
                        span.update(output=result)
                    if error:
                        span.update(status_message=error, level="ERROR")
                    span.end()
                except Exception as e:
                    logger.error(f"Error ending span: {e}")
                finally:
                    update_langfuse_context(span=None)

        return wrapper


# Cleanup function for graceful shutdown
async def flush_and_cleanup():
    """Flush all pending spans and cleanup resources."""
    global _flush_task
    
    # Flush remaining spans
    if _span_queue:
        with _flush_lock:
            remaining_spans = list(_span_queue)
            _span_queue.clear()
        
        if remaining_spans:
            await asyncio.get_event_loop().run_in_executor(
                None, _flush_span_batch, remaining_spans
            )
    
    # Cancel flush task
    if _flush_task and not _flush_task.done():
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
