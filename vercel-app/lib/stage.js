// Lead workflow stage — the outreach state machine, separate from `status`
// (which handles reject / apply-pipeline). One of these three values.
export const STAGES = ["new", "wip", "reached_out"];

export const STAGE_LABEL = {
  new: "New",
  wip: "Working",
  reached_out: "Reached out",
};

export const isStage = (s) => STAGES.includes(s);
