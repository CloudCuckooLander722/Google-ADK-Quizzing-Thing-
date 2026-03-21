import {
    CopilotRuntime, // Main runtime that manages agent communication
    ExperimentalEmptyAdapter, // Service adapter for single-agent setups
    copilotRuntimeNextJSAppRouterEndpoint, // Next.js App Router endpoint handler
  } from "@copilotkit/runtime";

import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";
const serviceAdapter = new ExperimentalEmptyAdapter();
  
  
const runtime = new CopilotRuntime({
      agents: {
      default: new HttpAgent({
        url: "http://localhost:8000/",
      }),
    },
  });
  
  // Export the POST handler for the API route
export const POST = async (req: NextRequest) => {
  
const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
      runtime, // The CopilotRuntime instance we configured
      serviceAdapter, // The service adapter for agent coordination
      endpoint: "/api/copilotkit", // The endpoint path (matches this file's location)
    });
  
  
    return handleRequest(req);
  };