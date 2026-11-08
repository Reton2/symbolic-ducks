/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ReachabilityProof } from './ReachabilityProof';
import type { VerificationStatus } from './VerificationStatus';
export type GraphVerificationReport = {
    status: VerificationStatus;
    consistent: boolean;
    is_dag_consistent?: boolean;
    reachable_count?: number;
    dead_count?: number;
    dead_state_warnings?: Array<string>;
    reachability_proofs?: Array<ReachabilityProof>;
};
