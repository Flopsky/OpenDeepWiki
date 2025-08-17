import os
import sys
import time
import asyncio
import logging
import traceback
from pathlib import Path

# --- project path bootstrap ---
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# --- third-party / local imports ---
import dotenv
import aiofiles
import instructor
import google.generativeai as genai
from openai import OpenAI
from langfuse.decorators import observe, langfuse_context

from src.schemas.description import (
    TemplateManager,
    generate_code_structure_model_consize,
    DocumentCompression,
    YamlBrief,
)
from src.schemas.classif import create_file_classification
from .utils import list_all_files, SAFE

from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
dotenv.load_dotenv()


# ============================================================
# Base config shared by nodes: clients, prompts, limits
# ============================================================
class ClassifierConfig:
    def __init__(self):
        current_dir = Path(__file__).parent

        # Templates
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

        # Gather models from env
        self.file_class_models: list[str] = []
        for i in range(20):
            mn = os.getenv(f"GEMINI_MODEL_{i}")
            if mn:
                self.file_class_models.append(mn)
                setattr(self, f"file_class_model_{i}", mn)

        self.gpt_models: list[str] = []
        for i in range(20):
            gm = os.getenv(f"GPT_MODEL_{i}")
            if gm:
                self.gpt_models.append(gm)
                setattr(self, f"gpt_model_{i}", gm)
                logger.info(f"Found GPT model: GPT_MODEL_{i} = {gm}")

        logger.info(f"Total GPT models found: {len(self.gpt_models)} - {self.gpt_models}")

        if not self.file_class_models and not self.gpt_models:
            raise ValueError("No GEMINI_MODEL_* or GPT_MODEL_* env vars defined – at least one model is required.")

        # Concurrency controls (env-tunable)
        self._limits = {
            "openai": asyncio.Semaphore(int(os.getenv("OPENAI_INFLIGHT", "200"))),
            "gemini": asyncio.Semaphore(int(os.getenv("GEMINI_INFLIGHT", "200"))),
        }
        self._file_io_limit = asyncio.Semaphore(int(os.getenv("FILE_INFLIGHT", "200")))

        # Shared clients cache
        self._clients_cache = None
        self._model_names_cache = None
        self._cache_key = None

    # Provider name resolver
    @staticmethod
    def _provider_for(model_name: str) -> str:
        m = (model_name or "").lower()
        return "gemini" if ("gemini" in m or "gemma" in m) else "openai"

    # Create / reuse client pool
    def _get_or_create_clients(self, GEMINI_API_KEY: str = "", OPENAI_API_KEY: str = ""):
        logger.info(
            f"_get_or_create_clients called with GEMINI_API_KEY={'***' if GEMINI_API_KEY else 'empty'}, "
            f"OPENAI_API_KEY={'***' if OPENAI_API_KEY else 'empty'}"
        )
        logger.info(f"Available models - Gemini: {self.file_class_models}, GPT: {self.gpt_models}")

        cache_key = (bool(GEMINI_API_KEY), bool(OPENAI_API_KEY))
        if self._clients_cache is not None and self._cache_key == cache_key:
            return self._clients_cache, self._model_names_cache

        safe = SAFE
        clients = {}
        model_names = {}
        idx = 0

        # Gemini/Gemma clients
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

        # OpenAI clients
        if OPENAI_API_KEY and self.gpt_models:
            logger.info(f"Creating OpenAI clients for models: {self.gpt_models}")
            try:
                openai_client = OpenAI(api_key=OPENAI_API_KEY)
                for gpt_model in self.gpt_models:
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

        self._clients_cache = clients
        self._model_names_cache = model_names
        self._cache_key = cache_key
        return clients, model_names


# ============================================================
# Classifier: fan out tasks; provider-bounded calls
# ============================================================
class ClassifierNode(ClassifierConfig):
    def __init__(self):
        super().__init__()

    @observe(as_type="generation")
    async def process_batch(
        self,
        file_batch: list[str],
        client_gemini,
        model_name,
        symstem_prompt: str,
        user_prompt: str,
        scores: list[int],
    ) -> dict:
        """Process ONE batch (can be a single file) via the appropriate provider."""
        batch_prompt = user_prompt + "\n" + f"{file_batch}"
        messages = [
            {"role": "system", "content": symstem_prompt},
            {"role": "user", "content": batch_prompt},
        ]

        provider = self._provider_for(model_name)
        loop = asyncio.get_event_loop()

        try:
            async with self._limits[provider]:
                if provider == "gemini":
                    completion, raw = await loop.run_in_executor(
                        None,
                        lambda: client_gemini.chat.create_with_completion(
                            messages=messages,
                            response_model=create_file_classification(file_batch, scores),
                            generation_config={
                                "temperature": 0.0,
                                "top_p": 1,
                                "candidate_count": 1,
                                "max_output_tokens": 8000,  # keep as requested
                            },
                            max_retries=3,
                        ),
                    )
                else:
                    completion, raw = await loop.run_in_executor(
                        None,
                        lambda: client_gemini.chat.completions.create_with_completion(
                            model=model_name,
                            messages=messages,
                            response_model=create_file_classification(file_batch, scores),
                            temperature=0.0,
                            top_p=1,
                            max_tokens=8000,  # keep as requested
                            max_retries=3,
                        ),
                    )
            result = completion.model_dump()
        except Exception as e:
            # record failure into langfuse observation if available
            try:
                langfuse_context.update_current_observation(
                    status_message=f"Error processing batch: {str(e)}",
                    level="ERROR",
                )
            except Exception:
                pass
            raise Exception(f"Batch processing failed: {str(e)}, {traceback.format_exc()}")

        # attach usage if SDK provided it
        try:
            langfuse_context.update_current_observation(
                model=model_name,
                model_parameters={"temperature": 0, "top_p": 1, "max_new_tokens": 8000},
                usage={
                    "input": getattr(getattr(raw, "usage_metadata", {}), "prompt_token_count", None),
                    "output": getattr(getattr(raw, "usage_metadata", {}), "candidates_token_count", None),
                },
            )
        except Exception:
            pass

        return result

    @observe()
    async def llmclassifier(
        self,
        folder_path: str,
        batch_size: int = 1,          # default fan-out: single file per batch
        max_workers: int = 100,       # overall task cap (optional; provider caps still apply)
        GEMINI_API_KEY: str = "",
        ANTHROPIC_API_KEY: str = "",
        OPENAI_API_KEY: str = "",
    ) -> dict:
        """
        Classify files. Fan out one task per (batch_size) files.
        Set CLASSIFY_BATCH_SIZE env to override default (1).
        """
        scores = [0]
        env_batch = int(os.getenv("CLASSIFY_BATCH_SIZE", str(batch_size)))
        batch_size = max(1, env_batch)

        # Clients
        clients, model_names = self._get_or_create_clients(GEMINI_API_KEY, OPENAI_API_KEY)

        # Files
        files_structure = list_all_files(folder_path, include_md=True)
        file_names = files_structure["all_files_no_path"]
        files_paths = files_structure["all_files_with_path"]

        # Batching
        batches = [file_names[i:i + batch_size] for i in range(0, len(file_names), batch_size)]

        # Tasks (distribute over client set)
        tasks = []
        for index, batch in enumerate(batches):
            task = self.process_batch(
                batch,
                clients[index % len(clients)],
                model_names[index % len(clients)],
                self.prompts_config["system_classification"],
                self.prompts_config["user_classification"],
                scores,
            )
            tasks.append(task)

        # Optional global task cap to avoid memory spikes
        # (Provider/file semaphores are the main throttles)
        semaphore = asyncio.Semaphore(max_workers)

        async def bounded(t):
            async with semaphore:
                return await t

        results = await asyncio.gather(*(bounded(t) for t in tasks))

        all_results = {"file_classifications": []}
        for r in results:
            all_results["file_classifications"].extend(r.get("file_classifications", []))

        # Map file_id -> path
        for classification in all_results["file_classifications"]:
            classification["file_paths"] = files_paths[classification["file_id"]]

        return all_results


# ============================================================
# Summarizer/Compressor: one task per file; bounded I/O + provider caps
# ============================================================
class InformationCompressorNode(ClassifierConfig):
    def __init__(self):
        super().__init__()

    @observe(as_type="generation")
    async def process_batch(
        self,
        file_batch: str,
        client_gemini,
        model_name,
        system_prompt: str,
        user_prompt: str,
        scores: list[int],
        index=None,
        log_name=None,
        fallback_clients: list[instructor.Instructor] = None,
        fallback_model_names: list[str] = None,
    ) -> tuple[dict | None, str | None]:
        """Process a SINGLE file with timeout + provider-bound concurrency and file I/O bounding."""
        # --- File I/O (bounded) ---
        batch_prompt = ""
        try:
            async with self._file_io_limit:
                async with aiofiles.open(file_batch, "r") as f:
                    file_content = await f.read()
            batch_prompt = user_prompt + "\n" + file_content
        except Exception:
            return None, None

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": batch_prompt},
        ]

        if log_name == "docstring":
            pydantic_model = generate_code_structure_model_consize(batch_prompt)
        elif log_name == "documentation":
            pydantic_model = DocumentCompression
        else:
            pydantic_model = YamlBrief

        # Retry/time budget across fallbacks
        total_timeout_seconds = float(os.getenv("LLM_TOTAL_TIMEOUT_SECONDS", "30.0"))
        default_attempt_timeout = float(os.getenv("LLM_ATTEMPT_TIMEOUT_SECONDS", "15.0"))
        max_attempts = int(os.getenv("LLM_MAX_ATTEMPTS", "4"))

        clients_to_try = [(client_gemini, model_name)] + list(zip(fallback_clients or [], fallback_model_names or []))
        clients_to_try = clients_to_try[:max_attempts]

        deadline = time.monotonic() + total_timeout_seconds
        last_status_message = ""

        for attempt, (current_client, current_model_name) in enumerate(clients_to_try):
            provider = self._provider_for(current_model_name)
            loop = asyncio.get_event_loop()

            try:
                async def api_call_task():
                    async with self._limits[provider]:
                        if provider == "gemini":
                            return await loop.run_in_executor(
                                None,
                                lambda: current_client.chat.create_with_completion(
                                    messages=messages,
                                    response_model=pydantic_model,
                                    generation_config={
                                        "temperature": 0.0,
                                        "top_p": 1,
                                        "candidate_count": 1,
                                        "max_output_tokens": 8000,  # keep as requested
                                    },
                                    max_retries=1,
                                ),
                            )
                        else:
                            return await loop.run_in_executor(
                                None,
                                lambda: current_client.chat.completions.create_with_completion(
                                    model=current_model_name,
                                    messages=messages,
                                    response_model=pydantic_model,
                                    temperature=0.0,
                                    top_p=1,
                                    max_tokens=8000,  # keep as requested
                                    max_retries=1,
                                ),
                            )

                remaining = max(0.0, deadline - time.monotonic())
                if remaining <= 0:
                    last_status_message = (
                        f"Exceeded total timeout budget of {total_timeout_seconds:.1f}s before attempt {attempt + 1} "
                        f"(Model: {current_model_name})"
                    )
                    break

                per_attempt_timeout = max(0.2, min(default_attempt_timeout, remaining))
                completion, raw = await asyncio.wait_for(api_call_task(), timeout=per_attempt_timeout)

                result = completion.model_dump()
                try:
                    langfuse_context.update_current_observation(
                        model=current_model_name,
                        model_parameters={"temperature": 0, "top_p": 1, "max_new_tokens": 8000},
                        usage={
                            "input": getattr(getattr(raw, "usage_metadata", {}), "prompt_token_count", None),
                            "output": getattr(getattr(raw, "usage_metadata", {}), "candidates_token_count", None),
                        },
                        status_message=f"Success on attempt {attempt + 1}",
                    )
                except Exception:
                    pass
                return result, index

            except asyncio.TimeoutError:
                last_status_message = (
                    f"Attempt {attempt + 1} timed out within "
                    f"{min(default_attempt_timeout, max(0.0, deadline - time.monotonic())):.1f}s "
                    f"(Model: {current_model_name})"
                )
            except Exception as e:
                last_status_message = f"Attempt {attempt + 1} failed (Model: {current_model_name}): {str(e)}, {traceback.format_exc()}"

            try:
                langfuse_context.update_current_observation(status_message=last_status_message)
            except Exception:
                pass

        try:
            if time.monotonic() > deadline and "Exceeded total timeout" not in last_status_message:
                last_status_message = f"Exceeded total timeout budget of {total_timeout_seconds:.1f}s after {attempt + 1} attempts"
            langfuse_context.update_current_observation(status_message=last_status_message, level="ERROR")
        except Exception:
            pass

        return None, None

    @observe()
    async def summerizer(
        self,
        classified_files: dict,
        batch_size: int = 10,   # not used for fan-out; kept for compatibility
        max_workers: int = 80,
        GEMINI_API_KEY: str = "",
        ANTHROPIC_API_KEY: str = "",
        OPENAI_API_KEY: str = "",
    ) -> dict:
        # clients
        clients, model_names = self._get_or_create_clients(GEMINI_API_KEY, OPENAI_API_KEY)

        # group files by category
        files_structure_docstring = []
        files_structure_documentation = []
        files_structure_config = []

        original_indices = {}
        for index, file in enumerate(classified_files["file_classifications"]):
            file_path = file["file_paths"]
            file_name = file.get("file_name", "").lower()
            original_indices[file_path] = index

            if "code" in file["classification"].lower() and "ipynb" not in file_path and "__init__.py" not in file_path:
                files_structure_docstring.append([file_path, "docstring"])
            elif ".md" in file_path.lower():
                files_structure_documentation.append([file_path, "documentation"])
            elif ".yaml" in file_path.lower() or ".yml" in file_path.lower() or ".yml" in file_name:
                files_structure_config.append([file_path, "config"])

        all_files_to_process = files_structure_docstring + files_structure_documentation + files_structure_config

        results_docstring = {}
        results_documentation = {}
        results_config = {}

        # schedule tasks
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
            else:
                system_prompt = self.prompts_config["system_configuration"]
                user_prompt = self.prompts_config["user_configuration"]
                log_name = "config"

            task = self.process_batch(
                file_path,
                client,
                model_name,
                system_prompt,
                user_prompt,
                scores=[0],
                index=file_path,
                log_name=log_name,
                fallback_clients=fallback_clients,
                fallback_model_names=fallback_model_names,
            )
            tasks.append(task)
            file_to_category[i] = (file_path, category)

        # Optional global task cap to avoid memory spikes
        semaphore = asyncio.Semaphore(max_workers)

        async def bounded(t):
            async with semaphore:
                return await t

        results = await asyncio.gather(*(bounded(t) for t in tasks), return_exceptions=True)

        # collect
        for i, result in enumerate(results):
            file_path, category = file_to_category[i]
            if isinstance(result, Exception):
                continue
            processed_result, identifier = result
            if processed_result and identifier == file_path:
                if category == "docstring":
                    results_docstring[file_path] = processed_result
                elif category == "documentation":
                    results_documentation[file_path] = processed_result
                elif category == "config":
                    results_config[file_path] = processed_result

        # structure final output
        output_documentation = []
        output_documentation_md = []
        output_config = []

        processed_indices = set()

        for file_path, result in results_docstring.items():
            original_index = original_indices.get(file_path)
            if original_index is not None:
                file_data = classified_files["file_classifications"][original_index].copy()
                file_data["documentation"] = result
                file_data["file_id"] = len(output_documentation)
                output_documentation.append(file_data)
                processed_indices.add(original_index)

        for file_path, result in results_documentation.items():
            original_index = original_indices.get(file_path)
            if original_index is not None:
                file_data = classified_files["file_classifications"][original_index].copy()
                file_data["documentation"] = result
                file_data["file_id"] = len(output_documentation_md)
                output_documentation_md.append(file_data)
                processed_indices.add(original_index)

        for file_path, result in results_config.items():
            original_index = original_indices.get(file_path)
            if original_index is not None:
                file_data = classified_files["file_classifications"][original_index].copy()
                file_data["documentation_config"] = result
                file_data["file_id"] = len(output_config)
                output_config.append(file_data)
                processed_indices.add(original_index)

        return {
            "documentation": output_documentation,
            "documentation_md": output_documentation_md,
            "config": output_config,
        }


# ============================================================
# Service: sets a larger default executor, runs the 2-stage pipeline
# ============================================================
class ClassifierService:
    def __init__(self):
        self.model = None
        self.classifier_node = ClassifierNode()
        self.information_compressor_node = InformationCompressorNode()
        # Thread pool for network-bound SDK calls
        self._executor = ThreadPoolExecutor(max_workers=int(os.getenv("NETWORK_THREADPOOL", "200")))

    async def run_pipeline(
        self,
        folder_path: str,
        batch_size: int = 40,
        max_workers: int = 100,
        GEMINI_API_KEY: str = "",
        ANTHROPIC_API_KEY: str = "",
        OPENAI_API_KEY: str = "",
    ):
        # Make our big pool the default for run_in_executor / to_thread
        loop = asyncio.get_running_loop()
        loop.set_default_executor(self._executor)

        # 1) Classification — fan-out; override to per-file by env CLASSIFY_BATCH_SIZE=1
        classifier_result = await self.classifier_node.llmclassifier(
            folder_path=folder_path,
            batch_size=10,  # will be overridden by CLASSIFY_BATCH_SIZE env if set
            max_workers=100,
            GEMINI_API_KEY=GEMINI_API_KEY,
            ANTHROPIC_API_KEY=ANTHROPIC_API_KEY,
            OPENAI_API_KEY=OPENAI_API_KEY,
        )

        # 2) Summarization/compression — one task per file, bounded by provider + I/O limits
        information_compressor_result = await self.information_compressor_node.summerizer(
            classified_files=classifier_result,
            batch_size=batch_size,
            max_workers=100,
            GEMINI_API_KEY=GEMINI_API_KEY,
            ANTHROPIC_API_KEY=ANTHROPIC_API_KEY,
            OPENAI_API_KEY=OPENAI_API_KEY,
        )
        return information_compressor_result


# ============================================================
# test harness
# ============================================================
if __name__ == "__main__":
    start_time = time.time()
    print(f"Start time: {start_time}")

    async def main():
        classifier_service = ClassifierService()
        result = await classifier_service.run_pipeline(
            "/Users/davidperso/freelance/gradio",
            GEMINI_API_KEY=os.getenv("GEMINI_API_KEY"),
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
        )
        print(result)

    asyncio.run(main())
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")
