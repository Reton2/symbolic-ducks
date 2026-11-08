/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DeadLogicClassification } from './DeadLogicClassification';
export type DeadLogicDiagnostic = {
    target_variable: string;
    human_name: string;
    target_state: string;
    classification: DeadLogicClassification;
    explanation: string;
    conflicting_equation_ids?: Array<string>;
    conflicting_sentence_ids?: Array<number>;
    conflicting_sentences_text?: Array<string>;
    suggested_remediation?: string;
    relaxed_parameter_solutions?: Record<string, number>;
};
