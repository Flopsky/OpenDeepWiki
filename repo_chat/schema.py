from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional


def get_necesary_files(documentation: dict) -> BaseModel:
    class File(BaseModel):
        file_name: str = Field(
            description="The name of the file as it appears as file_name in the documentation",
            examples=["main.py", "utils.py"],
        )
        file_id: str = Field(
            description="The file id of the file as it appears as file_id in the documentation",
            examples=["241", "54"],
        )

    class ChosenFiles(BaseModel):
        justification: str = Field(
            description="The reasoning behind choosing the files, explaining why they are relevant",
        )

        files_list: List[File] = Field(
            description="The list of files that the user needs to look into to achieve their goal",
            examples=[
                [
                    {"file_name": "main.py", "file_id": "241"},
                    {"file_name": "utils.py", "file_id": "54"},
                ]
            ],
        )

        @model_validator(mode="after")
        def validate_files_list(cls, values):
            """
            checking that filename and file_id are in documentation["documentation"] file_list,
            Accumulating all errors to raise them only once
            """
            print(values)
            files_list = values.files_list
            errors = []
            documentation_files = documentation.get("documentation")
            for file in files_list:
                found = False
                for doc_file in documentation_files:
                    if file.file_name == doc_file.get(
                        "file_name"
                    ) and file.file_id == str(doc_file.get("file_id")):
                        found = True
                        break
                if not found:
                    errors.append(
                        f"File {file.file_name} with id {file.file_id} not found in documentation. "
                    )
                    print(
                        (
                            f"File ({file.file_name},{file.file_id}) not found in documentation"
                        )
                    )

            # make sure the justification is present to
            if not values.justification:
                errors.append("Justification is required")

            if errors:
                raise ValueError(
                    "\n".join(errors) + "correct all this errors. Respect the rules."
                )
            return values

    return ChosenFiles


class GoalRewriteModel(BaseModel):
    justification: str = Field(..., description="Explanation of the rewriting process")
    goal_rewrite: str = Field(
        ..., description="The rewritten sentence in goal-based format"
    )
