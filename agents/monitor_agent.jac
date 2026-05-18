# MonitorAgent — orchestration visibility (no LLM)

walker MonitorAgent {
    has agents: list = [],
        timeline: list = [];

    can track with entry {
        here.state = "RUNNING";
        here.last_action = "Monitoring agent fleet";
        report {"agents": self.agents, "timeline": self.timeline};
        here.state = "COMPLETED";
    }
}
