/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AutonomousPolicyGraph } from './AutonomousPolicyGraph';
import type { GraphVerificationReport } from './GraphVerificationReport';
/**
 * Full system state response returned by state query and update endpoints.
 */
export type SystemStateResponse = {
    graph: AutonomousPolicyGraph;
    param_overrides?: Record<string, number>;
    verification: GraphVerificationReport;
    smtlib2_preview?: string;
};
