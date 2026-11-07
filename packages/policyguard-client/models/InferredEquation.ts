/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A Z3 symbolic equation synthesized by aggregating all sentences governing `target_var`.
 */
export type InferredEquation = {
    equation_id: string;
    target_var: string;
    dependencies?: Array<string>;
    /**
     * Valid Z3 symbolic formula using v['var_id']
     */
    smt_expression: string;
    natural_language_logic?: string;
    source_sentence_ids?: Array<number>;
};
