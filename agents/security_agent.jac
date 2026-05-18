# SecurityAgent — heuristic vulnerability scanning

import from utils.security_scanner { scan_repository }

walker SecurityAgent {
    has repo_path: str = "",
        findings: list = [];

    can scan with entry {
        here.state = "RUNNING";
        here.last_action = "Scanning for vulnerabilities";
        self.findings = scan_repository(self.repo_path);
        here.state = "COMPLETED";
        report self.findings;
    }
}
