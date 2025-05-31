import os
import google.generativeai as genai
from google.generativeai import caching
import google.api_core.exceptions as exceptions
import datetime
import requests
import subprocess
from pathlib import Path
from typing import Optional
import json
from urllib.parse import urlparse
import time
import hashlib
import shutil
import tempfile
import zipfile
import traceback
import json
from typing import List, Tuple, Dict

import dotenv
import os

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


dotenv.load_dotenv()
CONTEXT_CACHING_RETRIVER = os.getenv("CONTEXT_CACHING_RETRIVER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Default configuration with environment variable
genai.configure(api_key=GEMINI_API_KEY)

# Function to configure API with a specific key
def configure_gemini_api(api_key=None):
    """Configure Gemini API with a specific key or use the environment variable"""
    if api_key:
        genai.configure(api_key=api_key)
    else:
        genai.configure(api_key=GEMINI_API_KEY)


def clone_github_repo(folder_path: str, repo_url: str) -> Optional[str]:
    """
    Clone a GitHub repository into a specified folder or return path if already cloned.

    Args:
        folder_path (str): The path where the repository should be cloned
        repo_url (str): The GitHub repository URL (e.g., 'https://github.com/username/repo')

    Returns:
        Optional[str]: The path to the cloned repository if successful, None if failed

    Raises:
        ValueError: If the inputs are invalid
        subprocess.CalledProcessError: If the git clone operation fails
    """
    # Validate inputs
    if not folder_path or not repo_url:
        raise ValueError("Both folder_path and repo_url must be provided")

    # Parse the repository URL to get the repository name
    parsed_url = urlparse(repo_url.rstrip("/"))
    if not parsed_url.path:
        raise ValueError("Invalid GitHub repository URL")

    # Extract repository name from the URL path
    # Handle both 'github.com/owner/repo' and 'github.com/owner/repo.git'
    path_parts = parsed_url.path.strip("/").split("/")
    if len(path_parts) != 2:
        raise ValueError("Invalid GitHub repository URL format")

    repo_name = path_parts[1].replace(".git", "")

    # Create the target directory if it doesn't exist
    folder_path = Path(folder_path).resolve()
    folder_path.mkdir(parents=True, exist_ok=True)

    # Generate the full path where the repository will be cloned
    repo_path = folder_path / repo_name

    # If repository already exists and has .git folder, return its path
    logger.info(f"Repository path: {repo_path}")
    if repo_path.exists() or (repo_path / ".git").exists():
        return str(repo_path)

    try:
        # Check if git is installed
        subprocess.run(["git", "--version"], check=True, capture_output=True)

        # Construct the git URL
        git_url = f"https://github.com/{path_parts[0]}/{path_parts[1]}.git"

        # Clone the repository
        subprocess.run(
            ["git", "clone", git_url, str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )

        # Verify the repository was cloned successfully
        if not (repo_path / ".git").exists():
            raise subprocess.CalledProcessError(1, "git clone")

        return str(repo_path)

    except subprocess.CalledProcessError as e:
        logger.error(f"Error cloning repository: {e}")
        if e.stderr:
            logger.error(f"Git error message: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None


def create_cache(display_name: str, documentation: str, system_prompt: str, gemini_api_key=None):
    # Configure Gemini API with the provided key or use the default
    configure_gemini_api(gemini_api_key)
    
    # Delete old caches with the same display name
    max_retries = 3
    retry_delay = 2 # seconds
    cache_list = None
    for attempt in range(max_retries):
        try:
            cache_list = caching.CachedContent.list()
            logger.info(f"Successfully listed caches on attempt {attempt + 1}")
            break # Success, exit loop
        except exceptions.ServiceUnavailable as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed to list caches: {e}. Retrying in {retry_delay}s...")
            if attempt + 1 == max_retries:
                logger.error("Max retries reached for listing caches. Raising error.")
                raise # Re-raise the last exception if max retries reached
            time.sleep(retry_delay)
        except Exception as e: # Catch other potential exceptions during list
            logger.error(f"Unexpected error listing caches on attempt {attempt + 1}: {e}")
            raise # Re-raise unexpected errors immediately

    if cache_list is not None:
        logger.info(f"Result of caching.CachedContent.list(): {cache_list}")
        logger.info(f"Type of cache_list: {type(cache_list)}")
        for cache in cache_list:
            if cache is not None:
                if cache.display_name == display_name:
                    return cache.name
            else:
                logger.warning("Encountered None value while iterating through cache_list")
    cache = caching.CachedContent.create(
        model=CONTEXT_CACHING_RETRIVER,
        display_name=display_name,  # used to identify the cache
        contents=documentation,
        system_instruction=system_prompt,
        ttl=datetime.timedelta(minutes=30),
    )
    return cache.name


def delete_cache(display_name: str):
    # Delete old display name
    cache_list = caching.CachedContent.list()
    for cache in cache_list:
        if cache.display_name == display_name:
            cache.delete()
            return None


import os


def process_repo_link(link: str, gemini_api_key=None):
    display_name = link.split("/")[-1]
    documentation_path = f"docstrings_json/{display_name}.json"
    documentation_md_path = f"ducomentations_json/{display_name}.json"
    config_path = f"configs_json/{display_name}.json"
    
    # Ensure parent directories exist
    Path(documentation_path).parent.mkdir(parents=True, exist_ok=True)
    Path(documentation_md_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    
    repo_path = clone_github_repo("repository_folder", link)

    system_prompt = """
# Context
You are an expert Software developer with a deep understanding of the software development lifecycle, including requirements gathering, design, implementation, testing, and deployment.
Your task is to answer any question related to the documentation of the python repository repository_name that you have in your context.


""".replace(
        "repository_name", display_name
    )

    # Check if documentation file already exists
    if os.path.exists(documentation_path):
        # Load existing documentation
        with open(documentation_path, "r") as f:
            documentation_json = json.load(f)

        # Load existing config and documentation_md if they exist
        config = None # Initialize config
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f) # Load config as JSON
        documentation_md = None # Initialize documentation_md
        if os.path.exists(documentation_md_path):
            with open(documentation_md_path, "r") as f:
                documentation_md = json.load(f) # Load documentation_md as JSON
    else:
        
        # If file doesn't exist, proceed with repo cloning and documentation generation
        url_file_classification = "http://localhost:8002/score"

        # Get the documentation json from the fastapi documentation generation server
        logger.info(f"Calling classifier service for {repo_path}")
        api_key_preview = gemini_api_key[:5] if gemini_api_key and len(gemini_api_key) >= 5 else gemini_api_key
        logger.info(f"Using GEMINI_API_KEY: {api_key_preview}... (length: {len(gemini_api_key) if gemini_api_key else 0})")
        
        payload = {
            "folder_path": str(repo_path), 
            "batch_size": 50,
            "max_workers": 10,
            "GEMINI_API_KEY": gemini_api_key,
            "ANTHROPIC_API_KEY": "",
            "OPENAI_API_KEY": ""
        }
        
        response = requests.post(url_file_classification, json=payload) # Use repo_path directly
        if response.status_code != 200:
            raise Exception("Failed to get documentation from the server.")
        response_data = response.json()
        response = response_data["result"]

        documentation_json = {"documentation": response["documentation"]}
        documentation_md_json = {"documentation_md": response["documentation_md"]}
        config_json = {"config": response["config"]}

        logger.info(f"Loaded existing documentation_json")
        logger.info(f"Loaded existing config")
        logger.info(f"Loaded existing documentation_md")

        # Save the documentation_json to a file
        with open(documentation_path, "w") as f1:
            json.dump(documentation_json, f1, indent=4)
        # Save the config_json to a file
        with open(documentation_md_path, "w") as f2:
            json.dump(documentation_md_json, f2, indent=4)
        # Save the config_json to a file
        with open(config_path, "w") as f3:
            json.dump(config_json, f3, indent=4)

    documentation_str = str(documentation_json)
    cache_name = create_cache(display_name, documentation_str, system_prompt, gemini_api_key)

    return cache_name


def process_local_folder(repo_path_str: str, gemini_api_key=None):
    """
    Process a local repository folder that has already been copied to the shared volume.

    Args:
        repo_path_str (str): The path to the repository folder within the shared volume.

    Returns:
        str: The name of the created or updated context cache.

    Raises:
        Exception: If processing fails (e.g., classifier service error).
    """
    repo_path = Path(repo_path_str)
    if not repo_path.is_dir():
        raise ValueError(f"Provided path is not a directory: {repo_path_str}")

    display_name = repo_path.name
    documentation_path = Path(f"docstrings_json/{display_name}.json")
    documentation_md_path = Path(f"ducomentations_json/{display_name}.json")
    config_path = Path(f"configs_json/{display_name}.json")

    # Ensure parent directories exist
    documentation_path.parent.mkdir(parents=True, exist_ok=True)
    documentation_md_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)


    system_prompt = """
# Context
You are an expert Software developer with a deep understanding of the software development lifecycle, including requirements gathering, design, implementation, testing, and deployment.
Your task is to answer any question related to the documentation of the python repository repository_name that you have in your context.


""".replace("repository_name", display_name)

    # Check if documentation file already exists
    if documentation_path.exists():
        logger.info(f"Documentation already exists for {display_name}, loading...")
        # Load existing documentation
        with open(documentation_path, "r") as f:
            documentation_json = json.load(f)
        logger.info(f"Loaded existing documentation_json")

    else:
        logger.info(f"Documentation not found for {display_name}, generating...")
        # If file doesn't exist, proceed with documentation generation
        url_file_classification = "http://localhost:8002/score"

        # Get the documentation json from the fastapi documentation generation server
        logger.info(f"Calling classifier service for local folder: {repo_path}")
        api_key_preview = gemini_api_key[:5] if gemini_api_key and len(gemini_api_key) >= 5 else gemini_api_key
        logger.info(f"Using GEMINI_API_KEY: {api_key_preview}... (length: {len(gemini_api_key) if gemini_api_key else 0})")
        
        payload = {
            "folder_path": str(repo_path), 
            "batch_size": 50,
            "max_workers": 10,
            "GEMINI_API_KEY": gemini_api_key,
            "ANTHROPIC_API_KEY": "",
            "OPENAI_API_KEY": ""
        }
        
        try:
            response = requests.post(url_file_classification, json=payload)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to classifier service: {e}")
            raise Exception(f"Failed to connect to classifier service: {e}")
        except Exception as e:
            logger.error(f"Error during classifier request: {e}")
            raise Exception(f"Error during classifier request: {e}")

        if response.status_code != 200:
             logger.error(f"Classifier service returned status {response.status_code}: {response.text}")
             raise Exception(f"Classifier service failed with status {response.status_code}.")

        response_data = response.json()
        logger.info(f"Received response from classifier: {response_data}")
        response = response_data["result"]

        documentation_json = {"documentation": response.get("documentation", {})}
        documentation_md_json = {"documentation_md": response.get("documentation_md", "")}
        config_json = {"config": response.get("config", {})}


        # Save the generated data
        try:
            with open(documentation_path, "w") as f1:
                json.dump(documentation_json, f1, indent=4)
            with open(documentation_md_path, "w") as f2:
                json.dump(documentation_md_json, f2, indent=4)
            with open(config_path, "w") as f3:
                json.dump(config_json, f3, indent=4)
            logger.info(f"Successfully saved generated documentation for {display_name}")
        except IOError as e:
            logger.error(f"Failed to write documentation files: {e}")
            raise Exception(f"Failed to write documentation files: {e}")


    documentation_str = str(documentation_json) # Use the structure containing 'documentation' key
    cache_name = create_cache(display_name, documentation_str, system_prompt, gemini_api_key)
    logger.info(f"Cache created/updated for {display_name}: {cache_name}")

    return cache_name




def get_file_hash(file_path: Path) -> str:
    """Calculate MD5 hash of file content for quick comparison."""
    if not file_path.is_file():
        return ""
    
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error hashing file {file_path}: {e}")
        return ""

def compare_directories(source_dir: Path, target_dir: Path) -> Tuple[List[Path], List[Path], List[Path]]:
    """
    Compare two directories and return lists of changed, added, and deleted files.
    
    Args:
        source_dir: Path to the new directory
        target_dir: Path to the existing directory
        
    Returns:
        Tuple of (changed_files, added_files, deleted_files)
    """
    if not source_dir.exists() or not target_dir.exists():
        raise ValueError(f"Both directories must exist: {source_dir}, {target_dir}")
    
    # Get all files recursively from both directories, excluding .git
    source_files = {p.relative_to(source_dir): get_file_hash(p) 
                    for p in source_dir.rglob('*') 
                    if p.is_file() and '.git' not in p.parts}
    target_files = {p.relative_to(target_dir): get_file_hash(p) 
                    for p in target_dir.rglob('*') 
                    if p.is_file() and '.git' not in p.parts}
    
    # Find changes
    changed_files = [source_dir / p for p, hash_val in source_files.items() 
                    if p in target_files and hash_val != target_files[p]]
    
    # Find additions (files in source not in target)
    added_files = [source_dir / p for p in source_files.keys() if p not in target_files]
    
    # Find deletions (files in target not in source)
    deleted_files = [target_dir / p for p in target_files.keys() if p not in source_files]
    
    return changed_files, added_files, deleted_files

def prepare_temp_folder_for_changes(
    changed_files: List[Path], 
    added_files: List[Path],
    source_dir: Path,
    temp_dir: Path
) -> Dict[str, str]:
    """
    Create a temporary folder with only changed and added files, preserving original paths.
    
    Args:
        changed_files: List of changed file paths
        added_files: List of added file paths
        source_dir: Source directory (new version)
        temp_dir: Temporary directory to create files in
        
    Returns:
        Mapping of temporary file paths to original paths
    """
    # Create mapping of paths
    path_mapping = {}
    
    # Process all changed and added files
    all_files = changed_files + added_files
    for file_path in all_files:
        rel_path = file_path.relative_to(source_dir)
        temp_file_path = temp_dir / rel_path
        
        # Create parent directories if they don't exist
        temp_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy the file
        shutil.copy2(file_path, temp_file_path)
        
        # Add to mapping (storing both original and temporary paths)
        path_mapping[str(temp_file_path)] = str(file_path)
    
    return path_mapping

def process_changed_repository(repo_name: str, new_repo_path: Path, existing_repo_path: Path, gemini_api_key: str, anthropic_api_key: str = None, openai_api_key: str = None) -> str:
    """
    Process a repository that has changes compared to an existing one.
    Only processes changed/added files and updates JSONs accordingly.
    
    Args:
        repo_name: Name of the repository
        new_repo_path: Path to the new repository
        existing_repo_path: Path to the existing repository
        
    Returns:
        cache_name: The name of the cache for the updated repository
    """
    logger.info(f"Detecting changes between existing repo and new repo: {repo_name}")
    
    try:
        # Compare directories to find changes
        changed_files, added_files, deleted_files = compare_directories(new_repo_path, existing_repo_path)
        
        # Log what we found
        logger.info(f"Found {len(changed_files)} changed files, {len(added_files)} added files, and {len(deleted_files)} deleted files")
        
        if not changed_files and not added_files and not deleted_files:
            logger.info(f"No changes detected for {repo_name}, using existing cached data")
            # If no changes, load existing documentation and return existing cache
            documentation_path = Path(f"docstrings_json/{repo_name}.json")
            with open(documentation_path, "r") as f:
                documentation_json = json.load(f)
                
            # Create system prompt and cache with existing data
            system_prompt = """
# Context
You are an expert Software developer with a deep understanding of the software development lifecycle, including requirements gathering, design, implementation, testing, and deployment.
Your task is to answer any question related to the documentation of the python repository repository_name that you have in your context.


""".replace("repository_name", repo_name)
            
            documentation_str = str(documentation_json)
            from src.core.init_repo import create_cache
            cache_name = create_cache(repo_name, documentation_str, system_prompt, gemini_api_key)
            
            return cache_name
        
        # If we have changes, process only those files
        # Create temporary directory within repository_folder instead of system default temp location
        target_base_path = Path("/app/repository_folder")
        temp_dir = target_base_path / f"temp_{repo_name}_changes"
        
        # Ensure the directory doesn't exist (clean state)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        # Create the directory
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create a temporary folder with only changed/added files
            # Replace the old repository with the new one first
            logger.info(f"Replacing content at {existing_repo_path} with content from {new_repo_path}")
            if existing_repo_path.exists(): # Ensure it exists before removing
                shutil.rmtree(existing_repo_path)
            shutil.copytree(new_repo_path, existing_repo_path)
            logger.info(f"Updated repository content at {existing_repo_path}")

            # Replace the old repository with the new one first
            logger.info(f"Replacing content at {existing_repo_path} with content from {new_repo_path}")
            if existing_repo_path.exists(): # Ensure it exists before removing
                shutil.rmtree(existing_repo_path)
            shutil.copytree(new_repo_path, existing_repo_path)
            logger.info(f"Updated repository content at {existing_repo_path}")

            path_mapping = prepare_temp_folder_for_changes(
                changed_files, added_files, new_repo_path, temp_dir
            )
            
            logger.info(f"Created temporary folder with {len(path_mapping)} files for classification at {temp_dir}")
            
            # Call classifier on the updated repository in the shared volume
            url_file_classification = "http://localhost:8002/score"
            logger.info(f"Calling classifier service for updated repo at {existing_repo_path}")
            response = requests.post(
                url_file_classification, json={
                    "folder_path": str(existing_repo_path), 
                    "batch_size": 50,
                    "max_workers": 10,
                    "GEMINI_API_KEY": gemini_api_key,
                    "ANTHROPIC_API_KEY": "",
                    "OPENAI_API_KEY": ""
                } # Use the path in the shared volume
            )
            
            if response.status_code != 200:
                raise Exception(f"Classifier service failed with status {response.status_code}.")
                
            response_result = response.json()
            response_data = response_result["result"]
            
            # Load existing JSON files using absolute paths
            documentation_path = Path(f"/app/docstrings_json/{repo_name}.json")
            documentation_md_path = Path(f"/app/ducomentations_json/{repo_name}.json")
            config_path = Path(f"/app/configs_json/{repo_name}.json")
            
            # Ensure parent directories exist
            documentation_path.parent.mkdir(parents=True, exist_ok=True)
            documentation_md_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(documentation_path, "r") as f1:
                documentation_json = json.load(f1)
            with open(documentation_md_path, "r") as f2:
                documentation_md_json = json.load(f2)
            with open(config_path, "r") as f3:
                config_json = json.load(f3)
                
            # Update JSONs with new data
            # 1. Remove entries for deleted files
            deleted_rel_paths = [str(f.relative_to(existing_repo_path)) for f in deleted_files]
            
            # Handle docstrings_json (documentation)
            if "documentation" in documentation_json:
                updated_docs = []
                for item in documentation_json["documentation"]:
                    if "file_paths" in item and not any(item["file_paths"].endswith(deleted_path) for deleted_path in deleted_rel_paths):
                        updated_docs.append(item)
                documentation_json["documentation"] = updated_docs
            
            # Handle documentation_md
            if "documentation_md" in documentation_md_json:
                updated_md_docs = []
                for item in documentation_md_json["documentation_md"]:
                    if "file_paths" in item and not any(item["file_paths"].endswith(deleted_path) for deleted_path in deleted_rel_paths):
                        updated_md_docs.append(item)
                documentation_md_json["documentation_md"] = updated_md_docs
            
            # Handle configs
            if "config" in config_json:
                updated_configs = []
                for item in config_json["config"]:
                    if "file_paths" in item and not any(item["file_paths"].endswith(deleted_path) for deleted_path in deleted_rel_paths):
                        updated_configs.append(item)
                config_json["config"] = updated_configs
            
            # 2. Add new entries for changed/added files
            # Map temporary paths back to original paths for proper integration
            if "documentation" in response_data:
                for item in response_data["documentation"]:
                    if "file_paths" in item and item["file_paths"] in path_mapping:
                        # Replace temp path with original path
                        item["file_paths"] = path_mapping[item["file_paths"]]
                        # Add to existing documentation
                        documentation_json["documentation"].append(item)
            
            if "documentation_md" in response_data:
                for item in response_data["documentation_md"]:
                    if "file_paths" in item and item["file_paths"] in path_mapping:
                        item["file_paths"] = path_mapping[item["file_paths"]]
                        documentation_md_json["documentation_md"].append(item)
                        
            if "config" in response_data:
                for item in response_data["config"]:
                    if "file_paths" in item and item["file_paths"] in path_mapping:
                        item["file_paths"] = path_mapping[item["file_paths"]]
                        config_json["config"].append(item)
            
            # Save updated JSONs using absolute paths
            with open(documentation_path, "w") as f1:
                json.dump(documentation_json, f1, indent=4)
            with open(documentation_md_path, "w") as f2:
                json.dump(documentation_md_json, f2, indent=4)
            with open(config_path, "w") as f3:
                json.dump(config_json, f3, indent=4)
            
            # Create system prompt and cache
            system_prompt = """
# Context
You are an expert Software developer with a deep understanding of the software development lifecycle, including requirements gathering, design, implementation, testing, and deployment.
Your task is to answer any question related to the documentation of the python repository repository_name that you have in your context.


""".replace("repository_name", repo_name)
            
            documentation_str = str(documentation_json)
            from src.core.init_repo import create_cache
            cache_name = create_cache(repo_name, documentation_str, system_prompt, gemini_api_key)
            
            return cache_name
        finally:
            # Clean up the temporary directory
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temporary directory {temp_dir}: {cleanup_error}")
    
    except Exception as e:
        logger.error(f"Error processing changed repository {repo_name}: {str(e)}", exc_info=True)
        # Do not fall back to full processing here, raise the error
        raise e

def init_repo(repo_link, gemini_api_key=None):
    """Initialize repository and get parameters"""
    try:
        # Check if it's a local path (simple check, might need refinement)
        if Path(repo_link).is_dir():
            logger.warning("init_repo received a local path, which should be handled by folder upload.")
            return {
                "repo_name": "",
                "cache_id": "",
            }, "Please use the 'Upload Local Folder' option for local directories."

        api_key_preview = gemini_api_key[:5] if gemini_api_key and len(gemini_api_key) >= 5 else gemini_api_key
        logger.info(f"Attempting to initialize repository: {repo_link}")
        logger.info(f"Using GEMINI_API_KEY: {api_key_preview}... (length: {len(gemini_api_key) if gemini_api_key else 0})")
        
        # Get repository name from URL
        repo_name = repo_link.split("/")[-1]
        
        # Check if this repository already exists in our system
        target_base_path = Path("/app/repository_folder")
        target_repo_path = target_base_path / repo_name
        
        if target_repo_path.exists():
            logger.info(f"Repository already exists: {repo_name}. Checking for changes...")
            
            # Create a temporary directory for the new repository
            with tempfile.TemporaryDirectory() as temp_clone_dir:
                # Clone the repository to a temporary location
                from src.core.init_repo import clone_github_repo
                temp_repo_path = clone_github_repo(temp_clone_dir, repo_link)
                
                if not temp_repo_path:
                    raise Exception(f"Failed to clone repository to temporary location: {repo_link}")
                
                # Process the repository with change detection
                cache_name = process_changed_repository(
                    repo_name, 
                    Path(temp_repo_path), 
                    target_repo_path,
                    gemini_api_key,
                )
        else:
            # Repository doesn't exist, process normally
            cache_name = process_repo_link(repo_link, gemini_api_key)
            
        logger.info(f"process_repo_link returned cache_name: {cache_name}")
        repo_params = {"repo_name": repo_name, "cache_id": cache_name}
        logger.info(f"Generated repo_params: {repo_params}")
        return (
            repo_params,
            f"Successfully initialized repository: {repo_params['repo_name']}\nSelect model Custom Documentalist to give any task to your specialized model",
        )
    except Exception as e:
        logger.error(f"Error initializing repository: {str(e)}, GEMINI_API_KEY: {gemini_api_key}", exc_info=True)
        return {
            "repo_name": "",
            "cache_id": "",
        }, f"Error initializing repository via URL: {str(e)}"


def handle_zip_upload(uploaded_zip_file, gemini_api_key=None):
    """Handle zip file upload, extract, copy, and process it."""
    api_key_preview = gemini_api_key[:5] if gemini_api_key and len(gemini_api_key) >= 5 else gemini_api_key
    logger.info(f"Handling zip upload with GEMINI_API_KEY: {api_key_preview}... (length: {len(gemini_api_key) if gemini_api_key else 0})")
    repo_params_error = {"repo_name": "", "cache_id": ""}
    if not uploaded_zip_file or not isinstance(uploaded_zip_file, str):
        # Check if it's None or not a list
        logger.warning(f"Invalid input to handle_zip_upload: {uploaded_zip_file}")
        return repo_params_error, "No folder uploaded or invalid data received."

    initial_message = "Starting folder processing..."
    # Yield initial message immediately
    yield repo_params_error, initial_message

    # Get the original filename from the temporary file path
    temp_zip_filepath = Path(uploaded_zip_file)
    original_filename = "uploaded_repo.zip" # Default
    try:
        original_filename = temp_zip_filepath.name
        logger.info(f"Original filename from temp file path: {original_filename}")
    except Exception as e:
        logger.warning(f"Could not parse original filename from temp path '{temp_zip_filepath}': {e}")

    try:
        # Create a temporary directory to extract the zip file
        with tempfile.TemporaryDirectory() as extraction_dir:
            extraction_base = Path(extraction_dir)
            logger.info(f"Created extraction directory: {extraction_base}")

            repo_name = None
            temp_source_dir = None

            try:
                logger.info("Attempting to extract zip file...")
                # Open the zip file using the provided filepath
                with zipfile.ZipFile(temp_zip_filepath, 'r') as zip_ref:
                    # Check for potential path traversal issues (basic check)
                    for member in zip_ref.namelist():
                        if member.startswith('/') or '..' in member:
                            raise ValueError(f"Zip file contains unsafe path: {member}")
                    zip_ref.extractall(extraction_base)
                logger.info(f"Successfully extracted zip to {extraction_base}")

                # Determine the root directory within the extracted contents
                extracted_items = list(extraction_base.iterdir())
                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    # Common case: zip contains a single root folder
                    temp_source_dir = extracted_items[0]
                    repo_name = temp_source_dir.name
                    logger.info(f"Identified single root directory: {repo_name}")
                elif len(extracted_items) > 1:
                    # Case: zip extracts multiple files/folders at the root
                    # We might need to treat the extraction_base itself as the source
                    # and perhaps derive a name from the original zip filename?
                    # Use the original zip filename (stem) as repo_name
                    repo_name = Path(original_filename).stem
                    temp_source_dir = extraction_base
                    logger.warning(f"Zip file extracted multiple items at root. Using extraction dir as source and name '{repo_name}'.")
                else:
                    raise ValueError("Zip file is empty or contains unexpected structure after extraction.")

            except zipfile.BadZipFile:
                logger.error("Invalid zip file uploaded.")
                yield repo_params_error, "Error: Invalid or corrupted zip file."
                return
            except Exception as extract_e:
                logger.error(f"Error during zip extraction: {extract_e}\n{traceback.format_exc()}")
                yield repo_params_error, f"Error during zip extraction: {extract_e}"
                return

            # --- The rest of the logic uses the extracted temp_source_dir ---

            if not repo_name or not temp_source_dir or not temp_source_dir.is_dir():
                logger.error("Failed to determine valid source directory or repo name after extraction.")
                yield repo_params_error, "Error: Could not process extracted zip contents."
                return

            target_base_path = Path("/app/repository_folder")
            target_repo_path = target_base_path / repo_name

            logger.info(f"Handling upload for folder: {repo_name}")
            logger.info(f"Temporary source directory: {temp_source_dir}")
            logger.info(f"Target path: {target_repo_path}")

            # Create target base directory if it doesn't exist
            target_base_path.mkdir(parents=True, exist_ok=True)

            # Check if the repository already exists
            if target_repo_path.exists():
                logger.info(f"Repository already exists: {repo_name}. Checking for changes...")
                yield repo_params_error, f"Repository '{repo_name}' already exists. Checking for changes..."
                
                # Process the repository with change detection
                cache_name = process_changed_repository(
                    repo_name,
                    temp_source_dir,
                    target_repo_path,
                    gemini_api_key,
                )
                
                repo_params = {"repo_name": repo_name, "cache_id": cache_name}
                logger.info(f"Generated repo_params for changed repository: {repo_params}")
                final_message = f"Successfully processed and updated repository: {repo_name}\nSelect Custom Documentalist model."
                yield repo_params, final_message
                return
            
            # For a new repository, follow the normal process
            # --- Logging before copy ---
            try:
                source_contents = list(temp_source_dir.rglob('*')) # Recursively list contents
                logger.info(f"Contents of source dir '{temp_source_dir}' before copy: {len(source_contents)} items")
                # Log first few items for glimpse
                for item in source_contents[:5]:
                    logger.debug(f"  - {item}")
                if len(source_contents) > 5:
                    logger.debug(f"  - ... and {len(source_contents) - 5} more")
            except Exception as log_e:
                logger.warning(f"Could not log source directory contents: {log_e}")

            # Remove existing target directory if it exists to ensure fresh copy
            if target_repo_path.exists():
                logger.warning(f"Removing existing folder at target: {target_repo_path}")
                shutil.rmtree(target_repo_path)

            # Update status before copy
            yield repo_params_error, f"Copying folder '{repo_name}'..."

            # Copy the uploaded folder contents to the target path
            # shutil.copytree is suitable for copying directories
            shutil.copytree(temp_source_dir, target_repo_path)
            logger.info(f"Successfully copied folder to {target_repo_path}")

            # --- Logging after copy ---
            try:
                target_contents = list(target_repo_path.rglob('*')) # Recursively list contents
                logger.info(f"Contents of target dir '{target_repo_path}' after copy: {len(target_contents)} items")
                # Log first few items for glimpse
                for item in target_contents[:5]:
                    logger.debug(f"  - {item}")
                if len(target_contents) > 5:
                    logger.debug(f"  - ... and {len(target_contents) - 5} more")
            except Exception as log_e:
                logger.warning(f"Could not log target directory contents: {log_e}")

            # Update status before processing
            yield repo_params_error, f"Processing folder '{repo_name}'... (this may take a while)"

            # Now process the copied folder
            logger.info(f"Processing local folder: {target_repo_path}")
            cache_name = process_local_folder(str(target_repo_path), gemini_api_key)
            logger.info(f"process_local_folder returned cache_name: {cache_name}")

            repo_params = {"repo_name": repo_name, "cache_id": cache_name}
            logger.info(f"Generated repo_params for local folder: {repo_params}")
            final_message = f"Successfully processed local folder: {repo_name}\nSelect Custom Documentalist model."
            yield repo_params, final_message

    except Exception as outer_e:
        error_message = f"Error processing uploaded folder: {str(outer_e)}"
        logger.error(f"{error_message}\n{traceback.format_exc()}", exc_info=True)
        yield repo_params_error, error_message


