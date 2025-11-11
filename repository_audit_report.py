#!/usr/bin/env python3
"""
Repository Audit Script
Analyzes the trading bot repository for:
- Duplicate code
- Unnecessary test files
- Code quality issues
- Strategy profitability analysis
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
import json

class RepositoryAuditor:
    def __init__(self, root_path: str = "/workspace"):
        self.root_path = Path(root_path)
        self.test_files: List[Path] = []
        self.strategy_files: List[Path] = []
        self.config_files: List[Path] = []
        self.duplicate_patterns: Dict[str, List[Path]] = {}
        self.issues: List[Dict] = []

    def scan_repository(self) -> None:
        """Scan repository and categorize files"""
        print("🔍 Scanning repository structure...")

        for file_path in self.root_path.rglob("*.py"):
            if file_path.is_file():
                filename = file_path.name.lower()

                # Categorize test files
                if filename.startswith("test_") or "test" in filename:
                    self.test_files.append(file_path)

                # Categorize strategy files
                if "strategy" in filename or "donchian" in filename:
                    self.strategy_files.append(file_path)

        # Find config files
        for file_path in self.root_path.rglob("*.json"):
            if file_path.is_file():
                self.config_files.append(file_path)

        print(f"   Found {len(self.test_files)} test files")
        print(f"   Found {len(self.strategy_files)} strategy files")
        print(f"   Found {len(self.config_files)} config files")

    def analyze_test_files(self) -> None:
        """Analyze test files for redundancy"""
        print("\n📋 Analyzing test files...")

        test_purposes: Dict[str, List[str]] = {}

        for test_file in self.test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract what the test is testing
                imports = re.findall(r'from\s+(\w+)\s+import', content)
                imports += re.findall(r'import\s+(\w+)', content)

                key = tuple(sorted(set(imports)))
                if key not in test_purposes:
                    test_purposes[key] = []
                test_purposes[key].append(test_file.name)

            except Exception as e:
                print(f"   ⚠️  Error reading {test_file.name}: {e}")

        # Find potential duplicates
        for imports, files in test_purposes.items():
            if len(files) > 1:
                self.issues.append({
                    "type": "duplicate_tests",
                    "severity": "medium",
                    "files": files,
                    "description": f"Multiple test files testing similar modules: {', '.join(files)}"
                })
                print(f"   ⚠️  Potential duplicate tests: {', '.join(files)}")

    def analyze_strategies(self) -> None:
        """Analyze strategy files"""
        print("\n📊 Analyzing strategy files...")

        for strategy_file in self.strategy_files:
            print(f"   Checking {strategy_file.name}...")
            try:
                with open(strategy_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                # Check for common issues
                if content.count('import') > 30:
                    self.issues.append({
                        "type": "excessive_imports",
                        "severity": "low",
                        "file": strategy_file.name,
                        "description": f"Excessive imports in {strategy_file.name}"
                    })

                # Check for duplicate function definitions
                functions = re.findall(r'def\s+(\w+)\s*\(', content)
                if len(functions) != len(set(functions)):
                    duplicates = [f for f in functions if functions.count(f) > 1]
                    self.issues.append({
                        "type": "duplicate_functions",
                        "severity": "high",
                        "file": strategy_file.name,
                        "functions": list(set(duplicates)),
                        "description": f"Duplicate function definitions: {', '.join(set(duplicates))}"
                    })
                    print(f"   ❌ Duplicate functions found: {', '.join(set(duplicates))}")

                # Check for unused imports
                imports = re.findall(r'import\s+(\w+)', content)
                for imp in imports:
                    if content.count(imp) == 1:  # Only appears in import line
                        self.issues.append({
                            "type": "unused_import",
                            "severity": "low",
                            "file": strategy_file.name,
                            "import": imp,
                            "description": f"Potentially unused import: {imp}"
                        })

            except Exception as e:
                print(f"   ⚠️  Error analyzing {strategy_file.name}: {e}")

    def analyze_backtest_results(self) -> Dict:
        """Analyze backtest results for profitability"""
        print("\n💰 Analyzing backtest results...")

        results = {
            "profitability": "unknown",
            "metrics": {},
            "files_found": []
        }

        # Check for backtest results CSV
        csv_path = self.root_path / "backtest_results.csv"
        if csv_path.exists():
            results["files_found"].append("backtest_results.csv")
            print(f"   ✓ Found {csv_path.name}")

        # Check for backtest results directory
        backtest_dir = self.root_path / "backtest_results"
        if backtest_dir.exists() and backtest_dir.is_dir():
            result_files = list(backtest_dir.glob("*.json")) + list(backtest_dir.glob("*.csv"))
            results["files_found"].extend([f.name for f in result_files])
            print(f"   ✓ Found {len(result_files)} result files in backtest_results/")

        # Check for daily equity JSON
        daily_eq_path = self.root_path / "daily_eq.json"
        if daily_eq_path.exists():
            results["files_found"].append("daily_eq.json")
            try:
                with open(daily_eq_path, 'r') as f:
                    equity_data = json.load(f)
                    results["metrics"]["equity_data"] = equity_data
                    print(f"   ✓ Loaded equity data")
            except Exception as e:
                print(f"   ⚠️  Error loading equity data: {e}")

        if not results["files_found"]:
            print("   ⚠️  No backtest results found")
            self.issues.append({
                "type": "missing_backtest_results",
                "severity": "medium",
                "description": "No backtest results found to analyze profitability"
            })

        return results

    def check_code_duplication(self) -> None:
        """Check for duplicate code patterns"""
        print("\n🔄 Checking for code duplication...")

        # Check for duplicate MT5 connection patterns
        mt5_files = list(self.root_path.glob("*mt5*.py"))
        if len(mt5_files) > 3:
            print(f"   ⚠️  Found {len(mt5_files)} MT5-related files - potential duplication")
            self.issues.append({
                "type": "duplicate_modules",
                "severity": "medium",
                "files": [f.name for f in mt5_files],
                "description": f"Multiple MT5 connection files may contain duplicate logic"
            })

    def generate_report(self) -> str:
        """Generate comprehensive audit report"""
        print("\n" + "="*60)
        print("📝 REPOSITORY AUDIT REPORT")
        print("="*60)

        report = []
        report.append("# Repository Audit Report\n")
        report.append(f"Total Issues Found: {len(self.issues)}\n")

        # Group by severity
        high = [i for i in self.issues if i.get('severity') == 'high']
        medium = [i for i in self.issues if i.get('severity') == 'medium']
        low = [i for i in self.issues if i.get('severity') == 'low']

        report.append(f"\n## Issues by Severity")
        report.append(f"- 🔴 High: {len(high)}")
        report.append(f"- 🟡 Medium: {len(medium)}")
        report.append(f"- 🟢 Low: {len(low)}\n")

        if high:
            report.append("\n### 🔴 High Severity Issues\n")
            for issue in high:
                report.append(f"- **{issue['type']}**: {issue['description']}\n")

        if medium:
            report.append("\n### 🟡 Medium Severity Issues\n")
            for issue in medium:
                report.append(f"- **{issue['type']}**: {issue['description']}\n")

        if low:
            report.append("\n### 🟢 Low Severity Issues\n")
            for issue in low:
                report.append(f"- **{issue['type']}**: {issue['description']}\n")

        # Recommendations
        report.append("\n## Recommendations\n")

        if len(self.test_files) > 10:
            report.append(f"1. **Consolidate test files**: Found {len(self.test_files)} test files. Consider consolidating similar tests.\n")

        if any(i['type'] == 'duplicate_functions' for i in self.issues):
            report.append("2. **Remove duplicate functions**: Duplicate function definitions found in strategy files.\n")

        if any(i['type'] == 'duplicate_modules' for i in self.issues):
            report.append("3. **Refactor MT5 modules**: Multiple MT5 connection files suggest code duplication.\n")

        report_text = "\n".join(report)
        print(report_text)

        return report_text

    def save_report(self, filename: str = "AUDIT_REPORT.md") -> None:
        """Save report to file"""
        report = self.generate_report()
        output_path = self.root_path / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\n✅ Report saved to {filename}")

    def run_full_audit(self) -> None:
        """Run complete audit"""
        print("🚀 Starting Repository Audit\n")

        self.scan_repository()
        self.analyze_test_files()
        self.analyze_strategies()
        self.analyze_backtest_results()
        self.check_code_duplication()
        self.save_report()

        print("\n✅ Audit complete!")

if __name__ == "__main__":
    auditor = RepositoryAuditor()
    auditor.run_full_audit()
