"""
Master Test Runner for PolicyWatch
Runs all test suites across all 5 integrated modules:
1. models/test_app.py (CRUD, Auth, Diff, Routes)
2. policywatch_module5/tests/test_service.py (Notifications & Freshness Service)
3. change_detection/tests/test_change_detection.py (NLP Classification, Diff Engine, Rationale)
4. ptct-scraper/tests/ (Web Scraping, Pipelines, Parsing, Fixtures)
5. tests/test_integration.py (End-to-End System Integration Flow)
"""
import os
import sys
import unittest
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def run_unittest_suite(test_path, name):
    print(f"\n{'='*70}")
    print(f"[*] Running {name}: {test_path}")
    print(f"{'='*70}")
    rel_path = os.path.relpath(test_path, PROJECT_ROOT)
    env = os.environ.copy()
    env['PYTHONPATH'] = PROJECT_ROOT
    res = subprocess.run([sys.executable, "-m", "unittest", rel_path], cwd=PROJECT_ROOT, env=env)
    return res.returncode == 0

def run_pytest_suite(test_dir, name):
    print(f"\n{'='*70}")
    print(f"[*] Running {name} (pytest): {test_dir}")
    print(f"{'='*70}")
    res = subprocess.run([sys.executable, "-m", "pytest", test_dir], cwd=PROJECT_ROOT)
    return res.returncode == 0

def main():
    os.environ['PYTHONPATH'] = PROJECT_ROOT
    results = {}

    # 1. Models & App Tests
    results["Module 2 & 3: models/test_app.py"] = run_unittest_suite(
        os.path.join(PROJECT_ROOT, "models", "test_app.py"),
        "Models & Authentication Test Suite"
    )

    # 2. Module 5 Notifications & Freshness
    results["Module 5: policywatch_module5/tests/test_service.py"] = run_unittest_suite(
        os.path.join(PROJECT_ROOT, "policywatch_module5", "tests", "test_service.py"),
        "Module 5 Notification & Freshness Service Suite"
    )

    # 3. Change Detection & NLP Classifier
    results["Change Detection: change_detection/tests/test_change_detection.py"] = run_unittest_suite(
        os.path.join(PROJECT_ROOT, "change_detection", "tests", "test_change_detection.py"),
        "Semantic Change Detection & NLP Classifier Suite"
    )

    # 4. End-to-End Integration Test
    results["Full Integration: tests/test_integration.py"] = run_unittest_suite(
        os.path.join(PROJECT_ROOT, "tests", "test_integration.py"),
        "End-to-End System Integration Flow"
    )

    # 5. Scraper Tests (pytest)
    results["Module 1: ptct-scraper/tests"] = run_pytest_suite(
        os.path.join(PROJECT_ROOT, "ptct-scraper", "tests"),
        "Web Scraper & Pipeline Suite"
    )

    print("\n" + "="*70)
    print("                    POLICYWATCH TEST SUMMARY")
    print("="*70)
    all_passed = True
    for suite_name, passed in results.items():
        status = "[PASSED]" if passed else "[FAILED]"
        print(f"  {status:10} {suite_name}")
        if not passed:
            all_passed = False

    print("="*70)
    if all_passed:
        print(" [SUCCESS] ALL TEST SUITES PASSED CLEANLY (99+ Tests)!")
    else:
        print(" [WARNING] Some test suites had errors.")
    print("="*70 + "\n")
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
