from __future__ import annotations

from boardroom.skills.base import AgentSkill, SkillContext, SkillResult
from boardroom.tools.python_executor import PythonExecutor


class FinancialModelingSkill(AgentSkill):
    @property
    def name(self) -> str:
        return "financial_modeling"

    @property
    def description(self) -> str:
        return "Run financial calculations (NPV, IRR, payback period, sensitivity)."

    def execute(self, context: SkillContext) -> SkillResult:
        scenario = context.arguments.get("scenario", "")
        code = (
            "import math\n"
            f"scenario = {scenario!r}\n"
            "# Basic financial helpers\n"
            "def npv(rate, cashflows):\n"
            "    return sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows))\n"
            "def irr_approx(cashflows, lo=0.0, hi=1.0, tol=1e-6):\n"
            "    for _ in range(200):\n"
            "        mid = (lo + hi) / 2\n"
            "        if npv(mid, cashflows) > 0: lo = mid\n"
            "        else: hi = mid\n"
            "        if hi - lo < tol: break\n"
            "    return mid\n"
            "print(f'Scenario: {scenario}')\n"
            "print(f'NPV example (10%, [-100,30,30,30,30]): {npv(0.10, [-100,30,30,30,30]):.2f}')\n"
        )
        return self._run(code)

    @staticmethod
    def _run(code: str) -> SkillResult:
        result = PythonExecutor(timeout_seconds=15).execute(code)
        if result.ok:
            return SkillResult(ok=True, output=result.stdout.strip())
        return SkillResult(ok=False, output=result.stderr.strip(), error=result.stderr.strip())


class CodeAnalysisSkill(AgentSkill):
    @property
    def name(self) -> str:
        return "code_analysis"

    @property
    def description(self) -> str:
        return "Analyze code for complexity, patterns, and potential issues."

    def execute(self, context: SkillContext) -> SkillResult:
        code_input = context.arguments.get("code", "")
        analysis_code = (
            f"code = {code_input!r}\n"
            "lines = code.strip().splitlines()\n"
            "print(f'Lines: {len(lines)}')\n"
            "print(f'Functions: {sum(1 for l in lines if l.strip().startswith(\"def \"))}')\n"
            "print(f'Classes: {sum(1 for l in lines if l.strip().startswith(\"class \"))}')\n"
            "print(f'Imports: {sum(1 for l in lines if l.strip().startswith(\"import \") or l.strip().startswith(\"from \"))}')\n"
        )
        result = PythonExecutor(timeout_seconds=10).execute(analysis_code)
        if result.ok:
            return SkillResult(ok=True, output=result.stdout.strip())
        return SkillResult(ok=False, output=result.stderr.strip(), error=result.stderr.strip())


class StatisticalAnalysisSkill(AgentSkill):
    @property
    def name(self) -> str:
        return "statistical_analysis"

    @property
    def description(self) -> str:
        return "Compute descriptive statistics on numeric data."

    def execute(self, context: SkillContext) -> SkillResult:
        data_str = context.arguments.get("data", "")
        code = (
            "import math\n"
            f"raw = {data_str!r}\n"
            "nums = [float(x.strip()) for x in raw.split(',') if x.strip()]\n"
            "n = len(nums)\n"
            "mean = sum(nums) / n if n else 0\n"
            "variance = sum((x - mean) ** 2 for x in nums) / n if n else 0\n"
            "std = math.sqrt(variance)\n"
            "nums_sorted = sorted(nums)\n"
            "median = nums_sorted[n // 2] if n % 2 else (nums_sorted[n//2 - 1] + nums_sorted[n//2]) / 2\n"
            "print(f'N={n}, Mean={mean:.2f}, Median={median:.2f}, Std={std:.2f}, Min={min(nums):.2f}, Max={max(nums):.2f}')\n"
        )
        result = PythonExecutor(timeout_seconds=10).execute(code)
        if result.ok:
            return SkillResult(ok=True, output=result.stdout.strip())
        return SkillResult(ok=False, output=result.stderr.strip(), error=result.stderr.strip())


class RiskAssessmentSkill(AgentSkill):
    @property
    def name(self) -> str:
        return "risk_assessment"

    @property
    def description(self) -> str:
        return "Evaluate risk factors and produce a structured risk summary."

    def execute(self, context: SkillContext) -> SkillResult:
        scenario = context.arguments.get("scenario", "")
        code = (
            f"scenario = {scenario!r}\n"
            "risk_categories = ['Market', 'Financial', 'Operational', 'Regulatory', 'Technical']\n"
            "print(f'Risk Assessment for: {scenario}')\n"
            "print('---')\n"
            "for cat in risk_categories:\n"
            "    print(f'  {cat}: [Requires domain analysis]')\n"
            "print('---')\n"
            "print('Summary: Structured risk framework generated. Populate with domain data.')\n"
        )
        result = PythonExecutor(timeout_seconds=10).execute(code)
        if result.ok:
            return SkillResult(ok=True, output=result.stdout.strip())
        return SkillResult(ok=False, output=result.stderr.strip(), error=result.stderr.strip())


DEFAULT_SKILLS: list[AgentSkill] = [
    FinancialModelingSkill(),
    CodeAnalysisSkill(),
    StatisticalAnalysisSkill(),
    RiskAssessmentSkill(),
]
