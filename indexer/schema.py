from pydantic import BaseModel, Field, model_validator, model_serializer
from typing import List, Optional


class FileClassifaction(BaseModel):
    """
    Used to classify a file
    """

    file_id: int = Field(description="the original id of the file", example=[3, 30])
    file_name: str = Field(description="Name of the file", example="example.pdf")
    classification: str = Field(
        description="""Classification of the file which can be one of the following :
            - code_file
            - doc_file
            - configuration_file
            - other""",
        example="doc_file",
    )


def create_file_classification(
    file_name_for_verification: List[str], scores
) -> BaseModel:
    """
    input :
    file_name_for_verification  is used to check that all file are classified

    ouput :
        A type FileClassifications which all constrain used to classify files
    """

    class FileClassifications(BaseModel):
        """
        Model Used to classify files
        """

        file_classifications: List[FileClassifaction] = Field(
            description="List of file classifications",
            example=[
                {"file_name": "example.pdf", "classification": "doc_file"},
                {"file_name": "example.txt", "classification": "code_file"},
            ],
        )

        @model_validator(mode="after")
        def check_file_classification(cls, values):
            scores[0] += 1

            # Create sets of dictionaries for comparison
            classified_files = {
                (file_classification.file_name, file_classification.file_id)
                for file_classification in values.file_classifications
            }

            original_files = {
                (file_info["file_name"], file_info["file_id"])
                for file_info in file_name_for_verification
            }

            # Find missing and hallucinated files
            missing_files = original_files - classified_files
            hallucinated_files = classified_files - original_files

            # Prepare error message if needed
            error_messages = []

            if missing_files:
                missing_files_str = ", ".join(
                    f"(name: {name}, id: {id})" for name, id in missing_files
                )
                error_messages.append(
                    f"All files must be classified, you forgot these files: {missing_files_str}"
                )

            if hallucinated_files:
                hallucinated_files_str = ", ".join(
                    f"(name: {name}, id: {id})" for name, id in hallucinated_files
                )
                error_messages.append(
                    f"The original file names should be maintained, you hallucinated these files: {hallucinated_files_str}"
                )

            if error_messages:
                raise ValueError(" ".join(error_messages))

            return values

    return FileClassifications


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
            description="Attribus of the class",
            example={
                """
                [
                {
                    "attribute_name": "data",
                    "attribute_description": "Data storage for the class"
                }
                ]
                """
            },
        )
        functions_in_class: List[FunctionInfo] = Field(
            description="Fonctions of the class",
            example={
                """
                [
                {
                    "function_name": "calculate_average",
                    "function_description": "Calculate the average of a list of numbers"
                }
                ]
                """
            },
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
                example="This code contains functions for mathematical operations",
            )
            functions_out_class: Optional[List[FunctionInfo]] = Field(
                None,
                description="List of functions not belonging to any class",
                example=[
                    """
                [
                    {
                    "function_name": "calculate_sum",
                    "function_description": "Calculate the sum of a list of numbers"
                    }
                ]
                """
                ],
            )
            classes: Optional[List[ClassInfo]] = Field(
                None,
                description="List of classes in the code",
                example=[
                    """
                    [
                        {
                            "class_name": "DataStore",
                            "class_description": "Handles data storage and retrieval",
                            "attributes": [
                                {
                                    "attribute_name": "data",
                                    "attribute_description": "Data storage for the class"
                                }
                            ],
                            "functions_in_class": [
                                {
                                    "function_name": "calculate_average",
                                    "function_description": "Calculate the average of a list of numbers"
                                }
                            ]
                        }
                    ]
                    """
                ],
            )

            @model_validator(mode="after")
            def check_names_are_in_file(cls, values):
                """
                Ensure that all names mentioned in the model are present in the provided code text.
                Accumulate all errors and raise them once if the accumlation string is not empty
                """
                errors = []
                for function in values.functions_out_class:
                    if function.function_name not in code_text:
                        errors.append(
                            f"Function {function.function_name} not found in code"
                        )
                for class_info in values.classes:
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



class ClassifyRequest(BaseModel):
    text: str

class ClassifyResponse(BaseModel):
    result: str

