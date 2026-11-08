/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TelemetryOutputDirective } from './TelemetryOutputDirective';
export type TelemetryEvaluationResult = {
    latency_us: number;
    outputs?: Record<string, TelemetryOutputDirective>;
    elevated_lineage_nodes?: Array<string>;
    full_state?: Record<string, (number | boolean)>;
};
