from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging
from .service import Librairie_Service
import traceback

app = FastAPI(title="Libraire Service", description="Documentation retrieval and response generation service")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the libraire service
repo_chat = Librairie_Service()

class LibraireRequest(BaseModel):
    repository_name: str
    cache_id: str
    documentation: Dict[str, Any]
    user_problem: str
    documentation_md: Dict[str, Any]
    config: Dict[str, Any]
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

class LibraireResponse(BaseModel):
    libraire_response: str

@app.post("/score", response_model=LibraireResponse)
async def process_libraire_request(request: LibraireRequest):
    """
    Process a libraire request to generate documentation-based responses.
    This endpoint replaces the old promptflow libraire service.
    """
    try:
        logger.info(f"Received libraire request for repository: {request.repository_name}")
        
        result = repo_chat.run_pipeline(
            repository_name=request.repository_name,
            cache_id=request.cache_id,
            documentation=request.documentation,
            user_problem=request.user_problem,
            documentation_md=request.documentation_md,
            config_input=request.config,
            GEMINI_API_KEY=request.GEMINI_API_KEY
        )
        
        logger.info("Libraire processing completed successfully")
        return LibraireResponse(libraire_response=result)
        
    except Exception as e:
        logger.error(f"Error during libraire processing: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Libraire processing failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "repo_chat"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001) 