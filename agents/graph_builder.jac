# GraphBuilder — fetch repo metadata and dependency graph (no LLM)

import from nodes.repo_nodes { RepoNode, DependencyNode }
import from utils.github_tools {
    parse_repo_url,
    fetch_repo_metadata,
    list_root_files,
    fetch_file_content,
    parse_dependencies
}

walker GraphBuilder {
    has repo_url: str = "",
        owner: str = "",
        repo_name: str = "";

    can build with entry {
        parsed = parse_repo_url(self.repo_url);
        self.owner = parsed[0];
        self.repo_name = parsed[1];
        if not self.owner or not self.repo_name {
            print("Invalid GitHub URL");
            disengage;
        }

        meta = fetch_repo_metadata(self.owner, self.repo_name);
        repo_node = RepoNode(
            url=self.repo_url,
            owner=self.owner,
            repo_name=self.repo_name,
            language=meta.get("language", "unknown"),
            stars=meta.get("stars", 0)
        );
        root ++> repo_node;

        root_files = list_root_files(self.owner, self.repo_name);
        dep_filenames = [
            "requirements.txt",
            "package.json",
            "Gemfile",
            "go.mod",
            "pom.xml"
        ];
        dep_count = 0;

        for fname in dep_filenames {
            if fname not in root_files {
                continue;
            }
            content = fetch_file_content(self.owner, self.repo_name, fname);
            packages = parse_dependencies(content, fname);
            for pkg in packages {
                if dep_count >= 20 {
                    break;
                }
                dep = DependencyNode(
                    name=pkg.get("name", ""),
                    ecosystem=pkg.get("ecosystem", "")
                );
                repo_node ++> dep;
                dep_count += 1;
            }
            if dep_count >= 20 {
                break;
            }
        }

        print(f"Graph built: {self.owner}/{self.repo_name} ({dep_count} dependencies)");
    }
}
