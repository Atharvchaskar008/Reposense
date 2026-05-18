# DependencyAgent — clone, parse, build dependency graph

import from utils.repo_cloner { clone_repo }
import from utils.parser { scan_repo }
import from utils.graph_builder { build_dependency_graph }

walker DependencyAgent {
    has repo_url: str = "",
        repo_path: str = "",
        graph_data: dict = {};

    can start with entry {
        here.state = "RUNNING";
        here.last_action = "Cloning repository";
        clone_result = clone_repo(self.repo_url);
        if not clone_result["success"] {
            here.state = "FAILED";
            report {"error": clone_result.get("error", "clone failed")};
            disengage;
        }
        self.repo_path = clone_result["path"];
        here.last_action = "Parsing Python files";
        files = scan_repo(self.repo_path);
        here.last_action = "Building dependency graph";
        self.graph_data = build_dependency_graph(files, self.repo_path);
        here.state = "COMPLETED";
        report self.graph_data;
    }
}
