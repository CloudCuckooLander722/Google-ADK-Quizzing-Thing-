"use client";

import {CopilotKitCSSProperties, CopilotSidebar} from "@copilotkit/react-ui";
import {useState} from "react";

export default function CopilotKitPage() {
    const [themeColor, setThemeColor] = useState("#6366f1");
  
    // ...
  
    return (
      <main style={{ "--copilot-kit-primary-color": themeColor } as CopilotKitCSSProperties}>
        <YourMainContent themeColor={themeColor} />
        <CopilotSidebar
          clickOutsideToClose={false}
          defaultOpen={true}
          labels={{
            title: "Popup Assistant",
            initial: "👋 Hi, there! You're chatting with an agent. This agent comes with a few tools to get you started.\n\nFor example you can try:\n- **Frontend Tools**: \"Set the theme to orange\"\n- **Shared State**: \"Write a proverb about AI\"\n- **Generative UI**: \"Get the weather in SF\"\n\nAs you interact with the agent, you'll see the UI update in real-time to reflect the agent's **state**, **tool calls**, and **progress**."
          }}
        />
      </main>
    );
  }