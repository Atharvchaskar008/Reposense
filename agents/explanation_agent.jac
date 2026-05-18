# ExplanationAgent — plain-English repository intelligence

import from utils.summarizer { generate_summary }

walker ExplanationAgent {
    has repo_name: str = "",
        repo_path: str = "",
        files: list = [],
        findings: list = [],
        metrics: dict = {},
        summary: dict = {};

    can explain with entry {
        here.state = "RUNNING";
        here.last_action = "Generating repository intelligence";
        self.summary = generate_summary(
            self.repo_name,
            self.repo_path,
            self.files,
            self.findings,
            self.metrics
        );
        here.state = "COMPLETED";
        report self.summary;
    }
}
