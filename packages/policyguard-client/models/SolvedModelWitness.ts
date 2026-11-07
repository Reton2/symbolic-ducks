/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { VariableSolvedState } from './VariableSolvedState';
/**
 * Separated variable assignments grouped by their topological graph role.
 */
export type SolvedModelWitness = {
    INPUT?: Record<string, VariableSolvedState>;
    INTERMEDIATE?: Record<string, VariableSolvedState>;
    OUTPUT?: Record<string, VariableSolvedState>;
    PARAMETER?: Record<string, VariableSolvedState>;
};
