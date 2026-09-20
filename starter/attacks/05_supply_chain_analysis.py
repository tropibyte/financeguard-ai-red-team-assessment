"""
Supply Chain Vulnerability Analysis.

Parses a Trivy JSON report and analyzes a Dockerfile for security issues.
Produces a structured risk assessment of the AI system's deployment pipeline.

Usage:
    python 05_supply_chain_analysis.py
    python 05_supply_chain_analysis.py --trivy-report ../06_trivy_report.json --dockerfile ../Dockerfile
"""
import json
import argparse
import os

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "05_supply_chain")


def parse_trivy_report(path):
    """
    Parse a Trivy JSON report and extract vulnerability details.

    The Trivy JSON format has a "Results" array, where each result has:
    - "Target": what was scanned (e.g., "debian 13.4" or "Python")
    - "Type": scan type (e.g., "debian", "python-pkg")
    - "Vulnerabilities": array of vulnerability objects

    Each vulnerability has: VulnerabilityID, Severity, PkgName,
    InstalledVersion, FixedVersion, Title, Description

    Args:
        path: Path to Trivy JSON report

    Returns:
        List of vulnerability dictionaries
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    vulns = []

    for result in data.get("Results", []):
        target = result.get("Target", "")
        target_type = result.get("Type", "")
        for v in (result.get("Vulnerabilities") or []):
            description = (v.get("Description") or "").strip()
            vulns.append({
                "id": v.get("VulnerabilityID", ""),
                "severity": (v.get("Severity") or "UNKNOWN").upper(),
                "package": v.get("PkgName", ""),
                "installed_version": v.get("InstalledVersion", ""),
                "fixed_version": v.get("FixedVersion", ""),
                "title": v.get("Title", ""),
                "description": description[:200],
                "target": target,
                "target_type": target_type,
            })

    return vulns


def analyze_dockerfile(path):
    """
    Analyze a Dockerfile for common security issues.

    Check for:
    1. Running as root (no USER directive) — HIGH
    2. Unpinned base image (no SHA256 digest) — MEDIUM
    3. COPY . (copies entire context including secrets) — MEDIUM
    4. No HEALTHCHECK — LOW
    5. Build tools left in production image — MEDIUM
    6. Unnecessary tools (curl, git) in production — LOW

    Args:
        path: Path to Dockerfile

    Returns:
        List of issue dictionaries with: issue, severity, detail, recommendation
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()
    lines = content.strip().split("\n")

    issues = []

    def instruction_present(keyword):
        return any(l.strip().upper().startswith(keyword) for l in lines)

    lowered = content.lower()

    # 1. Runs as root — no USER directive means the process (and any RCE
    #    exploit against it) has root inside the container.
    if not instruction_present("USER "):
        issues.append({
            "issue": "Container runs as root (no USER directive)",
            "severity": "HIGH",
            "detail": (
                "No USER instruction is present, so the app runs as root (UID 0). "
                "Any code execution flaw or container escape starts with full root."
            ),
            "recommendation": (
                "Create and switch to a non-root user, e.g. "
                "`RUN useradd -m appuser` then `USER appuser` before CMD."
            ),
        })

    # 2. Unpinned base image — no @sha256 digest means the base can change
    #    under you between builds (mutable tag = non-reproducible + tamperable).
    from_lines = [l for l in lines if l.strip().upper().startswith("FROM ")]
    if from_lines and not any("@sha256:" in l for l in from_lines):
        base = from_lines[0].strip().split()[1] if len(from_lines[0].split()) > 1 else "?"
        issues.append({
            "issue": "Unpinned base image (no SHA256 digest)",
            "severity": "MEDIUM",
            "detail": (
                f"Base image '{base}' is referenced by a mutable tag with no "
                "@sha256 digest, so builds are not reproducible and the tag can "
                "be repointed at a malicious image."
            ),
            "recommendation": (
                "Pin the base image by digest, e.g. "
                "`FROM python:3.11-slim@sha256:<digest>`."
            ),
        })

    # 3. COPY . — copies the whole build context into the image, including
    #    .env files, .git history, keys, caches.
    copy_all = any(
        l.strip().upper().startswith("COPY")
        and len(l.split()) >= 2 and l.split()[1] == "."
        for l in lines
    )
    if copy_all:
        issues.append({
            "issue": "COPY . copies the entire build context",
            "severity": "MEDIUM",
            "detail": (
                "`COPY . /app` bakes the whole context into the image — any .env, "
                ".git directory, credentials, or local artifacts get shipped."
            ),
            "recommendation": (
                "Copy only what is needed and add a strict .dockerignore "
                "(.env, .git, __pycache__, *.pt, tests/)."
            ),
        })

    # 4. No HEALTHCHECK — orchestrators cannot tell a wedged container from a
    #    healthy one, so failures go unnoticed.
    if not instruction_present("HEALTHCHECK"):
        issues.append({
            "issue": "No HEALTHCHECK defined",
            "severity": "LOW",
            "detail": (
                "Without a HEALTHCHECK the orchestrator cannot detect a hung or "
                "crashed app and will keep routing traffic to it."
            ),
            "recommendation": (
                "Add a HEALTHCHECK that probes the /health endpoint, e.g. "
                "`HEALTHCHECK CMD curl -f http://localhost:5001/health || exit 1`."
            ),
        })

    # 5. Build tools left in the production image — enlarge the attack surface
    #    and give an attacker a compiler for on-host exploitation.
    build_tools = [t for t in ("build-essential", "gcc", "g++", "make") if t in lowered]
    if build_tools:
        issues.append({
            "issue": f"Build tools present in final image ({', '.join(build_tools)})",
            "severity": "MEDIUM",
            "detail": (
                "Compilers/toolchains remain in the runtime image, bloating it and "
                "handing an attacker the tools to build further exploits in place."
            ),
            "recommendation": (
                "Use a multi-stage build: compile in a builder stage and copy only "
                "the runtime artifacts into a clean final image."
            ),
        })

    # 6. Unnecessary tools (curl, git) — network + repo tooling that eases
    #    lateral movement and data exfiltration if the container is popped.
    import re
    extra_tools = [t for t in ("curl", "git", "wget", "netcat", "nc")
                   if re.search(r"\b" + re.escape(t) + r"\b", lowered)]
    if extra_tools:
        issues.append({
            "issue": f"Unnecessary tools in image ({', '.join(extra_tools)})",
            "severity": "LOW",
            "detail": (
                "Tools like curl/git are not needed at runtime but give an "
                "attacker ready-made means to pull payloads or move laterally."
            ),
            "recommendation": (
                "Remove runtime tools not required by the app, or install them "
                "only in a builder stage."
            ),
        })

    return issues


def generate_report(vulns, dockerfile_issues):
    """Generate a structured supply chain risk report."""
    # TODO: Generate a report dictionary with:
    # - "summary": total vulnerabilities, severity breakdown, dockerfile issue count
    # - "high_severity_vulnerabilities": list of HIGH severity CVEs (top 15)
    # - "python_specific": vulnerabilities in Python packages
    # - "dockerfile_issues": from analyze_dockerfile()
    # - "risk_assessment": overall risk level and key concerns

    severity_counts = {}
    for v in vulns:
        sev = v.get("severity", "UNKNOWN")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # HIGH-severity CVEs, fixable ones first so remediation is obvious.
    high_vulns = [v for v in vulns if v.get("severity") == "HIGH"]
    high_vulns.sort(key=lambda v: (v.get("fixed_version") in (None, "", "N/A"),))
    high_severity = high_vulns[:15]

    # Python (application-layer) packages — the part the team actually controls.
    python_specific = [
        v for v in vulns if v.get("target_type") in ("python-pkg", "pip")
    ]

    fixable_high = [v for v in high_vulns if v.get("fixed_version")]
    dockerfile_high = [i for i in dockerfile_issues if i.get("severity") == "HIGH"]

    # Overall risk: HIGH count + a root container together warrant HIGH.
    n_high = severity_counts.get("HIGH", 0)
    n_crit = severity_counts.get("CRITICAL", 0)
    if n_crit or n_high >= 20 or dockerfile_high:
        risk_level = "HIGH"
    elif n_high or severity_counts.get("MEDIUM", 0) >= 20:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    key_concerns = []
    if dockerfile_high:
        key_concerns.append(
            "Container runs as root — any RCE in the Flask app yields root."
        )
    if python_specific:
        key_concerns.append(
            f"{len(python_specific)} HIGH vulnerabilities in Python packages, "
            "with fixes available."
        )
    if n_high:
        key_concerns.append(
            f"{n_high} HIGH-severity OS/package CVEs in the base image."
        )
    key_concerns.append(
        "AI-specific: model checkpoints and the FAISS index are copied in with "
        "no integrity verification, and dependencies are pinned by version but "
        "not by hash (dependency-confusion / tampering risk)."
    )

    report = {
        "summary": {
            "total_vulnerabilities": len(vulns),
            "severity_breakdown": severity_counts,
            "dockerfile_issues": len(dockerfile_issues),
            "fixable_high_count": len(fixable_high),
        },
        "high_severity_vulnerabilities": high_severity,
        "python_specific": python_specific,
        "dockerfile_issues": dockerfile_issues,
        "risk_assessment": {
            "overall_risk": risk_level,
            "key_concerns": key_concerns,
        },
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Supply Chain Vulnerability Analysis")
    parser.add_argument(
        "--trivy-report",
        default=os.path.join(os.path.dirname(__file__), "..", "06_trivy_report.json"),
    )
    parser.add_argument(
        "--dockerfile",
        default=os.path.join(os.path.dirname(__file__), "..", "Dockerfile"),
    )
    parser.add_argument(
        "--output",
        default=os.path.join(RESULTS_DIR, "supply_chain_report.json"),
    )
    args = parser.parse_args()
    if not os.path.dirname(args.output):
        args.output = os.path.join(RESULTS_DIR, args.output)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    print("Parsing Trivy report...")
    vulns = parse_trivy_report(args.trivy_report)

    print("Analyzing Dockerfile...")
    dockerfile_issues = analyze_dockerfile(args.dockerfile)

    report = generate_report(vulns, dockerfile_issues)

    # Print summary
    print(f"\n{'=' * 50}")
    print("  SUPPLY CHAIN RISK ASSESSMENT")
    print(f"{'=' * 50}")
    s = report["summary"]
    print(f"\n  Total vulnerabilities: {s['total_vulnerabilities']}")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = s["severity_breakdown"].get(sev, 0)
        if count:
            print(f"    {sev}: {count}")

    print(f"\n  Dockerfile issues: {s['dockerfile_issues']}")
    print(f"{'=' * 50}")

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report saved to {args.output}")


if __name__ == "__main__":
    main()
