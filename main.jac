# RepoSense — token-optimized GitHub security scanner (JacHacks 2026)

import sys;
import from agents.graph_builder { GraphBuilder }
import from agents.security_scanner { SecurityScanner }
import from nodes.repo_nodes { ReportNode }

with entry:__main__ {
    if len(sys.argv) < 2 {
        print("Usage: jac run main.jac <github_url>");
        print("Example: jac run main.jac https://github.com/pallets/flask");
    } else {
        repo_url = sys.argv[1];
        print("RepoSense scanning: " + repo_url);

        root spawn GraphBuilder(repo_url=repo_url);
        root spawn SecurityScanner();

        reports = [root -->][?:ReportNode];
        if reports {
            rep = reports[0];
            print("\n=== Security Report ===");
            print("Risk Score: " + str(rep.risk_score) + "/100");
            print("Total Issues: " + str(rep.total_issues));
            print("Summary: " + rep.summary);
            if rep.recommendations {
                print("Recommendations:");
                for rec in rep.recommendations {
                    print("  - " + rec);
                }
            }
        }

        print("\nReport saved to outputs/report.json");
    }
}
