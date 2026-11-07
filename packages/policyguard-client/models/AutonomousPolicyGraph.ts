/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { InferredEquation } from './InferredEquation';
import type { InferredVariable } from './InferredVariable';
export type AutonomousPolicyGraph = {
    graph_id: string;
    title: string;
    raw_document_text: string;
    sentence_count: number;
    variables?: Record<string, InferredVariable>;
    equations?: Record<string, InferredEquation>;
    topological_order?: Array<string>;
    cegis_compiler_log?: Array<string>;
};
