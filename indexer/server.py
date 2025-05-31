from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
from .service import ClassifierService
import traceback

app = FastAPI(title="Indexer Service", description="File classification and summarization service")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the classifier service
classifier_service = ClassifierService()

class ClassificationRequest(BaseModel):
    folder_path: str
    batch_size: int = 50
    max_workers: int = 10
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

class ClassificationResponse(BaseModel):
    result: dict

@app.post("/score", response_model=ClassificationResponse)
async def classify_files(request: ClassificationRequest):
    """
    Classify files in the given folder path.
    This endpoint replaces the old promptflow file_classification service.
    """
    try:
        logger.info(f"Received classification request for folder: {request.folder_path}")
        
        result = await classifier_service.run_pipeline(
            folder_path=request.folder_path,
            batch_size=request.batch_size,
            max_workers=request.max_workers,
            GEMINI_API_KEY=request.GEMINI_API_KEY,
            ANTHROPIC_API_KEY=request.ANTHROPIC_API_KEY,
            OPENAI_API_KEY=request.OPENAI_API_KEY
        )
        
        logger.info("Classification completed successfully")
        return ClassificationResponse(result=result)
        
    except Exception as e:
        logger.error(f"Error during classification: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "indexer"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002) 