import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import logging

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src" / "backend"))

from reset_demo import reset_demo

class TestResetDemo(unittest.TestCase):
    def setUp(self):
        # Configurar un entorno de pruebas temporal
        self.test_dir = tempfile.mkdtemp()
        
        # Crear estructura de directorios de prueba
        self.data_dir = os.path.join(self.test_dir, 'src', 'data')
        self.output_dir = os.path.join(self.test_dir, 'src', 'backend', 'output')
        self.reclutados_dir = os.path.join(self.output_dir, 'RECLUTADOS')
        self.descartados_dir = os.path.join(self.output_dir, 'DESCARTADOS')
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.reclutados_dir, exist_ok=True)
        os.makedirs(self.descartados_dir, exist_ok=True)

    def tearDown(self):
        # Limpiar el directorio temporal después de cada prueba
        shutil.rmtree(self.test_dir)

    def test_reset_demo_success(self):
        # Crear archivos de prueba
        db_path = os.path.join(self.data_dir, 'smart_cv.db')
        reclutados_file = os.path.join(self.reclutados_dir, 'file1.txt')
        descartados_file = os.path.join(self.descartados_dir, 'file2.txt')
        
        # Crear archivos de prueba
        with open(db_path, 'w') as f:
            f.write('test data')
        with open(reclutados_file, 'w') as f:
            f.write('reclutados')
        with open(descartados_file, 'w') as f:
            f.write('descartados')
        
        # Ejecutar reset_demo con el directorio de prueba
        reset_demo(base_path=self.test_dir)
        
        # Verificar que los archivos fueron eliminados
        self.assertFalse(os.path.exists(db_path))
        self.assertEqual(len(os.listdir(self.reclutados_dir)), 0)
        self.assertEqual(len(os.listdir(self.descartados_dir)), 0)

    def test_reset_demo_no_files(self):
        # Eliminar todos los archivos y directorios
        for path in [
            os.path.join(self.test_dir, 'src', 'data', 'smart_cv.db'),
            os.path.join(self.test_dir, 'src', 'backend', 'output', 'RECLUTADOS'),
            os.path.join(self.test_dir, 'src', 'backend', 'output', 'DESCARTADOS')
        ]:
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
        
        # Configurar logger para capturar advertencias
        with self.assertLogs(level='WARNING') as log_cm:
            # Ejecutar reset_demo con directorios vacíos
            reset_demo(base_path=self.test_dir)
            
            # Verificar que se registraron advertencias
            warnings = [record for record in log_cm.records if record.levelno == logging.WARNING]
            self.assertEqual(len(warnings), 3, f"Advertencias capturadas: {log_cm.output}")
            
            # Verificar contenido de las advertencias
            warning_messages = [record.getMessage() for record in warnings]
            self.assertTrue(any('Base de datos no encontrada' in msg for msg in warning_messages))
            self.assertTrue(any('RECLUTADOS no encontrado' in msg for msg in warning_messages))
            self.assertTrue(any('DESCARTADOS no encontrado' in msg for msg in warning_messages))

    def test_reset_demo_error_handling(self):
        # Crear un archivo para simular la base de datos
        db_path = os.path.join(self.data_dir, 'smart_cv.db')
        os.makedirs(self.data_dir, exist_ok=True)
        with open(db_path, 'w') as f:
            f.write('test data')
        
        # Simular un error durante la eliminación
        with patch('reset_demo.os.remove', side_effect=PermissionError("Test error")), \
             self.assertLogs(level='ERROR') as log_cm:
            
            with self.assertRaises(PermissionError):
                reset_demo(base_path=self.test_dir)
            
            # Verificar que se registró el error
            self.assertTrue(any('Error de permisos al eliminar base de datos' in msg for msg in log_cm.output))

if __name__ == '__main__':
    unittest.main()
