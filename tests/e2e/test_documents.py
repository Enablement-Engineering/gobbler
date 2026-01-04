"""E2E tests for document conversion.

These tests require the Docling Docker container to be running.
Start with: docker compose up docling
"""

import pytest

from .helpers import has_markdown_structure, validate_markdown_output

pytestmark = pytest.mark.requires_docling


class TestPDFConversion:
    """Tests for PDF document conversion."""

    def test_convert_fillable_pdf_w4(self, run_gobbler, documents_dir):
        """Test converting IRS Form W-4 (fillable form with fields)."""
        pdf_path = documents_dir / "pdf" / "irs_form_w4.pdf"

        result = run_gobbler(
            ["document", str(pdf_path)],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

        # Check metadata
        assert validation["metadata"]["format"] == "pdf"

        # Should contain W-4 content
        body_lower = validation["body"].lower()
        assert "w-4" in body_lower or "withholding" in body_lower

    def test_convert_fillable_pdf_w9(self, run_gobbler, documents_dir):
        """Test converting IRS Form W-9 (fillable form)."""
        pdf_path = documents_dir / "pdf" / "irs_form_w9.pdf"

        result = run_gobbler(
            ["document", str(pdf_path)],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

    def test_convert_text_heavy_pdf(self, run_gobbler, documents_dir):
        """Test converting IRS instructions (text-heavy, multi-page)."""
        pdf_path = documents_dir / "pdf" / "irs_instructions_1040.pdf"

        result = run_gobbler(
            ["document", str(pdf_path), "--no-ocr"],  # Faster without OCR
            timeout=180,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

        # Instructions should have some content (Docling extraction varies)
        # The W-4/W-9 forms work better, this PDF may have complex layout
        assert validation["word_count"] > 20, "Instructions document too short"

    def test_convert_resume_pdf(self, run_gobbler, documents_dir):
        """Test converting a simple resume PDF."""
        pdf_path = documents_dir / "pdf" / "resume_sample.pdf"

        result = run_gobbler(
            ["document", str(pdf_path)],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

    def test_convert_pdf_to_file(self, run_gobbler, documents_dir, temp_output_dir):
        """Test saving PDF conversion to file."""
        pdf_path = documents_dir / "pdf" / "irs_form_w4.pdf"
        output_file = temp_output_dir / "w4.md"

        result = run_gobbler(
            ["document", str(pdf_path), "-o", str(output_file)],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_file.exists(), "Output file not created"

        content = output_file.read_text()
        validation = validate_markdown_output(content, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"


class TestDOCXConversion:
    """Tests for Word document conversion."""

    def test_convert_kitchen_sink_docx(self, run_gobbler, documents_dir):
        """Test converting comprehensive DOCX with all features."""
        docx_path = documents_dir / "docx" / "kitchen_sink.docx"

        result = run_gobbler(
            ["document", str(docx_path)],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

        # Check for preserved markdown structure
        structure = has_markdown_structure(validation["body"])
        assert structure["has_headings"], "DOCX headings not preserved"
        assert structure["has_bold"], "DOCX bold text not preserved"
        assert structure["has_lists"], "DOCX lists not preserved"
        assert structure["has_tables"], "DOCX tables not preserved"


class TestSpreadsheetConversion:
    """Tests for Excel spreadsheet conversion."""

    def test_convert_xlsx_small(self, run_gobbler, documents_dir):
        """Test converting small XLSX spreadsheet."""
        xlsx_path = documents_dir / "xlsx" / "sample_100kb.xlsx"

        result = run_gobbler(
            ["document", str(xlsx_path)],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

        # Spreadsheet should produce tables
        assert "|" in validation["body"], "No markdown tables in spreadsheet output"

    def test_convert_xlsx_medium(self, run_gobbler, documents_dir):
        """Test converting medium XLSX spreadsheet."""
        xlsx_path = documents_dir / "xlsx" / "sample_500kb.xlsx"

        result = run_gobbler(
            ["document", str(xlsx_path)],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

    def test_convert_legacy_xls(self, run_gobbler, documents_dir):
        """Test converting legacy XLS format (IRS statistics)."""
        xls_path = documents_dir / "xlsx" / "irs_statistics.xls"

        result = run_gobbler(
            ["document", str(xls_path)],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

        # Should have tabular data
        assert "|" in validation["body"], "No tables in XLS output"


class TestPresentationConversion:
    """Tests for PowerPoint conversion."""

    def test_convert_pptx_small(self, run_gobbler, documents_dir):
        """Test converting small PPTX presentation."""
        pptx_path = documents_dir / "pptx" / "sample_100kb.pptx"

        result = run_gobbler(
            ["document", str(pptx_path)],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

    def test_convert_pptx_medium(self, run_gobbler, documents_dir):
        """Test converting medium PPTX presentation."""
        pptx_path = documents_dir / "pptx" / "sample_500kb.pptx"

        result = run_gobbler(
            ["document", str(pptx_path)],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

    @pytest.mark.slow
    def test_convert_pptx_large(self, run_gobbler, documents_dir):
        """Test converting large PPTX presentation (1MB)."""
        pptx_path = documents_dir / "pptx" / "sample_1mb.pptx"

        result = run_gobbler(
            ["document", str(pptx_path)],
            timeout=180,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "document")
        assert validation["valid"], f"Validation errors: {validation['errors']}"


class TestDocumentErrors:
    """Tests for document conversion error handling."""

    def test_nonexistent_file_error(self, run_gobbler):
        """Test error handling for nonexistent file."""
        result = run_gobbler(
            ["document", "/nonexistent/path/document.pdf"],
            timeout=30,
        )

        assert result.returncode != 0, "Should fail for nonexistent file"

    def test_unsupported_format_error(self, run_gobbler, temp_output_dir):
        """Test error handling for unsupported file format."""
        # Create a fake file with unsupported extension
        fake_file = temp_output_dir / "test.xyz"
        fake_file.write_text("fake content")

        result = run_gobbler(
            ["document", str(fake_file)],
            timeout=30,
        )

        # Should fail or warn about unsupported format
        # (exact behavior depends on implementation)
        assert result.returncode != 0 or "error" in result.stderr.lower()
