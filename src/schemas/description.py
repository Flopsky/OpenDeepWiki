from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional, Any
from jinja2 import Environment, FileSystemLoader
from pathlib import Path


class TemplateManager:
    """
    Handles loading and rendering of Jinja2 templates.
    """
    def __init__(self, default_search_dir: Path):
        # default_search_dir is the root from which template paths are resolved.
        # e.g. if path is "prompts/file.jinja2", default_search_dir is script's dir.
        self.default_search_dir = default_search_dir

    def render_template(self, template_relative_path: str, context: dict = None) -> str:
        """
        Loads and renders a Jinja2 template.
        template_relative_path is relative to the default_search_dir.
        """
        if context is None:
            context = {}

        full_template_relative_path = self.default_search_dir / template_relative_path
        
        template_dir_for_loader = full_template_relative_path.parent
        template_file_name = full_template_relative_path.name

        if not full_template_relative_path.exists():
            raise FileNotFoundError(f"Template file not found: {full_template_relative_path} (resolved from base {self.default_search_dir})")

        # Cache the Jinja2 environment per directory to avoid re-creating on each render
        if not hasattr(self, "_env_cache"):
            self._env_cache = {}
        cache_key = str(template_dir_for_loader)
        env = self._env_cache.get(cache_key)
        if env is None:
            env = Environment(loader=FileSystemLoader(searchpath=str(template_dir_for_loader)))
            self._env_cache[cache_key] = env
        template = env.get_template(template_file_name)
        return template.render(context)



def generate_code_structure_model_consize(code_text: str):
    class FunctionInfo(BaseModel):
        """
        Represents information about a function
        """

        function_name: str = Field(
            description="Name of the function", example="calculate_average"
        )
        function_description: str = Field(
            description="Description of what the function does",
            example="Calculate the average of a list of numbers",
        )

    class AttributeInfo(BaseModel):
        """
        Represents information about a class attribute
        """

        attribute_name: str = Field(
            description="Name of the attribute", example="data_store"
        )
        attribute_description: str = Field(
            description="Description of the attribute",
            example="Stores processed data in memory",
        )

    class ClassInfo(BaseModel):
        """
        Represents information about a class including its attributes and methods
        """

        class_name: str = Field(description="Name of the class", example="DataStore")
        class_description: str = Field(
            description="Description of the class",
            example="Handles data storage and retrieval",
        )
        attributes: List[AttributeInfo] = Field(
            description="Attributes of the class",
            example=[
                {
                    "attribute_name": "data",
                    "attribute_description": "Data storage for the class",
                }
            ],
        )
        functions_in_class: List[FunctionInfo] = Field(
            description="Functions of the class",
            example=[
                {
                    "function_name": "calculate_average",
                    "function_description": "Calculate the average of a list of numbers",
                }
            ],
        )

    def generate_code_structure_model(code_text: str) -> BaseModel:
        """
        Generates a Pydantic model based on the provided code text.
        """

        class CodeStructure(BaseModel):
            """
            Root model representing the entire code structure
            """

            global_code_description: str = Field(
                description="High-level summary of what the codebase or file does",
                example="Utility functions for mathematical operations and data management.",
            )
            functions_out_class: Optional[List[FunctionInfo]] = Field(
                None,
                description="List of functions not belonging to any class",
                example=[
                    {
                        "function_name": "calculate_sum",
                        "function_description": "Calculate the sum of a list of numbers",
                    }
                ],
            )
            classes: Optional[List[ClassInfo]] = Field(
                None,
                description="List of classes in the code",
                example=[
                    {
                        "class_name": "DataStore",
                        "class_description": "Handles data storage and retrieval",
                        "attributes": [
                            {
                                "attribute_name": "data",
                                "attribute_description": "Data storage for the class",
                            }
                        ],
                        "functions_in_class": [
                            {
                                "function_name": "calculate_average",
                                "function_description": "Calculate the average of a list of numbers",
                            }
                        ],
                    }
                ],
            )

            @model_validator(mode="after")
            def check_names_are_in_file(cls, values):
                """
                Ensure that all names mentioned in the model are present in the provided code text.
                Accumulate all errors and raise them once if the accumulation string is not empty
                """
                errors = []
                for function in (values.functions_out_class or []):
                    if function.function_name not in code_text:
                        errors.append(
                            f"Function {function.function_name} not found in code"
                        )
                for class_info in (values.classes or []):
                    if class_info.class_name not in code_text:
                        errors.append(
                            f"Class {class_info.class_name} not found in code"
                        )
                    for attribute in class_info.attributes:
                        if attribute.attribute_name not in code_text:
                            errors.append(
                                f"Attribute {attribute.attribute_name} not found in code"
                            )
                    for function in class_info.functions_in_class:
                        if function.function_name not in code_text:
                            errors.append(
                                f"Function {function.function_name} not found in code"
                            )
                if errors:
                    raise ValueError("\n".join(errors))
                return values

        return CodeStructure

    return generate_code_structure_model(code_text)


##########################################################################################################################################################


def generate_code_structure_model_precise(code_text: str):
    class FunctionInfo(BaseModel):
        """
        Represents information about a function
        """

        function_name: str = Field(
            description="Name of the function",
            example="calculate_average",
        )
        function_description: str = Field(
            description="Description of what the function does",
            example=(
                "Calculate the average of a list of numbers.\n"
                "Inputs: A list of numerical values.\n"
                "Output: A float representing the average of the input numbers."
            ),
        )

    class AttributeInfo(BaseModel):
        """
        Represents information about a class attribute
        """

        attribute_name: str = Field(
            description="Name of the attribute",
            example="data_store",
        )
        attribute_description: str = Field(
            description="Description of the attribute",
            example=(
                "Stores processed data in memory.\n"
                "Purpose: To maintain state and provide quick access to processed information."
            ),
        )

    class ClassInfo(BaseModel):
        """
        Represents information about a class including its attributes and methods
        """

        class_name: str = Field(
            description="Name of the class",
            example="DataStore",
        )
        class_description: str = Field(
            description="Description of the class",
            example=(
                "Handles data storage and retrieval.\n"
                "Purpose: To provide a structured way to manage and access data efficiently."
            ),
        )
        attributes: List[AttributeInfo] = Field(
            description="Attributes of the class",
            example=[
                {
                    "attribute_name": "data",
                    "attribute_description": (
                        "Stores data in memory.\n"
                        "Purpose: To hold processed data for quick access and manipulation."
                    ),
                }
            ],
        )
        functions_in_class: List[FunctionInfo] = Field(
            description="Functions/methods of the class",
            example=[
                {
                    "function_name": "calculate_average",
                    "function_description": (
                        "Calculates the average of a list of numbers.\n"
                        "Inputs: A list of numerical values.\n"
                        "Output: A float representing the average of the input numbers."
                    ),
                }
            ],
        )

    def generate_code_structure_model(code_text: str) -> BaseModel:
        """
        Generates a Pydantic model based on the provided code text.
        """

        class CodeStructure(BaseModel):
            """
            Root model representing the entire code structure
            """

            global_code_description: str = Field(
                description="Description of the entire code",
                example=(
                    "This code contains utility functions and classes for performing "
                    "mathematical operations and data management.\n"
                    "Purpose: To provide reusable components for data processing tasks.\n"
                    "Outputs: Efficient and accurate mathematical computations and data storage mechanisms."
                ),
            )
            functions_out_class: Optional[List[FunctionInfo]] = Field(
                None,
                description="List of functions not belonging to any class",
                example=[
                    {
                        "function_name": "calculate_sum",
                        "function_description": (
                            "Calculate the sum of a list of numbers.\n"
                            "Inputs: A list of numerical values.\n"
                            "Output: A float representing the total sum of the input numbers."
                        ),
                    }
                ],
            )
            classes: Optional[List[ClassInfo]] = Field(
                None,
                description="List of classes in the code",
                example=[
                    {
                        "class_name": "DataStore",
                        "class_description": (
                            "Handles data storage and retrieval.\n"
                            "Purpose: To manage and provide access to stored data efficiently.\n"
                            "Outputs: Methods for storing, retrieving, and manipulating data."
                        ),
                        "attributes": [
                            {
                                "attribute_name": "data",
                                "attribute_description": (
                                    "Stores data in memory.\n"
                                    "Purpose: To hold processed data for quick access and manipulation."
                                ),
                            }
                        ],
                        "functions_in_class": [
                            {
                                "function_name": "calculate_average",
                                "function_description": (
                                    "Calculates the average of a list of numbers.\n"
                                    "Inputs: A list of numerical values.\n"
                                    "Output: A float representing the average of the input numbers."
                                ),
                            }
                        ],
                    }
                ],
            )

            @model_validator(mode="after")
            def check_names_are_in_file(cls, values):
                """
                Ensure that all names mentioned in the model are present in the provided code text.
                Accumulate all errors and raise them once if the accumulation string is not empty
                """
                errors = []
                for function in values.functions_out_class or []:
                    if function.function_name not in code_text:
                        errors.append(
                            f"Function {function.function_name} not found in code"
                        )
                for class_info in values.classes or []:
                    if class_info.class_name not in code_text:
                        errors.append(
                            f"Class {class_info.class_name} not found in code"
                        )
                    for attribute in class_info.attributes:
                        if attribute.attribute_name not in code_text:
                            errors.append(
                                f"Attribute {attribute.attribute_name} not found in code"
                            )
                    for function in class_info.functions_in_class:
                        if function.function_name not in code_text:
                            errors.append(
                                f"Function {function.function_name} not found in code"
                            )
                if errors:
                    raise ValueError("\n".join(errors))
                return values

        return CodeStructure

    return generate_code_structure_model(code_text)


##############################################################################
#### compress informations from md files


class TextChunkInfo(BaseModel):
    """
    Represents a compressed chunk of text with a brief summary.
    """

    summary: str = Field(
        description="A concise summary of the information contained in the text chunk.",
        example="Introduction to the data processing pipeline and its main components.",
    )
    keywords: List[str] = Field(
        description="A list of important keywords present in the text chunk.",
        example=["data processing", "pipeline", "components", "input", "output"],
    )
    context_cues: Optional[List[str]] = Field(
        description="Contextual cues that help understand the nature of the information (e.g., 'purpose', 'example', 'note').",
        example=["purpose", "overview"],
        default=None,
    )


class SectionCompression(BaseModel):
    """
    Represents a compressed section of a document.
    """

    title: str = Field(
        description="Title of the section.",
        example="Data Processing Pipeline",
    )
    compressed_chunks: List[TextChunkInfo] = Field(
        description="A list of compressed text chunks within this section.",
    )


class DocumentCompression(BaseModel):
    """
    Represents the compressed information from a documentation file.
    """

    overview_summary: Optional[TextChunkInfo] = Field(
        description="A high-level summary of the entire document.",
        default=None,
    )
    sections: List[SectionCompression] = Field(
        description="A list of compressed sections within the document.",
    )


######################################################
##### extract info from configuration file


class KeyPurpose(BaseModel):
    """
    Represents the purpose of a configuration key.
    """

    key_name: str = Field(description="Name of the configuration key")
    purpose: str = Field(description="A brief description of the key's purpose")
    is_sensitive: bool = Field(
        default=False,
        description="Indicates if this key likely holds sensitive information",
    )


class SectionPurpose(BaseModel):
    """
    Represents the purpose of a section within the configuration.
    """

    section_name: str = Field(description="Name of the section")
    purpose: str = Field(description="A brief description of the section's purpose")
    is_sensitive: bool = Field(
        default=False,
        description="Indicates if this section likely contains sensitive information",
    )
    key_purposes: List[KeyPurpose] = Field(
        default=[], description="List of key purposes within this section"
    )


class YamlBrief(BaseModel):
    """
    Provides a brief overview of the YAML file's purpose and key elements.
    """

    file_purpose: str = Field(
        description="A concise summary of the overall purpose of this YAML file"
    )
    sections: List[SectionPurpose] = Field(
        default=[], description="List of significant sections and their purposes"
    )
    standalone_keys: List[KeyPurpose] = Field(
        default=[],
        description="List of key-value pairs not part of a distinct section",
    )
