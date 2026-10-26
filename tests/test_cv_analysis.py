import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.cv_handler import CandidateRepository
from src.backend.analyzer import CVAnalyzer

class TestCVAnalysis(unittest.TestCase):
    def setUp(self):
        # Mockear la sesión de base de datos
        self.mock_session = MagicMock()
        self.repo = CandidateRepository(self.mock_session)

        # Mockear el analizador
        self.repo.analyzer = MagicMock(spec=CVAnalyzer)

    def test_process_cv_success(self):
        # Configurar el analizador para devolver un resultado exitoso
        self.repo.analyzer.analyze.return_value = {
            "apto": "SI",
            "puntuacion": 85,
            "motivo": "Cumple con todos los criterios."
        }

        # Texto de prueba
        raw_text = "Candidato con experiencia en ventas B2B y conocimiento del mercado tecnológico."

        # Ejecutar el método
        result = self.repo.process_cv(raw_text)

        # Verificar el resultado
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["decision"], "SI")
        self.assertEqual(result["reason"], "Cumple con todos los criterios.")

    def test_process_cv_failure(self):
        # Configurar el analizador para devolver un resultado fallido
        self.repo.analyzer.analyze.return_value = {
            "apto": "NO",
            "puntuacion": 40,
            "motivo": "No cumple con los criterios mínimos."
        }

        # Texto de prueba
        raw_text = "Candidato sin experiencia relevante."

        # Ejecutar el método
        result = self.repo.process_cv(raw_text)

        # Verificar el resultado
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["decision"], "NO")
        self.assertEqual(result["reason"], "No cumple con los criterios mínimos.")

if __name__ == "__main__":
    unittest.main()
