import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.extractor import UniversalExtractor

class TestUniversalExtractor(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.dirname(__file__)
        self.txt_path = os.path.join(self.test_dir, "test_cv.txt")
        with open(self.txt_path, "w", encoding="utf-8") as f:
            f.write("Juan Perez\nIngeniero de Software\nExperiencia en Python")

    def tearDown(self):
        if os.path.exists(self.txt_path):
            os.remove(self.txt_path)

    def test_extract_txt(self):
        # Validation for regular txt file text extraction
        text = UniversalExtractor.extract_text(self.txt_path)
        self.assertIn("Juan Perez", text)
        self.assertIn("Python", text)

    def test_unsupported_format(self):
        # Validation that unsupported files raise an Error
        dummy_file = os.path.join(self.test_dir, "test.unknown")
        with open(dummy_file, "w") as f:
            f.write("test")
            
        with self.assertRaises(ValueError):
            UniversalExtractor.extract_text(dummy_file)
            
        os.remove(dummy_file)

    @patch('src.backend.extractor.pdfplumber')
    def test_extract_pdf_2_columns(self, mock_pdfplumber):
        # Mocking pdfplumber for a 2-column layout CV
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.width = 600
        mock_page.height = 800
        
        # Simulating the two split bounds
        left_mock = MagicMock()
        left_mock.extract_text.return_value = "Columna Izquierda\nDatos Personales: ..."
        
        right_mock = MagicMock()
        right_mock.extract_text.return_value = "Columna Derecha\nExperiencia Laboral: ..."
        
        # Handling the crop bbox side effects
        def within_bbox_side(bbox):
            # If the bounding box starts at x=0, it's the left column
            if bbox[0] == 0:
                return left_mock
            return right_mock
            
        mock_page.within_bbox.side_effect = within_bbox_side
        mock_pdf.pages = [mock_page]
        
        # Return the mocked PDF from the context manager mock
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        
        # Test the extraction
        text = UniversalExtractor._extract_from_pdf("dummy.pdf")
        
        self.assertIn("Columna Izquierda", text)
        self.assertIn("Columna Derecha", text)
        
        # Verify the parsing ordered the left column BEFORE the right column
        self.assertTrue(text.index("Columna Izquierda") < text.index("Experiencia Laboral"))

if __name__ == "__main__":
    unittest.main()
