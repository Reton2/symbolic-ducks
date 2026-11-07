/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ConstraintOperator } from './ConstraintOperator';
/**
 * User-specified constraint applied during abductive input synthesis.
 */
export type TargetConstraintSpec = {
    op?: ConstraintOperator;
    val: (number | boolean | string);
};
