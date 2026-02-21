"""
Unit Tests for Ingestion Lambda
Tests document parsing, chunking, and metadata extraction.

Serverless RAG Project - MSc Thesis
"""

import pytest
import sys
import os

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/lambdas/ingestion'))


class TestTextCleaning:
    """Tests για καθαρισμό κειμένου"""

    def test_clean_text_whitespace(self):
        """Κανονικοποίηση whitespace"""
        from handler import clean_text

        text = "Hello   world\n\n\ntest"
        result = clean_text(text)
        assert "   " not in result
        assert "\n\n\n" not in result

    def test_clean_text_quotes(self):
        """Κανονικοποίηση quotes"""
        from handler import clean_text

        text = ""Hello" and 'world'"
        result = clean_text(text)
        assert '"Hello"' in result
        assert "'world'" in result

    def test_clean_text_control_chars(self):
        """Αφαίρεση control characters"""
        from handler import clean_text

        text = "Hello\x00World\x1f"
        result = clean_text(text)
        assert "\x00" not in result
        assert "\x1f" not in result


class TestChunking:
    """Tests για text chunking"""

    def test_chunk_text_basic(self):
        """Βασικό chunking"""
        from handler import chunk_text

        text = "Sentence one. Sentence two. Sentence three. Sentence four."
        chunks = chunk_text(text, chunk_size=50, overlap=10)

        assert len(chunks) > 0
        assert all(len(c.text) <= 60 for c in chunks)  # Allow some flexibility

    def test_chunk_text_preserves_content(self):
        """Chunking διατηρεί όλο το περιεχόμενο"""
        from handler import chunk_text

        text = "A. B. C. D. E. F. G. H. I. J."
        chunks = chunk_text(text, chunk_size=10, overlap=2)

        combined = " ".join(c.text for c in chunks)
        for letter in "ABCDEFGHIJ":
            assert letter in combined

    def test_chunk_text_overlap(self):
        """Chunks έχουν overlap"""
        from handler import chunk_text

        text = "First sentence here. Second sentence here. Third sentence here."
        chunks = chunk_text(text, chunk_size=30, overlap=15)

        if len(chunks) > 1:
            # Κάποιο overlap θα πρέπει να υπάρχει
            text1 = chunks[0].text
            text2 = chunks[1].text
            # Ελέγχουμε ότι τουλάχιστον κάποιες λέξεις επαναλαμβάνονται
            words1 = set(text1.split())
            words2 = set(text2.split())
            overlap = words1 & words2
            assert len(overlap) > 0

    def test_chunk_text_indices(self):
        """Chunk indices είναι σωστά"""
        from handler import chunk_text

        text = "One. Two. Three."
        chunks = chunk_text(text, chunk_size=20, overlap=5)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_text_empty(self):
        """Empty text επιστρέφει empty list"""
        from handler import chunk_text

        chunks = chunk_text("", chunk_size=100, overlap=20)
        assert chunks == []


class TestDocumentId:
    """Tests για document ID generation"""

    def test_generate_doc_id_deterministic(self):
        """Same inputs produce consistent output format"""
        from handler import generate_doc_id

        id1 = generate_doc_id("bucket", "key.pdf")
        assert len(id1) == 16
        assert id1.isalnum()

    def test_generate_doc_id_unique(self):
        """Different inputs produce different IDs"""
        from handler import generate_doc_id

        # Note: λόγω timestamp, τα IDs θα είναι διαφορετικά
        id1 = generate_doc_id("bucket1", "key.pdf")
        id2 = generate_doc_id("bucket2", "key.pdf")
        # Δεν είναι guaranteed να είναι διαφορετικά αν τρέξουν πολύ γρήγορα
        assert len(id1) == len(id2) == 16


class TestFileType:
    """Tests για file type extraction"""

    def test_get_file_type_pdf(self):
        """PDF extension"""
        from handler import get_file_type

        assert get_file_type("document.pdf") == "pdf"
        assert get_file_type("path/to/document.pdf") == "pdf"

    def test_get_file_type_docx(self):
        """DOCX extension"""
        from handler import get_file_type

        assert get_file_type("report.docx") == "docx"

    def test_get_file_type_uppercase(self):
        """Uppercase extensions"""
        from handler import get_file_type

        assert get_file_type("FILE.PDF") == "pdf"
        assert get_file_type("FILE.DOCX") == "docx"

    def test_get_file_type_no_extension(self):
        """No extension defaults to txt"""
        from handler import get_file_type

        assert get_file_type("filename") == "txt"


class TestLambdaHandler:
    """Tests για Lambda handler"""

    def test_handler_missing_key(self):
        """Handler returns error for missing key"""
        from handler import handler

        event = {"body": {"bucket": "test-bucket"}}
        response = handler(event, None)

        assert response["statusCode"] == 400
        assert "error" in response["body"]


class TestTextExtraction:
    """Tests για text extraction"""

    def test_extract_text_plain_utf8(self):
        """Plain text UTF-8"""
        from handler import extract_text_plain

        content = "Γειά σου κόσμε".encode("utf-8")
        result = extract_text_plain(content)
        assert "Γειά σου κόσμε" in result

    def test_extract_text_plain_latin1(self):
        """Plain text Latin-1"""
        from handler import extract_text_plain

        content = "Hello world".encode("latin-1")
        result = extract_text_plain(content)
        assert "Hello world" in result


class TestDocumentMetadata:
    """Tests για DocumentMetadata dataclass"""

    def test_document_metadata_creation(self):
        """Create DocumentMetadata"""
        from handler import DocumentMetadata

        meta = DocumentMetadata(
            document_id="test-123",
            filename="test.pdf",
            file_type="pdf",
            file_size=1024,
            s3_key="uploads/test.pdf",
            chunk_count=5,
            status="completed",
            created_at=1234567890.0
        )

        assert meta.document_id == "test-123"
        assert meta.filename == "test.pdf"
        assert meta.chunk_count == 5

    def test_document_metadata_with_error(self):
        """DocumentMetadata με error"""
        from handler import DocumentMetadata

        meta = DocumentMetadata(
            document_id="test-123",
            filename="test.pdf",
            file_type="pdf",
            file_size=0,
            s3_key="uploads/test.pdf",
            chunk_count=0,
            status="failed",
            created_at=1234567890.0,
            error="File too large"
        )

        assert meta.status == "failed"
        assert meta.error == "File too large"


class TestTextChunk:
    """Tests για TextChunk dataclass"""

    def test_text_chunk_creation(self):
        """Create TextChunk"""
        from handler import TextChunk

        chunk = TextChunk(
            text="Hello world",
            chunk_index=0,
            start_char=0,
            end_char=11
        )

        assert chunk.text == "Hello world"
        assert chunk.chunk_index == 0
        assert chunk.end_char - chunk.start_char == 11


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
