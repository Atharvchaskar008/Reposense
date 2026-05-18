# FixAgent — secure patch recommendations

import from utils.llm_fixer { generate_fix }

walker FixAgent {
    has finding: dict = {},
        fix: dict = {},
        needs_approval: bool = True;

    can generate with entry {
        here.state = "RUNNING";
        here.last_action = "Generating secure patch";
        self.fix = generate_fix(self.finding);
        here.state = "REQUESTING_APPROVAL" if self.needs_approval else "COMPLETED";
        report self.fix;
    }
}
