"use client";

import React, { useState } from "react";
import { CopilotChat } from "@copilotkit/react-ui";
import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";

export default function APChemStudyPage() {
  // 1. State goes inside the function
  const [topic, setTopic] = useState<string>("General Chemistry");
  const [questions, setQuestions] = useState<any[]>([]);

  // 2. This shares your current topic with the AI
  useCopilotReadable({
    description: "The current AP Chemistry topic the student is studying",
    value: topic,
  });

  // 3. This allows the AI to "push" new questions to your screen
  useCopilotAction({
    name: "generateQuestions",
    description: "Generates AP Chemistry MCQs or FRQs based on a specific topic",
    parameters: [
      {
        name: "newQuestions",
        type: "object[]",
        description: "An array of question objects with text, options, and correctAnswer",
      },
      {
        name: "topicName",
        type: "string",
        description: "The name or number of the AP Chem topic",
      }
    ],
    handler: (args) => {
      // We use 'args' to access the parameters sent by the AI
      setQuestions(args.newQuestions);
      setTopic(args.topicName);
    },
  });

  // 4. The HTML (JSX) must be inside the same function!
  return (
    <main className="flex h-screen w-full bg-white text-slate-900">
      
      {/* LEFT SIDE: Quiz Interface */}
      <div className="w-1/2 p-10 overflow-y-auto border-r border-slate-200">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">AP Chem: {topic}</h1>
          <p className="text-slate-500 italic">
            Type a topic in the chat to generate questions (e.g., "Give me 8.4 MCQs")
          </p>
        </div>

        {questions.length > 0 ? (
          <div className="space-y-6">
            {questions.map((q, i) => (
              <div key={i} className="p-6 bg-slate-50 rounded-xl border border-slate-200 shadow-sm">
                <p className="font-bold mb-4">{q.text}</p>
                {q.options?.map((opt: string) => (
                  <button 
                    key={opt} 
                    className="block w-full text-left p-3 mb-2 border rounded bg-white hover:bg-blue-50 transition-colors"
                  >
                    {opt}
                  </button>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <div className="h-64 flex flex-col items-center justify-center border-2 border-dashed rounded-xl text-slate-400">
            <p>No questions loaded yet.</p>
            <p className="text-sm">Ask the AI: "Generate Topic 8.4 MCQs"</p>
          </div>
        )}
      </div>

      {/* RIGHT SIDE: Feynman AI Tutor */}
      <div className="w-1/2 h-full flex flex-col">
        <CopilotChat
          instructions={`
            You are a world-class AP Chemistry tutor who uses the Feynman Technique.
            1. Explain complex concepts using simple analogies (like you're talking to a 10-year-old).
            2. Break explanations into fundamental steps.
            3. ALWAYS provide 2-3 links to helpful articles (Khan Academy, LibreTexts) at the end.
            4. When asked for questions (MCQs/FRQs), use the 'generateQuestions' tool.
          `}
          labels={{
            title: "Feynman Chem Tutor",
            initial: "Hi! I'm your AP Chem coach. Want to try some Topic 8.4 questions, or should I explain a concept first?",
          }}
        />
      </div>
    </main>
  );
}
