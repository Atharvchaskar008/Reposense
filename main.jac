# RepoSense entry — CLI scanner + JacCloud walker entry
# Local mission control UI: python server.py
# JacCloud: jac install && jac start main.jac --scale

import sys;
import from agents.graph_builder { GraphBuilder }
import from agents.security_scanner { SecurityScanner }
import from nodes.repo_nodes { ReportNode }

# Public walker for JacCloud / jac serve API (optional HTTP trigger)
walker:pub ScanRepo {
    has repo_url: str = "";

    can scan with entry {
        if not self.repo_url {
            report {"error": "repo_url required"};
            disengage;
        }
        root spawn GraphBuilder(repo_url=self.repo_url);
        root spawn SecurityScanner();
        reports = [root -->][?:ReportNode];
        if reports {
            rep = reports[0];
            report {
                "risk_score": rep.risk_score,
                "summary": rep.summary,
                "total_issues": rep.total_issues,
                "recommendations": rep.recommendations
            };
        } else {
            report {"error": "scan produced no report"};
        }
    }
}

with entry:__main__ {
    if len(sys.argv) < 2 {
        print("RepoSense CLI — token-optimized GitHub security scanner");
        print("Usage: jac run main.jac <github_url>");
        print("Example: jac run main.jac https://github.com/psf/requests");
        print("Mission control UI: python server.py");
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
