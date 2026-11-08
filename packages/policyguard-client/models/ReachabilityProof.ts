/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DeadLogicDiagnostic } from './DeadLogicDiagnostic';
export type ReachabilityProof = {
    output_var: string;
    human_name: string;
    target_state: string;
    reachable: boolean;
    diagnostic?: (DeadLogicDiagnostic | null);
};
