"""
evaluate_optimized_100.py
Full 100-contract evaluation with optimized extraction prompts.
"""
import os, sys

# Add project root and src/ to import path
_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(_root, 'src'))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    print("[X] OPENAI_API_KEY not set"); sys.exit(1)

from recall_improvement_test import CONTRADICTION_RULES, CONTEXT_CONTRADICTION_RULES
import extractor as ext_module

# Patch answer prompt
b = ext_module.EXTRACTION_SYSTEM_PROMPT
m = "## Extraction Guidelines:"
ext_module.EXTRACTION_SYSTEM_PROMPT = (b[:b.index(m)] + CONTRADICTION_RULES + b[b.index(m):]) if m in b else CONTRADICTION_RULES + b

# Patch context prompt
b2 = ext_module.CONTEXT_EXTRACTION_PROMPT
m2 = "Rules:"
ext_module.CONTEXT_EXTRACTION_PROMPT = (b2[:b2.index(m2)] + CONTEXT_CONTRADICTION_RULES + "\n" + b2[b2.index(m2):]) if m2 in b2 else CONTEXT_CONTRADICTION_RULES + b2

print("[OK] Prompts patched")

from evaluate import EvaluationRunner, QUESTIONS, GROUND_TRUTH

runner = EvaluationRunner(
    contracts=sorted(GROUND_TRUTH.keys()),
    questions=[q["id"] for q in QUESTIONS],
    conditions=["ovrag", "plain"],
    output_dir=os.path.join(_root, "evaluation", "results", "optimized_100"),
    resume=True,
)
runner.run()
