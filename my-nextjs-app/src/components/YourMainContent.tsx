"use client";

import { useCoAgent } from "@copilotkit/react-core";

// State of the agent, make sure this aligns with your agent's state.
type AgentState = {
  proverbs: string[];
}

function YourMainContent({ themeColor }: { themeColor: string }) {

  // 🪁 Shared State: https://docs.copilotkit.ai/coagents/shared-state
  const { state, setState } = useCoAgent<AgentState>({
    name: "default",
    initialState: {
      proverbs: [
        "CopilotKit may be new, but it's the best thing since sliced bread.",
      ],
    },
  })

     // ...
  return (

  // ...
  )