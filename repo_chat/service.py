import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from src.schemas.doc_retriver import GoalRewriteModel,get_necesary_files
from .utils import SAFE,get_gemini_pro_25_response,get_claude_response
from src.monitor.langfuse import get_langfuse_context,trace,generate_trace_id
from src.schemas.description import TemplateManager
import instructor
import os
import dotenv
import traceback
import json
import instructor
from google.generativeai import caching
import google.generativeai as genai
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from repo_chat.utils_retrieval import order_docs_stably, chunk_ranges
from repo_chat.selection import llm_select_files
import logging
import traceback
from openai import OpenAI
from anthropic import Anthropic, Timeout

logger = logging.getLogger(__name__)


dotenv.load_dotenv()

#TODO PUT ALL LLM CLIENTS IN LLLM_SERVICE

class ClassifierConfig:
    def __init__(self):
        self.current_dir = Path(__file__).parent
        # Initialize TemplateManager with the correct search directory
        self.template_manager = TemplateManager(default_search_dir=self.current_dir)
        self.prompts_config = {
        }
        self.file_class_model_0 = os.getenv("GEMINI_MODEL_0")
        self.file_class_model_1 = os.getenv("GEMINI_MODEL_1")
        self.file_class_model_2 = os.getenv("GEMINI_MODEL_2")
        self.file_class_model_3 = os.getenv("GEMINI_MODEL_3")
        self.querry_rewriting_model = os.getenv("QUERRY_REWRITING_MODEL")
        self.documentation_context_retriver_model = os.getenv("DOCUMENTATION_CONTEXT_RETRIVER")
        self.context_caching_retriver_model = os.getenv("CONTEXT_CACHING_RETRIVER")
        self.final_response_generator_model = os.getenv("FINAL_ANSWER_GENERATOR")
        self.prompts_config = {
            "system_prompt_rewrite": "prompts/prompt_rewrite/system_prompt_rewrite.jinja2",
            "user_prompt_rewrite": "prompts/prompt_rewrite/user_prompt_rewrite.jinja2",
            "system_prompt_code_generator": "prompts/prompt_coder/system_prompt_code_generator.jinja2",
            "user_prompt_code_generator": "prompts/prompt_coder/user_prompt_code_generator.jinja2",
            "system_prompt_librari_retriver": "prompts/system_prompt_librari_retriver.jinja2",
            "user_prompt_librari_retriver": "prompts/user_prompt_librari_retriver.jinja2",
            "user_prompt_configuration_retriver": "prompts/prompt_user_config_retriver.jinja2",

        }

class Querry_Rewritter_Node(ClassifierConfig):
    def __init__(self):
        super().__init__()

    def process_batch(
        self,
        client_gemini,
        symstem_prompt: str,
        user_prompt: str,
        span=None,
    ) -> dict:
        """Process a batch of files using Gemini API"""

        messages = [
            {"role": "system", "content": symstem_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if span:
            generation = span.generation(
                name="gemini",
                model=self.querry_rewriting_model,
                model_parameters={"temperature": 0, "top_p": 1, "max_new_tokens": 8000},
                input={"system_prompt": symstem_prompt, "user_prompt": user_prompt},
            )

        try:
            completion, raw = client_gemini.chat.create_with_completion(
                messages=messages,
                response_model=GoalRewriteModel,
                generation_config={
                    "temperature": 0.0,
                    "top_p": 1,
                    "candidate_count": 1,
                    "max_output_tokens": 8000,
                },
                max_retries=10,
            )
            result = completion.model_dump()
            # if span:
            #     span.score(name="number_try", value=raw.n_attempts)
        except Exception as e:
            if span:
                generation.end(
                    output=None,
                    status_message=f"Error processing batch: {str(e)}, {traceback.format_exc()}",
                    level="ERROR",
                )
            raise e

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
    def querry_rewritter(
        self,
        symstem_prompt: str,
        user_prompt: str,
        GEMINI_API_KEY: str = "",
        ANTHROPIC_API_KEY: str = "",
        OPENAI_API_KEY: str = "",
        trace_id: str = "df8187ba-a07e-4ea9-9117-5a7662eaa063",
    ) -> str:
        span = get_langfuse_context().get("span")

        # Configure safety settings
        safe = SAFE

        # Configure Gemini with API key from request if provided
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
        else:
            # Use default API key from environment
            genai.configure()
            
        client_gemini = instructor.from_gemini(
            client=genai.GenerativeModel(
                model_name=self.querry_rewriting_model, safety_settings=safe
            ),
            mode=instructor.Mode.GEMINI_JSON,
        )

        rewrite = self.process_batch(client_gemini, symstem_prompt, user_prompt, span)

        return rewrite

                
class Documentation_Context_Retriver_Node(ClassifierConfig):
    def __init__(self):
        super().__init__()

    @trace
    def documentation_context_retriver(
        self,
        symstem_prompt: str,
        user_prompt: str,
        max_workers: int = 10,  # Number of parallel workers
        config_doc: dict = None,
        documentation_md: dict = None,
        GEMINI_API_KEY: str = "",
        ANTHROPIC_API_KEY: str = "",
        OPENAI_API_KEY: str = "",
        trace_id: str = "df8187ba-a07e-4ea9-9117-5a7662eaa063",
    ) -> str:
        span = get_langfuse_context().get("span")
        # if span:
        #     span.set("batch_size", batch_size)
        #     span.set("max_workers", max_workers)
        scores = [0]
        # Load documentations md and configs
        documentation = []

        documentation_md = documentation_md.get("documentation_md")
        config_doc = config_doc.get("config")
        if documentation_md and documentation_md[0] != {}:
            documentation = documentation + documentation_md
            if config_doc and config_doc[0] != {}:
                documentation = documentation + config_doc

        if len(documentation) == 0:
            return {"files_list": []}

        # Assign stable global file_ids for combined md+config set
        for index, doc in enumerate(documentation):
            doc["file_id"] = index
        # Configure safety settings
        safe = [
            {"category": "HARM_CATEGORY_DANGEROUS", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        # Configure Gemini with API key from request if provided
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
        else:
            # Use default API key from environment
            genai.configure()
            
        # Prepare chunking parameters
        chunk_size = int(os.getenv("CHUNK_SIZE", "400"))
        overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
        max_parallel = int(os.getenv("CHUNK_PARALLEL_LIMIT", "4"))
        max_selection_files = int(os.getenv("MAX_SELECTION_FILES", "50"))

        # Helper to perform one LLM retrieval call for a chunk
        def _retrieve_one(chunk_docs: list[dict]):
            local_user_prompt = user_prompt.replace("FILES_HERE", str(chunk_docs))
            client_gemini_local = instructor.from_gemini(
                client=genai.GenerativeModel(
                    model_name=self.documentation_context_retriver_model, safety_settings=safe
                ),
                mode=instructor.Mode.GEMINI_JSON,
            )
            local_messages = [
                {"role": "system", "content": symstem_prompt},
                {"role": "user", "content": local_user_prompt},
            ]
            completion, raw = client_gemini_local.chat.create_with_completion(
                messages=local_messages,
                response_model=get_necesary_files({"documentation": chunk_docs}),
                generation_config={
                    "temperature": 0.0,
                    "top_p": 1,
                    "candidate_count": 1,
                    "max_output_tokens": 8000,
                },
                max_retries=10,
            )
            return completion.model_dump()

        # use shared chunk_ranges utility for consistency

        # Decide single vs chunked path
        total_items = len(documentation)
        candidates: list[dict] = []

        if total_items <= chunk_size:
            # Single call as before
            local_user_prompt = user_prompt.replace("FILES_HERE", str(documentation))
            client_gemini = instructor.from_gemini(
                client=genai.GenerativeModel(
                    model_name=self.documentation_context_retriver_model, safety_settings=safe
                ),
                mode=instructor.Mode.GEMINI_JSON,
            )
            messages = [
                {"role": "system", "content": symstem_prompt},
                {"role": "user", "content": local_user_prompt},
            ]
            if span:
                generation = span.generation(
                    name="gemini",
                    model=self.documentation_context_retriver_model,
                    model_parameters={"temperature": 0, "top_p": 1, "max_new_tokens": 8000},
                    input={"system_prompt": symstem_prompt, "user_prompt": local_user_prompt},
                )
            completion, raw = client_gemini.chat.create_with_completion(
                messages=messages,
                response_model=get_necesary_files({"documentation": documentation}),
                generation_config={
                    "temperature": 0.0,
                    "top_p": 1,
                    "candidate_count": 1,
                    "max_output_tokens": 8000,
                },
                max_retries=10,
            )
            result = completion.model_dump()
            if span:
                generation.end(
                    output=result,
                    usage={
                        "input": raw.usage_metadata.prompt_token_count,
                        "output": raw.usage_metadata.candidates_token_count,
                    },
                )
            candidates = result.get("files_list", [])
        else:
            # Chunked parallel retrieval
            ranges = chunk_ranges(total_items, chunk_size, overlap)
            chunk_results: list[dict] = []
            with ThreadPoolExecutor(max_workers=max_parallel) as executor:
                futures = []
                for (s, e) in ranges:
                    chunk_docs = documentation[s:e]
                    futures.append(executor.submit(_retrieve_one, chunk_docs))
                for fut in futures:
                    try:
                        chunk_results.append(fut.result())
                    except Exception:
                        continue
            # Merge all candidates
            seen = set()
            for r in chunk_results:
                for item in (r or {}).get("files_list", []) or []:
                    fid = str(item.get("file_id"))
                    if fid in seen:
                        continue
                    seen.add(fid)
                    candidates.append(item)

        # Final LLM-based selection over merged candidates (top-N)
        # Construct documentation list with int file_ids for validation
        doc_candidates = []
        for it in candidates:
            try:
                doc_candidates.append({"file_name": it.get("file_name"), "file_id": int(it.get("file_id"))})
            except Exception:
                continue

        if not doc_candidates:
            return {"files_list": []}

        try:
            selected_list = llm_select_files(
                candidates=doc_candidates,
                system_prompt=symstem_prompt,
                user_prompt_template=user_prompt,
                safety_settings=safe,
                default_model_name=self.documentation_context_retriver_model,
                max_files=max_selection_files,
            )
            return {"files_list": selected_list}
        except Exception:
            # Fallback: truncate candidates deterministically
            ordered = sorted(candidates, key=lambda x: int(x.get("file_id", 0)))
            return {"files_list": ordered[:max_selection_files]}


class Context_Caching_Retriver_Node(ClassifierConfig):
    def __init__(self):
        super().__init__()

    def process_batch(
    self,
    client_gemini,
    symstem_prompt: str,
    user_prompt: str,
    span=None,
    documentation=None,
    cache_id=None,
    trace_id: str = "df8187ba-a07e-4ea9-9117-5a7662eaa063",
) -> dict:
        """Process a batch of files using Gemini API"""

        messages = [
            {"role": "system", "content": symstem_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Simulate a delay with random jitter
        # delay = random.uniform(0.1, 0.5)
        # time.sleep(delay)

        if span:
            generation = span.generation(
                name="gemini",
                model=self.context_caching_retriver_model,
                model_parameters={"temperature": 0, "top_p": 1, "max_new_tokens": 8000},
                input={
                    "system_prompt": symstem_prompt,
                    "user_prompt": cache_id + "\n\n" + user_prompt,
                },
            )

        try:
            completion, raw = client_gemini.chat.create_with_completion(
                messages=messages,
                response_model=get_necesary_files(documentation),
                generation_config={
                    "temperature": 0.0,
                    "top_p": 1,
                    "candidate_count": 1,
                    "max_output_tokens": 8000,
                },
                max_retries=5,
            )
            result = completion.model_dump()
            # if span:
            #     span.score(name="number_try", value=raw.n_attempts)
        except Exception as e:
            if span:
                generation.end(
                    output=None,
                    status_message=f"Error processing batch: {str(e)}, {traceback.format_exc()}",
                    level="ERROR",
                )
            raise e

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
    def context_caching_retrival(
        self,
        documentation: dict,
        cache_id: str,
        symstem_prompt: str,
        user_prompt: str,
        GEMINI_API_KEY: str = "",
        ANTHROPIC_API_KEY: str = "",
        OPENAI_API_KEY: str = "",
        trace_id: str = "df8187ba-a07e-4ea9-9117-5a7662eaa063",
    ) -> str:
        span = get_langfuse_context().get("span")
        # Configure safety settings
        safe = [
            {"category": "HARM_CATEGORY_DANGEROUS", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        # Configure Gemini with API key from request if provided
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
        else:
            # Use default API key from environment
            genai.configure()

        # getting the cached client
        cache = caching.CachedContent.get(cache_id)

        client_gemini = instructor.from_gemini(
            client=genai.GenerativeModel.from_cached_content(
                cached_content=cache, safety_settings=safe
            ),
            mode=instructor.Mode.GEMINI_JSON,
        )

        list_of_files = self.process_batch(
            client_gemini, symstem_prompt, user_prompt, span, documentation, cache_id
        )

        return list_of_files


    # moved to repo_chat/utils_retrieval.order_docs_stably

    def intelligent_file_selection(
        self,
        retrieved_files: list[dict],
        symstem_prompt: str,
        selection_user_prompt: str,
        max_files: int = int(os.getenv("MAX_SELECTION_FILES", "50")),
    ) -> list[dict]:
        """
        LLM-based selection among retrieved_files. Uses get_necesary_files schema
        and FILE_SELECTION_MODEL if provided; falls back to context_caching_retriver model.
        """
        # Deduplicate candidates and normalize
        candidates_map = {}
        for item in retrieved_files or []:
            try:
                fid = str(item.get("file_id"))
                fname = str(item.get("file_name"))
                if fid and fname and fid not in candidates_map:
                    candidates_map[fid] = {"file_name": fname, "file_id": int(fid)}
            except Exception:
                continue

        candidate_docs = list(candidates_map.values())
        if not candidate_docs:
            return []

        # Build prompt with candidates injected
        user_prompt_filled = selection_user_prompt.replace("FILES_HERE", str(candidate_docs))

        try:
            selected = llm_select_files(
                candidates=candidate_docs,
                system_prompt=symstem_prompt,
                user_prompt_template=user_prompt_filled,
                safety_settings=SAFE,
                default_model_name=self.context_caching_retriver_model,
                max_files=max_files,
            )
            if selected:
                return selected
        except Exception:
            pass

        # Fallback deterministic selection
        ordered = sorted(candidate_docs, key=lambda x: int(x.get("file_id", 0)))[:max_files]
        return [{"file_name": it.get("file_name"), "file_id": str(it.get("file_id"))} for it in ordered]

    @trace
    def retrieve_from_chunked_repository(
        self,
        repository_name: str,
        documentation: dict,
        symstem_prompt: str,
        user_prompt: str,
        max_parallel: int = int(os.getenv("CHUNK_PARALLEL_LIMIT", "4")),
        GEMINI_API_KEY: str = "",
        ANTHROPIC_API_KEY: str = "",
        OPENAI_API_KEY: str = "",
        trace_id: str = "df8187ba-a07e-4ea9-9117-5a7662eaa063",
    ) -> dict:
        span = get_langfuse_context().get("span")
        # Safety settings
        safe = [
            {"category": "HARM_CATEGORY_DANGEROUS", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        # Configure Gemini with API key if provided
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
        else:
            genai.configure()

        # Locate cache index (support both local and container paths)
        index_path_candidates = [
            Path("cache_index") / f"{repository_name}.json",
            Path("/app/cache_index") / f"{repository_name}.json",
        ]
        index_path = next((p for p in index_path_candidates if p.exists()), None)
        if index_path is None:
            raise FileNotFoundError(f"Cache index not found for repository {repository_name}")

        try:
            with open(index_path, "r") as f:
                repo_cache_info = json.load(f)
        except Exception as e:
            raise Exception(f"Failed to read cache index for {repository_name}: {e}")

        chunks = repo_cache_info.get("chunks", [])
        if not chunks:
            return {"files_list": []}

        # Rebuild the same stable order used during chunk creation
        ordered_docs = order_docs_stably(documentation)

        # Prepare parallel retrieval across chunk caches
        results_raw: list[dict] = []
        retrieval_errors = 0

        def _retrieve_one(chunk: dict) -> dict | None:
            cache_id = chunk.get("cache_id")
            fr = chunk.get("file_range", [0, -1])
            start, end = int(fr[0]), int(fr[1])
            # Slicing: end is inclusive in index, add +1
            chunk_docs = ordered_docs[start : end + 1]
            local_doc = {"documentation": chunk_docs}
            try:
                cache = caching.CachedContent.get(cache_id)
                client_gemini = instructor.from_gemini(
                    client=genai.GenerativeModel.from_cached_content(
                        cached_content=cache, safety_settings=safe
                    ),
                    mode=instructor.Mode.GEMINI_JSON,
                )
                return self.process_batch(
                    client_gemini,
                    symstem_prompt,
                    user_prompt,
                    span,
                    local_doc,
                    cache_id,
                )
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = {executor.submit(_retrieve_one, c): c for c in chunks}
            for fut in as_completed(futures):
                res = fut.result()
                if res is None:
                    retrieval_errors += 1
                    continue
                results_raw.append(res)

        # Merge and deduplicate by file_id
        merged: list[dict] = []
        seen_ids: set[str] = set()
        flat_candidates: list[dict] = []
        for r in results_raw:
            for item in r.get("files_list", []) or []:
                flat_candidates.append(item)
                fid = str(item.get("file_id"))
                if fid in seen_ids:
                    continue
                seen_ids.add(fid)
                merged.append({"file_name": item.get("file_name"), "file_id": fid})

        # Intelligent selection (rank + top-N)
        selected = self.intelligent_file_selection(
            retrieved_files=flat_candidates if flat_candidates else merged,
            symstem_prompt=symstem_prompt,
            selection_user_prompt=user_prompt,
        )
        return {"files_list": selected}


class Final_Response_Generator_Node(ClassifierConfig):
    def __init__(self):
        super().__init__()

    @trace
    def answer_user_querry_with_context(
        self,
        files_list: dict,
        files_list_md_config: dict,
        documentation: dict,
        documentation_md: dict,
        config: dict,
        cache_id: str,
        symstem_prompt: str,
        user_prompt: str,
        model_name: str = "",
        GEMINI_API_KEY: str = "",
        ANTHROPIC_API_KEY: str = "",
        OPENAI_API_KEY: str = "",
        trace_id: str = "df8187ba-a07e-4ea9-9117-5a7662eaa063",
        repository_name: str = "",
        ) -> str:
        span = get_langfuse_context().get("span")
        # Configure safety settings
        safe = SAFE

        # Configure Gemini with API key from request if provided
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
        else:
            # Use default API key from environment
            genai.configure()

        # Configure Anthropic client with API key from request if provided
        repository_set = set()
        # Get file names from the documentation : files_list_md_config
        for file in files_list_md_config:
            file_id = int(file["file_id"])
            file_name = file["file_name"]
            source_repository = file.get("source_repository", repository_name)
            repository_set.add(source_repository)
            if ".md" in file_name:
                path = documentation_md["documentation_md"][file_id]["file_paths"]
                try:
                    with open(path, "r") as f:
                        user_prompt += f"\n<repository_name:{source_repository}, file_name:{file_name}>\n" + f.read() + f"\n</repository_name:{source_repository}, file_name:{file_name}>"
                except:
                    # raise Exception(
                    #     f"Error while reading the file {path}, {traceback.format_exc()}"
                    # )
                    pass
            else:
                try:
                    path = config["config"][file_id]["file_paths"]
                    with open(path, "r") as f:
                        user_prompt += f"\n<repository_name:{source_repository}, file_name:{file_name}>\n" + f.read() + f"\n</repository_name:{source_repository}, file_name:{file_name}>"
                except:
                    # raise Exception(
                    #     f"Error while reading the file {path}, {traceback.format_exc()}"
                    # )
                    pass
        # Get file names from the documentation : files_list
        for file in files_list:
            file_id = int(file["file_id"])
            file_name = file["file_name"]
            source_repository = file.get("source_repository", repository_name)
            repository_set.add(source_repository)
            path = documentation["documentation"][file_id]["file_paths"]
            try:
                with open(path, "r") as f:
                    user_prompt += f"\n<repository_name:{source_repository}, file_name:{file_name}>\n" + f.read() + f"\n</repository_name:{source_repository}, file_name:{file_name}>"
            except:
                raise Exception(
                    f"Error while reading the file {path}, {traceback.format_exc()}"
                )

        # Add system prompt if provided
        symstem_prompt += f"\n\nThe *repositories you are working on are*: {repository_set}"
        user_prompt += f"\n\nThe *repositories you are working on are*: *{repository_set}*"

        # Determine which SDK to use based on model name
        def determine_sdk_type(model_name: str) -> str:
            """Determine which SDK to use based on model name"""
            model_lower = model_name.lower()
            if "gpt" in model_lower or model_lower.startswith("o"):
                return "openai"
            elif "claude" in model_lower:
                return "anthropic"
            elif "gemini" in model_lower:
                return "gemini"
            else:
                # Default to gemini for backward compatibility if model_name is empty or unrecognized
                return "gemini"

        # Use model_name if provided, otherwise fall back to environment variable
        effective_model_name = model_name or self.final_response_generator_model
        sdk_type = determine_sdk_type(effective_model_name)

        # Add user message
        try:
            if span:
                generation = span.generation(
                    name=sdk_type,
                    model=effective_model_name,
                    model_parameters={"temperature": 0, "top_p": 1, "max_new_tokens": 60000},
                    input={"system_prompt": symstem_prompt, "user_prompt": user_prompt},
                )

            Answer = None
            usage_metadata = None

            if sdk_type == "openai":
                logger.info(f"Using OpenAI SDK with model: {effective_model_name}")
                
                openai_api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
                if not openai_api_key:
                    raise ValueError(f"OpenAI API key is required for model '{effective_model_name}'. Please configure your OpenAI API key in the settings.")
                
                openai_client = OpenAI(api_key=openai_api_key)
                
                # Handle different OpenAI model types
                if effective_model_name.lower().startswith("o"):
                    # Handle O-series models (reasoning models)
                    logger.info(f"Using OpenAI reasoning model: {effective_model_name}")
                    response = openai_client.chat.completions.create(
                        model=effective_model_name,
                        messages=[
                            {"role": "system", "content": symstem_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens=60000,
                        temperature=0,
                        top_p=1
                    )
                else:
                    # Handle regular GPT models
                    logger.info(f"Using OpenAI GPT model: {effective_model_name}")
                    response = openai_client.chat.completions.create(
                        model=effective_model_name,
                        messages=[
                            {"role": "system", "content": symstem_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens=8000,
                        temperature=0,
                        top_p=1
                    )
                
                # Create a mock Answer object with .text attribute for compatibility
                class MockAnswer:
                    def __init__(self, text, usage):
                        self.text = text
                        self.usage_metadata = usage
                
                class MockUsage:
                    def __init__(self, prompt_tokens, completion_tokens):
                        self.prompt_token_count = prompt_tokens
                        self.candidates_token_count = completion_tokens
                
                Answer = MockAnswer(
                    response.choices[0].message.content,
                    MockUsage(response.usage.prompt_tokens, response.usage.completion_tokens)
                )

            elif sdk_type == "anthropic":
                logger.info(f"Using Anthropic SDK with model: {effective_model_name}")
                
                # Debug API key sources
                logger.info(f"ANTHROPIC_API_KEY parameter: {'***' if ANTHROPIC_API_KEY else 'empty/None'}")
                logger.info(f"ANTHROPIC_API_KEY parameter (first 15): {ANTHROPIC_API_KEY[:15] if ANTHROPIC_API_KEY else 'None'}")
                env_key = os.getenv("ANTHROPIC_API_KEY")
                logger.info(f"Environment ANTHROPIC_API_KEY: {'***' if env_key else 'empty/None'}")
                logger.info(f"Environment ANTHROPIC_API_KEY (first 15): {env_key[:15] if env_key else 'None'}")
                
                anthropic_api_key = ANTHROPIC_API_KEY or env_key
                logger.info(f"Final anthropic_api_key: {'***' if anthropic_api_key else 'empty/None'}")
                logger.info(f"Using API key from: {'parameter' if ANTHROPIC_API_KEY else 'environment'}")
                
                # Additional debugging - check API key format and length
                if anthropic_api_key:
                    logger.info(f"API key length: {len(anthropic_api_key)}")
                    logger.info(f"API key starts with: {anthropic_api_key[:15]}...")
                    logger.info(f"API key ends with: ...{anthropic_api_key[-10:]}")
                    # Check for common issues
                    if '\n' in anthropic_api_key or '\r' in anthropic_api_key:
                        logger.warning("API key contains newline characters!")
                    if ' ' in anthropic_api_key:
                        logger.warning("API key contains spaces!")
                    # Clean the API key
                    anthropic_api_key = anthropic_api_key.strip()
                    logger.info(f"Cleaned API key length: {len(anthropic_api_key)}")
                
                if not anthropic_api_key:
                    raise ValueError(f"Anthropic API key is required for model '{effective_model_name}'. Please configure your Anthropic API key in the settings.")
                
                anthropic_client = Anthropic(
                    api_key=anthropic_api_key,
                    timeout=Timeout(60.0 * 30, connect=5.0)  # 30 minutes timeout
                )
                
                response = anthropic_client.messages.create(
                    model=effective_model_name,
                    max_tokens=60000,
                    system=symstem_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                
                # Create a mock Answer object with .text attribute for compatibility
                class MockAnswer:
                    def __init__(self, text, usage):
                        self.text = text
                        self.usage_metadata = usage
                
                class MockUsage:
                    def __init__(self, prompt_tokens, completion_tokens):
                        self.prompt_token_count = prompt_tokens
                        self.candidates_token_count = completion_tokens
                
                Answer = MockAnswer(
                    response.content[0].text,
                    MockUsage(response.usage.input_tokens, response.usage.output_tokens)
                )

            elif sdk_type == "gemini":
                logger.info(f"Using Gemini SDK with model: {effective_model_name}")
                
                # Configure Gemini with API key if provided
                if GEMINI_API_KEY:
                    genai.configure(api_key=GEMINI_API_KEY)
                else:
                    genai.configure()
                
                final_answer_generator = genai.GenerativeModel(
                    model_name=effective_model_name,
                    safety_settings=safe,
                    generation_config={"temperature": 0, "top_p": 1, "max_output_tokens": 60000},
                )
                
                Answer = final_answer_generator.generate_content(symstem_prompt + "\n" + user_prompt)

            else:
                raise ValueError(f"Unsupported model '{effective_model_name}'. Please use models starting with 'gemini-', 'gpt-', 'o', or 'claude-'.")

            if span:
                generation.end(
                    output=f"# {effective_model_name} \n" + Answer.text,
                    usage={
                        "input": Answer.usage_metadata.prompt_token_count,
                        "output": Answer.usage_metadata.candidates_token_count,
                    },
                )
            return Answer.text
        
        except Exception as e:
            logger.error(f"Error while answering the user querry, {e}, traceback: {traceback.format_exc()}")
            raise Exception(f"Error while answering the user querry, {e}, traceback: {traceback.format_exc()}")
            

class Librairie_Service(ClassifierConfig):
    def __init__(self):
        super().__init__()
        self.trace_id = generate_trace_id()
        self.querry_rewritter = Querry_Rewritter_Node()
        self.doc_context_retriver = Documentation_Context_Retriver_Node()
        self.context_caching_retriver = Context_Caching_Retriver_Node()
        self.final_response_generator = Final_Response_Generator_Node()
    
    def run_pipeline_up_to_context_retrieval(self, repository_name: str, cache_id: str, documentation: dict,
            user_problem: str, documentation_md: dict, config_input: dict, GEMINI_API_KEY: str):
        """
        Run the pipeline up to context retrieval (steps 1-8) but don't call Final Response Generator.
        Returns all the context needed for final response generation.
        """
        
        trace_id = generate_trace_id()

        # 1. prompt_user_rewriter
        prompt_user_rewriter_output = self.template_manager.render_template(
            template_relative_path=self.prompts_config["user_prompt_rewrite"],
             context={"user_query": user_problem}
        )
        # 2. prompt_system_rewriter
        prompt_system_rewriter_output = self.template_manager.render_template(
            template_relative_path=self.prompts_config["system_prompt_rewrite"],
            context={"library_name": repository_name}
        )
        # 3. querry_rewriter
        querry_rewriter_output = self.querry_rewritter.querry_rewritter(
            symstem_prompt=prompt_system_rewriter_output,
            user_prompt=prompt_user_rewriter_output,
            GEMINI_API_KEY=GEMINI_API_KEY,
            trace_id=trace_id
        )
        # 4. prompt_system_librari_retriver
        prompt_system_librari_retriver_output = self.template_manager.render_template(
            template_relative_path=self.prompts_config["system_prompt_librari_retriver"],
            context={"repository_name": repository_name}
        )
        # 5. user_prompt_librari_retriver
        user_prompt_librari_retriver_output = self.template_manager.render_template(
            template_relative_path=self.prompts_config["user_prompt_librari_retriver"],
            context={"user_problem": querry_rewriter_output}
        )
        # 6. call documentation from context_caching_retriver node
        # Prefer chunked retrieval when cache_index exists; fallback to single cache
        try:
            files_from_chunks = self.context_caching_retriver.retrieve_from_chunked_repository(
                repository_name=repository_name,
                documentation=documentation,
                symstem_prompt=prompt_system_librari_retriver_output,
                user_prompt=user_prompt_librari_retriver_output,
                GEMINI_API_KEY=GEMINI_API_KEY,
                trace_id=trace_id
            )
            documentation_from_context_caching_retriver_output = files_from_chunks
        except Exception as e:
            logger.info(f"Chunked retrieval unavailable, falling back to single cache for {repository_name}: {e}")
            documentation_from_context_caching_retriver_output = self.context_caching_retriver.context_caching_retrival(
                cache_id=cache_id,
                documentation=documentation,
                symstem_prompt=prompt_system_librari_retriver_output,
                user_prompt=user_prompt_librari_retriver_output,
                GEMINI_API_KEY=GEMINI_API_KEY,
                trace_id=trace_id
            )
        
        # 7. user_prompt_config_retriver
        user_prompt_config_retriver_output = self.template_manager.render_template(
            template_relative_path=self.prompts_config["user_prompt_configuration_retriver"],
            context={"user_problem": querry_rewriter_output}
        )
        # 8. call documentation_context_retriver node
        md_documentation_output = self.doc_context_retriver.documentation_context_retriver(
            symstem_prompt=prompt_system_librari_retriver_output, # Uses output from step 4
            user_prompt=user_prompt_config_retriver_output,
            config_doc=config_input, # This is inputs.config
            documentation_md=documentation_md,
            GEMINI_API_KEY=GEMINI_API_KEY,
            trace_id=trace_id
        )

        # Return all context needed for final response generation
        return {
            "repository_name": repository_name,
            "cache_id": cache_id,
            "files_list": documentation_from_context_caching_retriver_output["files_list"],
            "files_list_md_config": md_documentation_output["files_list"],
            "documentation": documentation,
            "documentation_md": documentation_md,
            "config": config_input,
            "rewritten_query": querry_rewriter_output
        }
    
    def run_multi_repo_pipeline(self, repositories_data: dict, user_problem: str, GEMINI_API_KEY: str, ANTHROPIC_API_KEY: str, OPENAI_API_KEY: str, model_name: str = ""):
        """
        Run pipeline for multiple repositories.
        Steps 1-8 are run for each repository individually.
        Step 9-10 (Final Response Generator) is called once with all collected context.
        
        Args:
            repositories_data: Dict with repo_name -> {cache_id, documentation, documentation_md, config}
            user_problem: Original user query
            GEMINI_API_KEY: API key for Gemini
        """
        
        # Collect context from all repositories
        all_repo_contexts = []
        combined_files_list = []
        combined_files_list_md_config = []
        all_documentation = {}
        all_documentation_md = {}
        all_config = {}
        
        # Process each repository up to context retrieval
        for repo_name, repo_data in repositories_data.items():
            try:
                logger.info(f"Processing repository: {repo_name}")
                
                repo_context = self.run_pipeline_up_to_context_retrieval(
                    repository_name=repo_name,
                    cache_id=repo_data["cache_id"],
                    documentation=repo_data["documentation"],
                    user_problem=user_problem,
                    documentation_md=repo_data["documentation_md"],
                    config_input=repo_data["config"],
                    GEMINI_API_KEY=GEMINI_API_KEY
                )
                
                all_repo_contexts.append(repo_context)
                
                # Combine files lists with repository context
                for file_item in repo_context["files_list"]:
                    file_item["source_repository"] = repo_name
                    combined_files_list.append(file_item)
                
                for file_item in repo_context["files_list_md_config"]:
                    file_item["source_repository"] = repo_name
                    combined_files_list_md_config.append(file_item)
                
                # Combine documentation with repository prefixing
                if "documentation" in repo_context["documentation"]:
                    for doc_item in repo_context["documentation"]["documentation"]:
                        doc_item["source_repository"] = repo_name
                    all_documentation[f"{repo_name}_documentation"] = repo_context["documentation"]["documentation"]
                
                if "documentation_md" in repo_context["documentation_md"]:
                    for doc_item in repo_context["documentation_md"]["documentation_md"]:
                        doc_item["source_repository"] = repo_name
                    all_documentation_md[f"{repo_name}_documentation_md"] = repo_context["documentation_md"]["documentation_md"]
                
                if "config" in repo_context["config"]:
                    for config_item in repo_context["config"]["config"]:
                        config_item["source_repository"] = repo_name
                    all_config[f"{repo_name}_config"] = repo_context["config"]["config"]
                
                logger.info(f"Successfully processed context for repository: {repo_name}")
                
            except Exception as e:
                logger.error(f"Error processing repository {repo_name}: {str(e)}")
                # Continue with other repositories
                continue
        
        if not all_repo_contexts:
            raise Exception("No repositories were successfully processed")
        
        # Use the first repository's name for template context (or create a combined name)
        primary_repo_name = list(repositories_data.keys())[0]
        if len(repositories_data) > 1:
            library_name = f"Multi-Repository ({', '.join(repositories_data.keys())})"
        else:
            library_name = str(primary_repo_name)
        
        # 9. Generate prompts for final answer
        prompt_user_code_generator_output = self.template_manager.render_template(
            template_relative_path=self.prompts_config["user_prompt_code_generator"],
            context={"user_problem": user_problem}
        )
        prompt_system_code_generator_output = self.template_manager.render_template(
            template_relative_path=self.prompts_config["system_prompt_code_generator"],
            context={"library_name": library_name}
        )

        # 10. Call final_response_generator node ONCE with all collected context
        logger.info(f"Calling Final Response Generator with context from {len(all_repo_contexts)} repositories")
        
        # Use the first repository's cache_id for the final call (or could be modified to handle multiple)
        primary_cache_id = all_repo_contexts[0]["cache_id"]
        
        final_response_generator_output = self.final_response_generator.answer_user_querry_with_context(
            files_list=combined_files_list,
            files_list_md_config=combined_files_list_md_config,
            documentation={"documentation": sum(all_documentation.values(), [])},
            documentation_md={"documentation_md": sum(all_documentation_md.values(), [])},
            config={"config": sum(all_config.values(), [])},
            cache_id=primary_cache_id,
            symstem_prompt=prompt_system_code_generator_output,
            user_prompt=prompt_user_code_generator_output,
            model_name=model_name,
            GEMINI_API_KEY=GEMINI_API_KEY,
            ANTHROPIC_API_KEY=ANTHROPIC_API_KEY,
            OPENAI_API_KEY=OPENAI_API_KEY,
            trace_id=self.trace_id
        )

        return final_response_generator_output

    def run_pipeline(self, repository_name: str, cache_id: str, documentation: dict,
            user_problem: str, documentation_md: dict, config_input: dict, GEMINI_API_KEY: str, ANTHROPIC_API_KEY: str, OPENAI_API_KEY: str, model_name: str = ""):
        """
        Original single-repository pipeline - now uses the new context retrieval method
        """
        
        # Debug API keys received in run_pipeline
        logger.info(f"run_pipeline called with:")
        logger.info(f"  - repository_name: {repository_name}")
        logger.info(f"  - model_name: {model_name}")
        logger.info(f"  - GEMINI_API_KEY: {'***' if GEMINI_API_KEY else 'empty/None'}")
        logger.info(f"  - ANTHROPIC_API_KEY: {'***' if ANTHROPIC_API_KEY else 'empty/None'}")
        logger.info(f"  - OPENAI_API_KEY: {'***' if OPENAI_API_KEY else 'empty/None'}")
        
        # Get context from single repository
        repo_context = self.run_pipeline_up_to_context_retrieval(
            repository_name=repository_name,
            cache_id=cache_id,
            documentation=documentation,
            user_problem=user_problem,
            documentation_md=documentation_md,
            config_input=config_input,
            GEMINI_API_KEY=GEMINI_API_KEY
        )

        # 9. prompts for final answer
        prompt_user_code_generator_output = self.template_manager.render_template(
            template_relative_path=self.prompts_config["user_prompt_code_generator"],
            context={"user_problem": user_problem}
        )
        prompt_system_code_generator_output = self.template_manager.render_template(
            template_relative_path=self.prompts_config["system_prompt_code_generator"],
            context={"library_name": repository_name}
        )

        # 10. call final_response_generator node
        final_response_generator_output = self.final_response_generator.answer_user_querry_with_context(
            files_list=repo_context["files_list"],
            files_list_md_config=repo_context["files_list_md_config"],
            documentation=repo_context["documentation"],
            documentation_md=repo_context["documentation_md"],
            config=repo_context["config"],
            cache_id=repo_context["cache_id"],
            symstem_prompt=prompt_system_code_generator_output,
            user_prompt=prompt_user_code_generator_output,
            model_name=model_name,
            GEMINI_API_KEY=GEMINI_API_KEY,
            ANTHROPIC_API_KEY=ANTHROPIC_API_KEY,
            OPENAI_API_KEY=OPENAI_API_KEY,
            trace_id=generate_trace_id(),
            repository_name=repository_name
        )

        return final_response_generator_output



if __name__ == "__main__":
    import os
    import json
    import shutil
    import traceback

    # This test script will be placed directly in the if __name__ == "__main__" block.
    # Librairie_Service is already defined in this file.

    TEMP_DIR = "temp_test_files_for_librairie_service"



    print("--- Starting Test for Librairie_Service ---")


    # --- Prepare Fake Data for run_pipeline ---
    repository_name_test = "Arfxflix"
    cache_id_test = "test_cache_integration_001" # Ensure this cache_id exists if using actual caching system
    user_problem_test = "Presnt this repo in simple words"
    
    # The GEMINI_API_KEY is passed to run_pipeline.

    

    # This is the main "documentation" input, typically representing code files.
    documentation_input_test = None
    with open("backend/tests/tmp_test/documentation.json", "r") as f:
        documentation_input_test = {"documentation": json.load(f)}

    # This represents Markdown documentation files.
    documentation_md_input_test = None
    with open("backend/tests/tmp_test/documentation_md.json", "r") as f:
        documentation_md_input_test = {"documentation_md": json.load(f)}

    # This represents configuration files (e.g., JSON, YAML).
    config_input_test = None
    with open("backend/tests/tmp_test/config.json", "r") as f:
        config_input_test = {"config": json.load(f)}

    # --- Instantiate Service ---
    # Librairie_Service is defined in the current file.
    librairie_service_instance = Librairie_Service()

    # --- Run Pipeline ---
    print(f"\nRunning pipeline for repository: {repository_name_test}...")
    print(f"User problem: {user_problem_test}")
    final_result = None
    try:
        # Note: The 'cache_id' for context_caching_retrival implies a pre-existing cache.
        # For a first run or test, this might point to a non-existent cache unless your system
        # handles cache creation or if it's mocked.
        # The get_gemini_pro_25_response is also called in Final_Response_Generator_Node
        # ensure that is handled if testing offline.
        print(f"Using GEMINI_API_KEY: {'Provided' if os.getenv("GEMINI_API_KEY") else 'Not provided (will rely on env or default)'}")

        final_result = librairie_service_instance.run_pipeline(
            repository_name=repository_name_test,
            cache_id="cachedContents/vinldk2v9mojw3tbr1r99ni5g652snvru6cob138", #hardocded
            documentation=documentation_input_test,
            user_problem=user_problem_test,
            documentation_md=documentation_md_input_test,
            config_input=config_input_test,
            model_name="gemini-2.5-pro-preview-03-25",  # Test with a specific model
            GEMINI_API_KEY=os.getenv("GEMINI_API_KEY"),  # Pass the API key here
            ANTHROPIC_API_KEY=os.getenv("ANTHROPIC_API_KEY"),
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
        )
        print("\n--- Pipeline Execution Succeeded ---")
        print("Final Result:")
        # The result is expected to be a string (the generated answer).
        print(final_result)

    except Exception as e:
        print(f"\n--- Pipeline Execution Failed ---")
        print(f"An error occurred: {e}")
        print("Traceback:")
        traceback.print_exc()
    finally:
        print("\n--- Test for Librairie_Service Finished ---")
