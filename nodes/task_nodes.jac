# Task graph — agents discover work via traversal

node TaskNode {
    has task_type: str = "",
        status: str = "pending",
        assigned_agent: str = "",
        priority: str = "medium",
        details: str = "";
}

node ApprovalNode {
    has question: str = "",
        approved: bool = False,
        requested_by: str = "",
        risk_level: str = "medium",
        action_type: str = "",
        status: str = "pending",
        recommendation: str = "";
}

edge generated_task {
    has reason: str = "";
}

edge approval_request {
    has severity: str = "medium";
}

edge assigned_to {
    has at: str = "";
}
