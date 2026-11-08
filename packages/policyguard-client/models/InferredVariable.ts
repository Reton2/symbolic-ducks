/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { VariableRole } from './VariableRole';
import type { VariableSort } from './VariableSort';
export type InferredVariable = {
    var_id: string;
    human_name: string;
    role: VariableRole;
    in_degree?: number;
    out_degree?: number;
    layer_index?: number;
    sort: VariableSort;
    ordinal_levels?: (Record<string, string> | null);
    min_bound?: number;
    max_bound?: number;
    default_value?: (number | boolean);
    source_sentence_ids?: Array<number>;
    source_excerpts?: Array<string>;
};
