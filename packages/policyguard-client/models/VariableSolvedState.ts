/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Structured concrete valuation of a variable extracted from a Z3 SAT model.
 */
export type VariableSolvedState = {
    human_name: string;
    value: (number | boolean);
    formatted: string;
    layer?: number;
};
