/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AbductiveSolveStatus } from './AbductiveSolveStatus';
import type { SolvedModelWitness } from './SolvedModelWitness';
/**
 * Result of solving backwards from target states to primary input variables.
 */
export type AbductiveSolveResult = {
    status: AbductiveSolveStatus;
    applied_targets?: Array<string>;
    solved_state?: (SolvedModelWitness | null);
    message?: string;
};
