import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from src.schemas.description import (
    TemplateManager,
    generate_code_structure_model_consize,
    DocumentCompression,
    YamlBrief,
)
from src.schemas.classif import create_file_classification
from .utils import list_all_files, SAFE
import instructor
import os
import dotenv
import traceback
import asyncio
import google.generativeai as genai
from openai import OpenAI
import aiofiles
import logging
import traceback
from src.monitor import trace, generate_trace_id, get_langfuse_context, should_trace
from pathlib import Path

logger = logging.getLogger(__name__)

dotenv.load_dotenv()


class ClassifierConfig:
    def __init__(self):
        current_dir = Path(__file__).parent
        # Initialize TemplateManager with the correct search directory
        self.template_manager = TemplateManager(default_search_dir=current_dir)
        self.prompts_config = {
            "system_classification": self.template_manager.render_template("prompts/system_prompt_classification.jinja2"),
            "user_classification": self.template_manager.render_template("prompts/user_prompt_classification.jinja2"),
            "system_docstring": self.template_manager.render_template("prompts/prompt_docstrings/system_prompt_classification.jinja2"),
            "user_docstring": self.template_manager.render_template("prompts/prompt_docstrings/user_prompt_classification.jinja2"),
            "system_configuration": self.template_manager.render_template("prompts/prompt_configurations/system_prompt_configuration.jinja2"),
            "user_configuration": self.template_manager.render_template("prompts/prompt_configurations/user_prompt_configuration.jinja2"),
            "system_documentation": self.template_manager.render_template("prompts/prompt_documentations/system_prompt_documentation.jinja2"),
            "user_documentation": self.template_manager.render_template("prompts/prompt_documentations/user_prompt_documentation.jinja2"),
        }
        # Dynamically gather all GEMINI_MODEL_* env variables so that
        # adding new models is as simple as declaring them in the environment.
        # This also preserves the legacy attributes (file_class_model_0 … _N)
        # for backward-compatibility with the rest of the codebase.

        self.file_class_models: list[str] = []
        for i in range(20):  # support up to 20 models – adjust if ever needed
            model_name = os.getenv(f"GEMINI_MODEL_{i}")
            if model_name:
                self.file_class_models.append(model_name)
                setattr(self, f"file_class_model_{i}", model_name)

        # Gather GPT models
        self.gpt_models: list[str] = []
        for i in range(20):
            gpt_model = os.getenv(f"GPT_MODEL_{i}")
            if gpt_model:
                self.gpt_models.append(gpt_model)
                setattr(self, f"gpt_model_{i}", gpt_model)
                logger.info(f"Found GPT model: GPT_MODEL_{i} = {gpt_model}")

        logger.info(f"Total GPT models found: {len(self.gpt_models)} - {self.gpt_models}")

        if not self.file_class_models and not self.gpt_models:
            raise ValueError("No GEMINI_MODEL_* or GPT_MODEL_* environment variables defined – at least one model is required.")
        
        # Shared client pool for reuse across methods - initialized lazily
        self._clients_cache = None
        self._model_names_cache = None
    
    def _get_or_create_clients(self, GEMINI_API_KEY: str = "", OPENAI_API_KEY: str = ""):
        """Get or create shared client pool for reuse across methods"""
        logger.info(f"_get_or_create_clients called with GEMINI_API_KEY={'***' if GEMINI_API_KEY else 'empty'}, OPENAI_API_KEY={'***' if OPENAI_API_KEY else 'empty'}")
        logger.info(f"Available models - Gemini: {self.file_class_models}, GPT: {self.gpt_models}")
        cache_key = (bool(GEMINI_API_KEY), bool(OPENAI_API_KEY))
        if self._clients_cache is not None and getattr(self, "_cache_key", None) == cache_key:
            return self._clients_cache, self._model_names_cache
            
        # Configure safety settings
        safe = SAFE

        clients = {}
        model_names = {}
        idx = 0

        # --- Gemini / Gemma models ---
        if self.file_class_models:
            if GEMINI_API_KEY:
                genai.configure(api_key=GEMINI_API_KEY)
            else:
                genai.configure()

            for model_name in self.file_class_models:
                try:
                    gem_client = instructor.from_gemini(
                        client=genai.GenerativeModel(model_name=model_name, safety_settings=safe),
                        mode=instructor.Mode.GEMINI_JSON,
                    )
                    clients[idx] = gem_client
                    model_names[idx] = model_name
                    idx += 1
                except Exception as e:
                    logger.error(f"Failed to create Gemini client for model {model_name}: {e}")

        # --- GPT / OpenAI models ---
        if OPENAI_API_KEY and self.gpt_models:
            logger.info(f"Creating OpenAI clients for models: {self.gpt_models}")
            try:
                openai_client = OpenAI(api_key=OPENAI_API_KEY)
                for gpt_model in self.gpt_models:
                    # Create separate instructor client for each model to handle different model names
                    openai_instructor = instructor.from_openai(
                        client=openai_client,
                        mode=instructor.Mode.JSON,
                    )
                    clients[idx] = openai_instructor
                    model_names[idx] = gpt_model
                    logger.info(f"Added OpenAI client for model {gpt_model} at index {idx}")
                    idx += 1
            except Exception as e:
                logger.error(f"Failed to create OpenAI clients: {e}")
        elif OPENAI_API_KEY:
            logger.warning(f"OPENAI_API_KEY provided but no GPT models found. Available GPT models: {self.gpt_models}")
        elif self.gpt_models:
            logger.info(f"GPT models available ({self.gpt_models}) but no OPENAI_API_KEY provided")

        if not clients:
            raise RuntimeError("Unable to instantiate any LLM client. Check model names and credentials.")
            
        logger.info(f"Created {len(clients)} total clients: {list(model_names.values())}")
        
        # Cache for reuse
        self._clients_cache = clients
        self._model_names_cache = model_names
        self._cache_key = cache_key
        
        return clients, model_names


class ClassifierNode(ClassifierConfig):
    def __init__(self):
        super().__init__()

    async def process_batch(
        self,
        file_batch: list[str],
        client_gemini,
        model_name,
        symstem_prompt: str,
        user_prompt: str,
        scores: list[int],
        span=None,
    ) -> dict:
        """Process a batch of files using Gemini API"""
        batch_prompt = user_prompt + "\n" + f"{file_batch}"

        messages = [
            {"role": "system", "content": symstem_prompt},
            {"role": "user", "content": batch_prompt},
        ]

        if span:
            generation = span.generation(
                name="gemini",
                model=model_name,
                model_parameters={"temperature": 0, "top_p": 1, "max_new_tokens": 8000},
                input={"system_prompt": symstem_prompt, "user_prompt": batch_prompt},
            )

        try:
            # Detect if this is a Gemini or OpenAI client and use appropriate API
            if "gemini" in model_name.lower() or "gemma" in model_name.lower():
                # Gemini API
                completion, raw = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client_gemini.chat.create_with_completion(
                        messages=messages,
                        response_model=create_file_classification(file_batch, scores),
                        generation_config={
                            "temperature": 0.0,
                            "top_p": 1,
                            "candidate_count": 1,
                            "max_output_tokens": 8000,
                        },
                        max_retries=3,
                    )
                )
            else:
                # OpenAI API
                completion, raw = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client_gemini.chat.completions.create_with_completion(
                        model=model_name,
                        messages=messages,
                        response_model=create_file_classification(file_batch, scores),
                        temperature=0.0,
                        top_p=1,
                        max_tokens=8000,
                        max_retries=3,
                    )
                )
            result = completion.model_dump()

        except Exception as e:
            if span:
                generation.end(
                    output=None,
                    status_message=f"Error processing batch: {str(e)}",
                    level="ERROR",
                )
            raise Exception(f"Batch processing failed: {str(e)}, {traceback.format_exc()}")

        if span:
            generation.end(
                output=result,
                usage={
                    "input": raw.usage_metadata.prompt_token_count,
                    "output": raw.usage_metadata.candidates_token_count,
                },
            )

        return result

    @trace
    async def llmclassifier(
        self,
        folder_path: str,
        batch_size: int = 10,  # Ultra-small batches for maximum parallelism
        max_workers: int = 100,  # Maximum concurrency for ultra-fast processing
        GEMINI_API_KEY: str = "",
        ANTHROPIC_API_KEY: str = "",
        OPENAI_API_KEY: str = "",
        trace_id: str = ""
    ) -> str:
        span = get_langfuse_context().get("span")

        scores = [0]

        # Use shared client pool for better performance
        clients, model_names = self._get_or_create_clients(GEMINI_API_KEY, OPENAI_API_KEY)

        # Get file names
        files_structure = list_all_files(folder_path, include_md=True)

        file_names = files_structure["all_files_no_path"]
        files_paths = files_structure["all_files_with_path"]

        # Split files into batches
        batches = [
            file_names[i : i + batch_size] for i in range(0, len(file_names), batch_size)
        ]

        all_results = {"file_classifications": []}

        # Process batches in parallel using asyncio
        tasks = []
        for index, batch in enumerate(batches):
            task = self.process_batch(
                batch,
                clients[index % len(clients)],
                model_names[index % len(clients)],
                self.prompts_config["system_classification"],
                self.prompts_config["user_classification"],
                scores,
                span,
            )
            tasks.append(task)

        # Use asyncio.gather with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_workers)
        
        async def bounded_task(task):
            async with semaphore:
                return await task

        bounded_tasks = [bounded_task(task) for task in tasks]
        
        try:
            results = await asyncio.gather(*bounded_tasks)
            for result in results:
                all_results["file_classifications"].extend(
                    result.get("file_classifications", [])
                )
        except Exception as e:
            raise Exception(f"Batch processing failed: {str(e)}, {traceback.format_exc()}")

        # replace file_name by fileç_path
        for classification in all_results["file_classifications"]:
            classification["file_paths"] = files_paths[classification["file_id"]]

        return all_results


class InformationCompressorNode(ClassifierConfig):
    def __init__(self):
        super().__init__()
    
    async def process_batch(
        self,
        file_batch: str,
        client_gemini,
        model_name,
        system_prompt: str,
        user_prompt: str,
        scores: list[int],
        span=None,
        index=None,
        log_name=None,
        fallback_clients: list[instructor.Instructor] = None,
        fallback_model_names: list[str] = None,
    ) -> dict:
        """Process a batch of files using Gemini API with timeout and retries."""
        batch_prompt = ""
        try:
            # Use async file reading for non-blocking I/O
            async with aiofiles.open(file_batch, "r") as f:
                file_content = await f.read()
                batch_prompt = user_prompt + "\n" + file_content
        except Exception as e:
            return None, None

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": batch_prompt},
        ]

        if log_name == "docstring":
            pydantic_model = generate_code_structure_model_consize(batch_prompt)
        elif log_name == "documentation":
            pydantic_model = DocumentCompression
        else: # config
            pydantic_model = YamlBrief

        # --- Langfuse Span Setup ---
        generation = None
        if span:
            # Create the generation span *before* the retry loop
            generation = span.generation(
                name=f"{log_name}_attempt", # Initial name, might update later
                model=model_name, # Initial model
                model_parameters={"temperature": 0, "top_p": 1, "max_new_tokens": 8000},
                input={"system_prompt": system_prompt, "user_prompt": batch_prompt},
            )

        # --- Retry Logic ---
        max_attempts = 4 # 1 initial + 3 retries
        clients_to_try = [(client_gemini, model_name)] + list(zip(fallback_clients or [], fallback_model_names or []))
        # Ensure we don't try more clients than available or exceed max_attempts
        clients_to_try = clients_to_try[:max_attempts]

        last_exception = None
        last_status_message = ""

        for attempt, (current_client, current_model_name) in enumerate(clients_to_try):
            try:
                # Use asyncio.wait_for for timeout instead of ThreadPoolExecutor
                async def api_call_task():
                    if "gemini" in current_model_name.lower() or "gemma" in current_model_name.lower():
                        # Gemini API
                        return await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: current_client.chat.create_with_completion(
                                messages=messages,
                                response_model=pydantic_model,
                                generation_config={
                                    "temperature": 0.0,
                                    "top_p": 1,
                                    "candidate_count": 1,
                                    "max_output_tokens": 8000,
                                },
                                max_retries=1,
                            )
                        )
                    else:
                        # OpenAI API
                        return await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: current_client.chat.completions.create_with_completion(
                                model=current_model_name,
                                messages=messages,
                                response_model=pydantic_model,
                                temperature=0.0,
                                top_p=1,
                                max_tokens=8000,
                                max_retries=1,
                            )
                        )

                completion, raw = await asyncio.wait_for(api_call_task(), timeout=8.0)

                # --- Success ---
                result = completion.model_dump()
                if generation:
                    # Update generation details for the successful attempt
                    generation.model = current_model_name
                    generation.end(
                        output=result,
                        usage={
                            "input": raw.usage_metadata.prompt_token_count,
                            "output": raw.usage_metadata.candidates_token_count,
                        },
                        level="DEFAULT", # Explicitly set level to DEFAULT for success
                        status_message=f"Success on attempt {attempt + 1}"
                    )
                return result, index

            except asyncio.TimeoutError:
                last_status_message = f"Attempt {attempt + 1} timed out after 5s (Model: {current_model_name})"
                last_exception = asyncio.TimeoutError(last_status_message) # Store exception type

            except Exception as e:
                last_status_message = f"Attempt {attempt + 1} failed (Model: {current_model_name}): {str(e)}, {traceback.format_exc()}"
                last_exception = e # Store the exception

            # Update generation span for failed attempt if it exists
            if generation:
                generation.status_message=last_status_message # Keep updating status message on failures
                generation.model = current_model_name # Ensure model name reflects the failed attempt

        # --- All attempts failed ---
        if generation:
            generation.end(
                output=None,
                status_message=last_status_message,
                level="ERROR",
            )
        return None, None

    @trace
    async def summerizer(
        self,
        classified_files: dict,
        batch_size: int = 10,  # Smaller batches for better parallelism
        max_workers: int = 80,  # Number of parallel workers
        GEMINI_API_KEY: str = "",
        ANTHROPIC_API_KEY: str = "",
        OPENAI_API_KEY: str = "",
        trace_id: str = ""
    ) -> str:
        span = get_langfuse_context().get("span")
        scores = [0]

        # Use shared client pool for better performance
        clients, model_names = self._get_or_create_clients(GEMINI_API_KEY, OPENAI_API_KEY)

        # Prepare file lists for each category
        files_structure_docstring = []
        files_structure_documentation = []
        files_structure_config = []

        # Keep track of original indices to update the main dict later if needed
        # or to handle categorization after processing
        original_indices = {}

        for index, file in enumerate(classified_files["file_classifications"]):
            file_path = file["file_paths"]
            file_name = file.get("file_name", "").lower() # Handle potential missing key
            original_indices[file_path] = index # Store index by file_path

            if "code" in file["classification"].lower() and "ipynb" not in file_path and "__init__.py" not in file_path:
                files_structure_docstring.append([file_path, "docstring"])
            elif ".md" in file_path.lower():
                files_structure_documentation.append([file_path, "documentation"])
            elif ".yaml" in file_path.lower() or ".yml" in file_path.lower() or ".yml" in file_name:
                files_structure_config.append([file_path, "config"])

        # Combine all files to process
        all_files_to_process = files_structure_docstring + files_structure_documentation + files_structure_config

        # Temporary storage for results
        results_docstring = {}
        results_documentation = {}
        results_config = {}

        # Create tasks for all files
        tasks = []
        file_to_category = {}
        
        for i, (file_path, category) in enumerate(all_files_to_process):
            client_index = i % len(clients)
            model_name = model_names[client_index]
            client = clients[client_index]
            fallback_clients = [clients[j] for j in range(len(clients)) if j != client_index]
            fallback_model_names = [model_names[j] for j in range(len(clients)) if j != client_index]
            
            if category == "docstring":
                system_prompt = self.prompts_config["system_docstring"]
                user_prompt = self.prompts_config["user_docstring"]
                log_name = "docstring"
            elif category == "documentation":
                system_prompt = self.prompts_config["system_documentation"]
                user_prompt = self.prompts_config["user_documentation"]
                log_name = "documentation"
            else: # category == "config"
                system_prompt = self.prompts_config["system_configuration"]
                user_prompt = self.prompts_config["user_configuration"]
                log_name = "config"

            task = self.process_batch(
                file_path,
                client,
                model_name,
                system_prompt,
                user_prompt,
                scores,
                span,
                file_path, # Pass file_path as identifier instead of original index
                log_name=log_name,
                fallback_clients=fallback_clients,
                fallback_model_names=fallback_model_names,
            )
            tasks.append(task)
            file_to_category[i] = (file_path, category)

        # Use asyncio.gather with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_workers)
        
        async def bounded_task(task):
            async with semaphore:
                return await task

        bounded_tasks = [bounded_task(task) for task in tasks]
        
        try:
            results = await asyncio.gather(*bounded_tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                file_path, category = file_to_category[i]
                if isinstance(result, Exception):
                    continue
                    
                processed_result, identifier = result
                if processed_result and identifier == file_path: # Check if result is valid and matches the file path
                    if category == "docstring":
                        results_docstring[file_path] = processed_result
                    elif category == "documentation":
                        results_documentation[file_path] = processed_result
                    elif category == "config":
                        results_config[file_path] = processed_result
                        
        except Exception as e:
            pass

        # Structure the final output
        output_documentation = []
        output_documentation_md = []
        output_config = []

        processed_indices = set()

        # Populate docstring results
        for file_path, result in results_docstring.items():
            original_index = original_indices.get(file_path)
            if original_index is not None:
                file_data = classified_files["file_classifications"][original_index].copy()
                file_data["documentation"] = result
                file_data["file_id"] = len(output_documentation) # Assign new sequential ID
                output_documentation.append(file_data)
                processed_indices.add(original_index)

        # Populate documentation (.md) results
        for file_path, result in results_documentation.items():
            original_index = original_indices.get(file_path)
            if original_index is not None:
                file_data = classified_files["file_classifications"][original_index].copy()
                file_data["documentation"] = result # Add result under 'documentation' key
                file_data["file_id"] = len(output_documentation_md)
                output_documentation_md.append(file_data)
                processed_indices.add(original_index)

        # Populate config results
        for file_path, result in results_config.items():
            original_index = original_indices.get(file_path)
            if original_index is not None:
                file_data = classified_files["file_classifications"][original_index].copy()
                file_data["documentation_config"] = result # Add result under 'documentation_config' key
                file_data["file_id"] = len(output_config)
                output_config.append(file_data)
                processed_indices.add(original_index)

        return {
            "documentation": output_documentation,
            "documentation_md": output_documentation_md,
            "config": output_config,
        }


class ClassifierService:
    def __init__(self):
        self.model = None
        self.classifier_node = ClassifierNode()
        self.information_compressor_node = InformationCompressorNode()
        self.trace_id = generate_trace_id()
        
    async def run_pipeline(self, folder_path: str, batch_size: int = 40, max_workers: int = 100, GEMINI_API_KEY: str = "", ANTHROPIC_API_KEY: str = "", OPENAI_API_KEY: str = ""):
        trace_id = generate_trace_id()
        # Classifier Node
        classifier_result = await self.classifier_node.llmclassifier(
            folder_path, 
            batch_size, 
            max_workers, 
            GEMINI_API_KEY, 
            ANTHROPIC_API_KEY, 
            OPENAI_API_KEY, 
            trace_id=trace_id 
        )
        # Information Compressor Node
        information_compressor_result = await self.information_compressor_node.summerizer(
            classifier_result, 
            batch_size, 
            max_workers, 
            GEMINI_API_KEY, 
            ANTHROPIC_API_KEY, 
            OPENAI_API_KEY, 
            trace_id=trace_id  # Pass trace_id explicitly
        )
        return information_compressor_result




# test
if __name__ == "__main__":
    async def main():
        classifier_service = ClassifierService()
        result = await classifier_service.run_pipeline("/Users/davidperso/projects/deepgithub/backend/app",GEMINI_API_KEY=os.getenv("GEMINI_API_KEY"))
        print(result)
    
    asyncio.run(main())