from pathlib import Path
import pytest
from ia_memoria.security import SecurityError, normalize_project_id, safe_resolve

def test_project_id(): assert normalize_project_id("ia la pregunta") == "IA_LA_PREGUNTA"
def test_reject_parent(tmp_path: Path):
    with pytest.raises(SecurityError): safe_resolve(tmp_path,"../fuera.txt",must_exist=False)
def test_reject_absolute(tmp_path: Path):
    with pytest.raises(SecurityError): safe_resolve(tmp_path,"C:\\Windows\\win.ini",must_exist=False)
def test_allow_child(tmp_path: Path):
    path=safe_resolve(tmp_path,"20_PROJECTS/BAGO/estado.md",must_exist=False)
    assert path.is_relative_to(tmp_path)
