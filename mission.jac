# RepoSense — Jac mission entry (graph-native orchestration)

import os;
import from utils.mission_entry { execute_mission }

with entry {
    sid = os.environ.get("SESSION_ID", "local");
    url = os.environ.get("REPO_URL", "");
    mode = os.environ.get("EXECUTION_MODE", "autonomous");
    execute_mission(sid, url, mode);
}
