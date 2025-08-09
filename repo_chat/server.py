from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import logging
from .service import Librairie_Service
import traceback
import asyncio

app = FastAPI(title="Libraire Service", description="Documentation retrieval and response generation service")

# Configure logging
# Use uvicorn's structured logs in prod; keep INFO level
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
    model_name: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

class MultiRepoRequest(BaseModel):
    user_problem: str
    target_repositories: List[str]
    repository_data: Dict[str, Dict[str, Any]]  # repo_name -> {cache_id, documentation, documentation_md, config}
    model_name: str = ""
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
        
        # Offload blocking pipeline to a thread to avoid blocking the event loop
        result = await asyncio.to_thread(
            repo_chat.run_pipeline,
            request.repository_name,
            request.cache_id,
            request.documentation,
            request.user_problem,
            request.documentation_md,
            request.config,
            request.GEMINI_API_KEY,
            request.ANTHROPIC_API_KEY,
            request.OPENAI_API_KEY,
            request.model_name,
        )
        
        logger.info("Libraire processing completed successfully")
        return LibraireResponse(libraire_response=result)
        
    except Exception as e:
        logger.error(f"Error during libraire processing: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Libraire processing failed: {str(e)}")

@app.post("/multi_repo_score", response_model=LibraireResponse)
async def process_multi_repo_request(request: MultiRepoRequest):
    """
    Process a multi-repository request to generate documentation-based responses.
    This endpoint handles queries across multiple repositories simultaneously.
    Uses the new pipeline that processes each repo individually for context retrieval
    but makes only one call to the Final Response Generator.
    """
    try:
        logger.info(f"Received multi-repo request for repositories: {request.target_repositories}")
        
        if not request.target_repositories or not request.repository_data:
            raise HTTPException(status_code=400, detail="No repositories provided for multi-repo query")
        
        # Filter target repositories to only include those with available data
        available_repos = [repo for repo in request.target_repositories if repo in request.repository_data]
        
        if not available_repos:
            raise HTTPException(status_code=400, detail="No repository data available for target repositories")
        
        logger.info(f"Processing repositories: {available_repos}")
        
        # Prepare repository data in the format expected by run_multi_repo_pipeline
        repositories_data = {}
        for repo_name in available_repos:
            repo_data = request.repository_data[repo_name]
            repositories_data[repo_name] = {
                "cache_id": repo_data["cache_id"],
                "documentation": repo_data["documentation"],
                "documentation_md": repo_data["documentation_md"],
                "config": repo_data["config"]
            }
        
        # Use the new multi-repository pipeline that makes only one call to Final Response Generator
        logger.info(f"Calling multi-repository pipeline with {len(repositories_data)} repositories")
        
        # Offload blocking multi-repo pipeline to a thread
        aggregated_response = await asyncio.to_thread(
            repo_chat.run_multi_repo_pipeline,
            repositories_data,
            request.user_problem,
            request.GEMINI_API_KEY,
            request.ANTHROPIC_API_KEY,
            request.OPENAI_API_KEY,
            request.model_name,
        )
        
        logger.info("Multi-repo processing completed successfully")
        return LibraireResponse(libraire_response=aggregated_response)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error during multi-repo processing: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Multi-repo processing failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "repo_chat"}

if __name__ == "__main__":
    import uvicorn
    # Use faster loop/http if available
    uvicorn.run(app, host="0.0.0.0", port=8001, loop="uvloop", http="httptools")