/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { VariableRole } from './VariableRole';
import type { VariableSort } from './VariableSort';
/**
 * An entity autonomously discovered and resolved across unordered sentences.
 */
export type InferredVariable = {
    var_id: string;
    human_name: string;
    role: VariableRole;
    /**
     * Number of upstream concepts this variable depends on
     */
    in_degree?: number;
    /**
     * Number of downstream concepts that depend on this variable
     */
    out_degree?: number;
    /**
     * Topological depth: 0 for deg-(v)==0 inputs, K for sinks
     */
    layer_index?: number;
    sort: VariableSort;
    ordinal_levels?: (Record<string, string> | null);
    min_bound?: number;
    max_bound?: number;
    default_value?: (number | boolean);
    /**
     * Sentence indices anywhere in the text that reference/define this entity
     */
    source_sentence_ids?: Array<number>;
    source_excerpts?: Array<string>;
};
