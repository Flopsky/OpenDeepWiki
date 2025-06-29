# Monitor module for performance tracking
from .langfuse import (
    trace,
    generate_trace_id,
    flush_and_cleanup,
    get_langfuse_context,
    update_langfuse_context,
    LANG_DISABLE_TRACING
)

__all__ = [
    'trace',
    'generate_trace_id', 
    'flush_and_cleanup',
    'get_langfuse_context',
    'update_langfuse_context',
    'LANG_DISABLE_TRACING'
]

# Utility functions for common patterns
def create_trace_context(operation_name: str = "pipeline") -> str:
    """Create a new trace context for a pipeline operation."""
    return generate_trace_id()

def should_trace() -> bool:
    """Check if tracing is enabled."""
    return not LANG_DISABLE_TRACING
