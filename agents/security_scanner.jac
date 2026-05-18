# SecurityScanner — CVE + secrets + exactly 3 LLM calls (2 by llm, 1 Python)

::py::
import os as _os
_featherless = _os.getenv("FEATHERLESS_API_KEY", "")
if _featherless:
    _os.environ["OPENAI_API_KEY"] = _featherless
    _os.environ["OPENAI_API_BASE"] = "https://api.featherless.ai/v1"
::py::

import from nodes.repo_nodes {
    RepoNode,
    DependencyNode,
    SecretNode,
    ReportNode
}
import from utils.github_tools {
    list_root_files,
    fetch_file_content,
    check_cve,
    scan_secrets_regex,
    build_cve_llm_input,
    build_secret_llm_input,
    get_risk_score_input,
    apply_llm_cve_ratings,
    parse_report_llm_output,
    pick_secret_scan_files,
    featherless_complete,
    save_report_json
}

glob llm_model = "openai/deepseek-ai/DeepSeek-V3-0324";
glob llm_max_tokens = 500;

sem llm_rate_cves = "Rate each package CVE severity as HIGH, MEDIUM, or LOW only.";
sem llm_final_report = "Write a brief security report with risk_score 0-100 and 3 fix recommendations.";

def llm_rate_cves(cve_list: str) -> str by llm(
    model_name=llm_model,
    max_tokens=llm_max_tokens
);

def llm_final_report(scan_summary: str) -> str by llm(
    model_name=llm_model,
    max_tokens=llm_max_tokens
);

walker SecurityScanner {
    has cve_rows: list = [],
        secret_rows: list = [],
        secret_type_list: list = [];

    can scan with entry {
        repos = [root -->][?:RepoNode];
        if not repos {
            print("No RepoNode found — run GraphBuilder first");
            disengage;
        }
        repo_node = repos[0];
        owner = repo_node.owner;
        repo_name = repo_node.repo_name;

        deps = [repo_node -->][?:DependencyNode];
        self.cve_rows = [];

        for dep in deps {
            result = check_cve(dep.name, dep.ecosystem);
            dep.cve_ids = result.get("cve_ids", []);
            self.cve_rows.append({
                "name": dep.name,
                "ecosystem": dep.ecosystem,
                "cve_ids": dep.cve_ids,
                "node": dep
            });
        }

        # --- LLM CALL 1 → DependencyNode.llm_rating ---
        vuln_rows = [];
        for row in self.cve_rows {
            if row.get("cve_ids") {
                vuln_rows.append(row);
            }
        }
        cve_input = vuln_rows if vuln_rows else self.cve_rows;
        cve_prompt = build_cve_llm_input(cve_input);

        if deps {
            deps[0].llm_rating = llm_rate_cves(cve_prompt);
            apply_llm_cve_ratings(deps[0].llm_rating, self.cve_rows);
            for row in self.cve_rows {
                dep_node = row.get("node");
                if dep_node {
                    dep_node.llm_rating = row.get("llm_rating", "LOW");
                    dep_node.severity = row.get("severity", "LOW");
                }
            }
        }

        # Secret scan (regex only) — max 3 files
        root_files = list_root_files(owner, repo_name);
        scan_files = pick_secret_scan_files(root_files, owner, repo_name);
        seen_types = {};

        for fpath in scan_files {
            content = fetch_file_content(owner, repo_name, fpath);
            hits = scan_secrets_regex(content, fpath);
            for hit in hits {
                stype = hit.get("type", "unknown");
                if stype in seen_types {
                    continue;
                }
                seen_types[stype] = True;
                self.secret_type_list.append(stype);
                self.secret_rows.append({
                    "type": stype,
                    "file": fpath,
                    "count": hit.get("count", 1)
                });
                sec = SecretNode(file_path=fpath, secret_type=stype);
                repo_node ++> sec;
            }
        }

        # --- LLM CALL 2: Python Featherless (secret risk) ---
        secret_prompt = build_secret_llm_input(self.secret_type_list);
        secret_explain = featherless_complete(
            "Explain security risk impact in 2-3 sentences for: "
            + secret_prompt,
            max_tokens=200
        );
        secret_nodes = [repo_node -->][?:SecretNode];
        for sec in secret_nodes {
            sec.risk_explanation = secret_explain;
        }

        # --- LLM CALL 3 → ReportNode.summary ---
        risk_input = get_risk_score_input(self.cve_rows, self.secret_rows);
        total = len(vuln_rows) + len(self.secret_rows);
        rep_node = ReportNode();
        rep_node.total_issues = total;
        repo_node ++> rep_node;

        rep_node.summary = llm_final_report(
            risk_input
            + " Provide risk_score 0-100 and 3 bullet recommendations."
        );

        parsed = parse_report_llm_output(rep_node.summary);
        rep_node.risk_score = parsed.get("risk_score", 50);
        rep_node.recommendations = parsed.get("recommendations", []);

        out = {
            "repo": owner + "/" + repo_name,
            "risk_score": rep_node.risk_score,
            "summary": rep_node.summary,
            "vulnerabilities": [],
            "secrets_found": [],
            "recommendations": rep_node.recommendations
        };

        for row in self.cve_rows {
            out["vulnerabilities"].append({
                "name": row.get("name", ""),
                "ecosystem": row.get("ecosystem", ""),
                "cve_ids": row.get("cve_ids", []),
                "severity": row.get("llm_rating", "LOW")
            });
        }

        for sec in secret_nodes {
            risk_snip = "";
            if sec.risk_explanation {
                risk_snip = sec.risk_explanation[:120];
            }
            out["secrets_found"].append({
                "type": sec.secret_type,
                "file": sec.file_path,
                "risk": risk_snip
            });
        }

        save_report_json("outputs/report.json", out);
        print("Risk score: " + str(rep_node.risk_score) + "/100");
        print("Summary: " + rep_node.summary[:200] + "...");
        print("Report saved to outputs/report.json");
    }
}
