from pydantic import BaseModel, Field, model_validator
from typing import List, Literal


class FileClassification(BaseModel):
    """
    Single file classification entry.

    One output row must be produced for each input item. Use the exact input
    `file_id` and `file_name` without modification.
    """

    file_id: int = Field(
        description="Original identifier for the file from the input list",
        example=7,
    )
    file_name: str = Field(
        description="Exact file name as provided in the input",
        example="README.md",
    )
    classification: Literal["code_file", "doc_file", "configuration_file", "other"] = Field(
        description="Classification label",
        example="doc_file",
    )


def create_file_classification(
    file_name_for_verification: List[str], scores
) -> BaseModel:
    """
    Create a Pydantic model to validate the file classification response.

    - file_name_for_verification: the original input list used to ensure each item
      is classified exactly once. Each element is a dict with keys `file_id` and
      `file_name`.
    - scores: a single-item list used to track validation passes upstream.

    Returns a `FileClassifications` model enforcing completeness and no hallucination.
    """

    class FileClassifications(BaseModel):
        """
        List of file classifications corresponding 1:1 with the input files.
        """

        file_classifications: List[FileClassification] = Field(
            description="List of file classifications",
            example=[
                {"file_id": 1, "file_name": "README.md", "classification": "doc_file"},
                {"file_id": 2, "file_name": "main.py", "classification": "code_file"},
            ],
        )

        @model_validator(mode="after")
        def check_file_classification(cls, values):
            scores[0] += 1

            # Create sets for comparison
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
