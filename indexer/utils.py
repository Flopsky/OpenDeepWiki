import os
import ast
from typing import List, Dict
import uuid

import os

SAFE = [
            {"category": "HARM_CATEGORY_DANGEROUS", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
# List of patterns to ignore
ignore_list = [
    "pycache",
    ".gitignore",
    ".md",
    ".ipynb",
    "venv",
    ".git",
    ".idea",
    "node_modules",
    "build",
    "dist",
    "target",
    ".vscode",
    ".DS_Store",
    ".mypy_cache",
    ".pytest_cache",
    "__init__.py",  # Corrected from "init.py"
    ".txt",
    ".log",
    ".aux",
    ".bbl",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".lof",
    ".lot",
    ".out",
    ".toc",
    ".synctex.gz",
    ".egg-info",
    ".coverage",
    ".pytest_cache",
    ".ropeproject",
    ".ipynb_checkpoints",
    ".env",
    ".venv",
    "npm-debug.log",
    "yarn-error.log",
    ".pylintrc",
    ".cache",
    ".settings",
    ".classpath",
    ".project",
    ".metadata",
    "tags",
    "release",
    "debug",
    "bin",
    "obj",
    ".swp",  # Vim swap files
    "~",  # Emacs backup files
    ".swo",  # Vim undo files
    ".swn",  # Vim swap files (alternative)
    ".bak",  # Backup files
    ".tmp",  # Temporary files
    ".orig",  # Original files (often backups)
    ".rej",  # Patch rejection files
    ".lock",  # Lock files (various uses)
    ".log",  # Log files
    ".pdf",  # PDF documents
    ".doc",  # Word documents
    ".docx",  # Word documents (newer format)
    ".xls",  # Excel spreadsheets
    ".xlsx",  # Excel spreadsheets (newer format)
    ".ppt",  # PowerPoint presentations
    ".pptx",  # PowerPoint presentations (newer format)
    ".zip",  # Compressed archives
    ".tar",  # Tape archives
    ".gz",  # Gzip compressed files
    ".rar",  # RAR archives
    ".7z",  # 7-Zip archives
    ".dmg",  # macOS disk images
    ".iso",  # Disk image files
    ".exe",  # Executable files (Windows)
    ".dll",  # Dynamic link libraries (Windows)
    ".app",  # macOS application bundles
    ".pkg",  # macOS installer packages
    ".db",  # Database files (various types)
    ".sqlite",  # SQLite database files
    ".csv",  # Comma-separated value files
    ".json",  # JSON data files
    ".xml",  # XML data files
    ".yaml",  # YAML data files
    ".yml",  # YAML data files (alternative extension)
    ".cfg",  # Configuration files
    ".conf",  # Configuration files (alternative extension)
    ".ini",  # Initialization files
    ".pem",  # Privacy-enhanced mail files (often keys)
    ".crt",  # Certificate files
    ".key",  # Key files
    ".pfx",  # Personal Information Exchange files
    ".jks",  # Java KeyStore files
    ".dat",  # Data files (generic)
    ".bin",  # Binary files (generic)
    ".dump",  # Database or memory dumps
    ".sql",  # SQL scripts
    ".bak",  # Backup files (various types)
    ".old",  # Old versions of files
    ".draft",  # Draft documents
    ".media",  # Media files (generic)
    ".assets",  # Assets files (generic)
    ".resources",  # Resource files (generic)
    ".snap",  # Snapshots (various uses)
    ".image",  # Image files (generic)
    ".backup",  # Backup files (explicit)
    ".temp",  # Temporary files (alternative)
    ".download",  # Downloaded files (incomplete)
    ".part",  # Partially downloaded files
    ".crdownload",  # Chrome download files (incomplete)
    ".unconfirmed",  # Unconfirmed download files
    ".incomplete",  # Incomplete files
    ".journal",  # Journal files (various uses)
    ".fuse_hidden",  # Hidden files related to FUSE mounts
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".svg",
    ".mp3",
    ".wav",
    ".srt",
    ".flac",
    ".aac",
    ".ogg",
    ".wma",
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".wmv",
    ".flv",
    ".m4v",
    ".webm",
    ".m2ts",
    ".mts",
    ".3gp",
    ".m4a",
    ".aif",
    ".aiff",
    ".raw",
    ".psd",
    ".ai",
    ".eps",
    ".indd",
    ".blend",
    ".max",
    ".ma",
    ".mb",
    ".3ds",
    ".obj",
    ".fbx",
    ".dae",
    ".stl",
    ".wrl",
    ".x3d",
    ".ttf",
]


def has_file_extension(filename):
    """
    Check if a file has an extension.

    Args:
        filename (str): Name of the file to check

    Returns:
        bool: True if the file has an extension, False otherwise
    """
    return "." in filename and filename.rsplit(".", 1)[1].strip() != ""


def should_process_file(filepath):
    """
    Determine if a file should be processed based on ignore list and extension presence.

    Args:
        filepath (str): Full path of the file to check

    Returns:
        bool: True if the file should be processed, False otherwise
    """
    filename = os.path.basename(filepath)

    # Check if file matches any pattern in ignore list
    if any(forbidden in filepath for forbidden in ignore_list):
        return False

    # Check if file has an extension
    if not has_file_extension(filename):
        return False

    return True


def list_all_files(folder_path: str, include_md: bool) -> Dict[str, List[str]]:
    """
    Lists all valid files in the given folder and its subdirectories.

    Args:
        folder_path (str): Path to the folder to be analyzed.

    Returns:
        dict: A dictionary containing two lists:
              - 'all_files_with_path': Full paths of all valid files
              - 'all_files_no_path': A list of dictionaries, each with keys
                                    'file_name' and 'file_id'

    Raises:
        FileNotFoundError: If the folder_path doesn't exist
    """
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"The path {folder_path} does not exist")

    # Initialize lists to store file paths and names
    all_files_with_path = []
    all_files_no_path = []

    # Remove .md from ignore list if include_md is True
    if include_md:
        if ".md" in ignore_list:
            ignore_list.remove(".md")
        if ".yaml" in ignore_list:
            ignore_list.remove(".yaml")
        if ".yml" in ignore_list:
            ignore_list.remove(".yml")

    try:
        for root, _, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)

                if should_process_file(full_path) and "env_arxflix" not in full_path:
                    all_files_with_path.append(full_path)
                    all_files_no_path.append(
                        {"file_name": file, "file_id": len(all_files_with_path) - 1}
                    )

        return {
            "all_files_with_path": all_files_with_path,
            "all_files_no_path": all_files_no_path,
        }

    except Exception as e:
        raise Exception(f"Error while processing files: {str(e)}")
