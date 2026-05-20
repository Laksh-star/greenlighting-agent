import { useAgentContext, useComponent, useFrontendTool } from "@copilotkit/react-core/v2";
import type { Dispatch } from "react";
import { z } from "zod";
import { PackageGateCard, RecommendationCard } from "./components/GreenlightCards";
import type { GreenlightAction, GreenlightState } from "./types";

const recommendationSchema = z.object({
  recommendation: z.string(),
  confidence: z.string(),
  riskScore: z.string(),
  drivers: z.array(z.string())
});

const packageGateSchema = z.object({
  locked: z.boolean(),
  ready: z.boolean()
});

export function useGreenlightCopilotRegistrations(
  state: GreenlightState,
  dispatch: Dispatch<GreenlightAction>
) {
  useAgentContext({
    description: "Current studio greenlight decision state, including project, comparables, assumptions, recommendation, approval state, backend job status, and report paths.",
    value: state
  });

  useAgentContext({
    description: "Role instructions for the Studio Greenlight Copilot.",
    value: "You are a studio greenlight copilot. Use registered React components and frontend tools to review comparables, assumptions, recommendations, and pitch-package approval."
  });

  useComponent({
    name: "GreenlightRecommendationCard",
    description: "Render a polished decision card with recommendation, confidence, risk, and decision drivers.",
    parameters: recommendationSchema,
    render: RecommendationCard
  }, []);

  useComponent({
    name: "PitchPackageApprovalGate",
    description: "Render an approval gate for locking a pitch package after human review.",
    parameters: packageGateSchema,
    render: PackageGateCard
  }, []);

  useFrontendTool({
    name: "openGreenlightPanel",
    description: "Open a named panel in the Studio Greenlight Copilot workspace.",
    parameters: z.object({
      panel: z.enum(["brief", "comparables", "dashboard", "package", "report"])
    }),
    handler: async ({ panel }: { panel: string }) => {
      dispatch({ type: "set_tab", tab: panel });
      return { opened: panel };
    }
  }, [dispatch]);

  useFrontendTool({
    name: "approveGreenlightStep",
    description: "Approve a human-review checkpoint in the greenlight workflow.",
    parameters: z.object({
      step: z.enum(["comparables", "assumptions", "recommendation"])
    }),
    handler: async ({ step }: { step: string }) => {
      if (step === "comparables") dispatch({ type: "approve_comparables", approved: true });
      if (step === "assumptions") dispatch({ type: "approve_assumptions", approved: true });
      if (step === "recommendation") dispatch({ type: "approve_recommendation", approved: true });
      return { approved: step };
    }
  }, [dispatch]);
}
