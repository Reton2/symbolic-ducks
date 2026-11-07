/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ReachabilityProof } from './ReachabilityProof';
import type { VerificationStatus } from './VerificationStatus';
/**
 * Formal audit report proving base satisfiability and absence of dead states.
 */
export type GraphVerificationReport = {
    status: VerificationStatus;
    consistent: boolean;
    dead_state_warnings?: Array<string>;
    reachability_proofs?: Array<ReachabilityProof>;
};
