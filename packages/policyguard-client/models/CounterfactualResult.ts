/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ChangedInputSpec } from './ChangedInputSpec';
import type { CounterfactualStatus } from './CounterfactualStatus';
import type { VariableSolvedState } from './VariableSolvedState';
export type CounterfactualResult = {
    status: CounterfactualStatus;
    minimal_input_changes_count?: number;
    changed_inputs?: Record<string, ChangedInputSpec>;
    resulting_outputs?: Record<string, VariableSolvedState>;
    message?: string;
};
