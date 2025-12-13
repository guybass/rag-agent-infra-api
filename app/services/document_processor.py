import os
import uuid
from typing import BinaryIO
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from docx import Document as DocxDocument

from app.config import get_settings


class DocumentProcessor:
    """Service for processing and chunking documents."""

    def __init__(self):
        settings = get_settings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

    def process_file(
        self,
        file: BinaryIO,
        filename: str,
    ) -> tuple[str, list[str], list[dict]]:
        """
        Process an uploaded file and return chunks with metadata.

        Args:
            file: File-like object
            filename: Original filename

        Returns:
            Tuple of (document_id, texts, metadatas)
        """
        document_id = str(uuid.uuid4())
        extension = os.path.splitext(filename)[1].lower()

        # Extract text based on file type
        if extension == ".pdf":
            text = self._extract_pdf(file)
        elif extension in [".docx", ".doc"]:
            text = self._extract_docx(file)
        elif extension in [".txt", ".md", ".csv"]:
            text = file.read().decode("utf-8")
        else:
            raise ValueError(f"Unsupported file type: {extension}")

        # Split into chunks
        chunks = self.text_splitter.split_text(text)

        # Create metadata for each chunk
        metadatas = [
            {
                "filename": filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "file_type": extension,
            }
            for i in range(len(chunks))
        ]

        return document_id, chunks, metadatas

    def _extract_pdf(self, file: BinaryIO) -> str:
        """Extract text from PDF file."""
        reader = PdfReader(file)
        text_parts = []

        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

        return "\n\n".join(text_parts)

    def _extract_docx(self, file: BinaryIO) -> str:
        """Extract text from DOCX file."""
        doc = DocxDocument(file)
        text_parts = []

        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)

        return "\n\n".join(text_parts)

    def process_text(
        self,
        text: str,
        source_name: str = "direct_input",
    ) -> tuple[str, list[str], list[dict]]:
        """
        Process raw text and return chunks with metadata.

        Args:
            text: Raw text to process
            source_name: Name/identifier for the text source

        Returns:
            Tuple of (document_id, texts, metadatas)
        """
        document_id = str(uuid.uuid4())

        # Split into chunks
        chunks = self.text_splitter.split_text(text)

        # Create metadata for each chunk
        metadatas = [
            {
                "filename": source_name,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "file_type": "text",
            }
            for i in range(len(chunks))
        ]

        return document_id, chunks, metadatas
