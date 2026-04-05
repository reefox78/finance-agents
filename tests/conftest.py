"""
Fixtures partagées entre tous les tests.
"""
import pytest
import sys
import os

# Ajoute la racine du projet au path pour que les imports fonctionnent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
