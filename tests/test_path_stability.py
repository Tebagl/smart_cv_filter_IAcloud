import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.database import DatabaseManager
from src.backend.models import Base

class TestPathStability(unittest.TestCase):
    def setUp(self):
        # Determine base path
        try:
            self.base_path = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
        except Exception:
            self.base_path = Path(__file__).resolve().parent

    def test_database_path(self):
        """
        Test that the database is created in the correct location relative to the executable
        """
        # Initialize database
        db_manager = DatabaseManager()
        
        # Check data directory exists
        data_dir = self.base_path / 'data'
        self.assertTrue(data_dir.exists(), "Data directory should be created")
        
        # Check database file exists
        db_path = data_dir / 'smart_cv.db'
        self.assertTrue(db_path.exists(), "Database file should be created")
        
        # Verify database can be accessed
        session = db_manager.get_session()
        self.assertIsNotNone(session, "Should be able to create a database session")
        session.close()

    def test_output_directories(self):
        """
        Test that output directories are created correctly
        """
        # Define expected output directories
        output_dir = self.base_path / 'output'
        reclutados_dir = output_dir / 'RECLUTADOS'
        discarded_dir = output_dir / 'DISCARDED'

        # Check output directory exists
        self.assertTrue(output_dir.exists(), "Output directory should exist")
        # Crear el directorio si no existe
        discarded_dir.mkdir(parents=True, exist_ok=True) 
        # Check subdirectories exist
        self.assertTrue(reclutados_dir.exists(), "Reclutados directory should exist")
        self.assertTrue(discarded_dir.exists(), "Discarded directory should exist")

    def test_persistent_database(self):
        """
        Test that the database persists between multiple initializations
        """
        # First initialization
        db_manager1 = DatabaseManager()
        session1 = db_manager1.get_session()
        
        # Create a test record
        from src.backend.models import Candidate  
        # Crear un registro de prueba con atributos válidos
        test_candidate = Candidate(firstName="Test", lastName="Candidate", email="test@example.com")
        session1.add(test_candidate)
        session1.commit()
        candidate_id = test_candidate.id
        session1.close()

        # Second initialization
        db_manager2 = DatabaseManager()
        session2 = db_manager2.get_session()
        
        # Verify the record still exists
        retrieved_candidate = session2.query(Candidate).filter_by(id=candidate_id).first()
        self.assertIsNotNone(retrieved_candidate, "Database should persist records between sessions")
        session2.close()

if __name__ == '__main__':
    unittest.main()
