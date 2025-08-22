import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest

from geny.geny_brain import GenyBrain


@pytest.fixture(scope="module")
def brain():
    return GenyBrain()


def test_lookup_advanced_datasets(brain):
    # Should find ImageNet
    result = brain.lookup_offline("imagenet")
    assert result and "visual database" in result.lower()
    # Should find COCO
    result = brain.lookup_offline("COCO")
    assert result and "object detection" in result.lower()


def test_lookup_ai_coding_ultra_overview(brain):
    # Should find AI/coding overview
    result = brain.lookup_offline("ai coding ultra overview")
    assert result and "advanced ai topics" in result.lower()
    # Should find python example
    result = brain.lookup_offline("python_infer_simple")
    assert result and "transformers" in result.lower()
    # Should find java example
    result = brain.lookup_offline("java_example_socket")
    assert result and "tcp client" in result.lower()


def test_lookup_fuzzy_and_substring(brain):
    # Fuzzy match for 'imagenett' (typo)
    result = brain.lookup_offline("imagenett")
    assert result and "visual database" in result.lower()
    # Fuzzy match for 'pythn train snipet' (typo)
    result = brain.lookup_offline("pythn train snipet")
    assert result and "training loop" in result.lower()
    # Substring match for 'squad' in a longer question
    result = brain.lookup_offline("vad är squad-datasetet?")
    assert result and "stanford question answering" in result.lower()
    # Substring in value
    result = brain.lookup_offline("python programming problems")
    assert result and "python programming problems" in result.lower()


def test_lookup_language_detection(brain):
    # Swedish question triggers Swedish bonus (åäö in svar)
    result = brain.lookup_offline("Vad är imagenet?")
    assert result and ("bild" in result.lower() or "databas" in result.lower())
    # English question triggers English bonus
    result = brain.lookup_offline("What is ImageNet?")
    assert result and ("visual database" in result.lower() or "image" in result.lower())
