# ImpactAgent — blast radius via dependency graph traversal

import from utils.graph_builder { impact_analysis }

walker ImpactAgent {
    has graph: any = None,
        target: str = "auth",
        impact: dict = {};

    can analyze with entry {
        here.state = "RUNNING";
        here.last_action = "Computing blast radius";
        if self.graph {
            self.impact = impact_analysis(self.graph, self.target);
        }
        here.state = "COMPLETED";
        report self.impact;
    }
}
