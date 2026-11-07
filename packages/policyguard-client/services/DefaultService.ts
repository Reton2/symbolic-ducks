/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AbductiveSolveResult } from '../models/AbductiveSolveResult';
import type { CounterfactualRequest } from '../models/CounterfactualRequest';
import type { CounterfactualResult } from '../models/CounterfactualResult';
import type { EvaluateTelemetryRequest } from '../models/EvaluateTelemetryRequest';
import type { IngestDocumentRequest } from '../models/IngestDocumentRequest';
import type { SolveForInputsRequest } from '../models/SolveForInputsRequest';
import type { SystemStateResponse } from '../models/SystemStateResponse';
import type { TelemetryEvaluationResult } from '../models/TelemetryEvaluationResult';
import type { UpdateParamsRequest } from '../models/UpdateParamsRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import type { BaseHttpRequest } from '../core/BaseHttpRequest';
export class DefaultService {
    constructor(public readonly httpRequest: BaseHttpRequest) {}
    /**
     * Index
     * @returns any Successful Response
     * @throws ApiError
     */
    public indexGet(): CancelablePromise<any> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/',
        });
    }
    /**
     * Get System State
     * @returns SystemStateResponse Successful Response
     * @throws ApiError
     */
    public getSystemStateApiStateGet(): CancelablePromise<SystemStateResponse> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/state',
        });
    }
    /**
     * Update Parameters
     * @param requestBody
     * @returns SystemStateResponse Successful Response
     * @throws ApiError
     */
    public updateParametersApiParamsUpdatePost(
        requestBody: UpdateParamsRequest,
    ): CancelablePromise<SystemStateResponse> {
        return this.httpRequest.request({
            method: 'POST',
            url: '/api/params/update',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Solve For Inputs Endpoint
     * Abductive Z3 solving: synthesizes foundational telemetry values from desired target constraints.
     * @param requestBody
     * @returns AbductiveSolveResult Successful Response
     * @throws ApiError
     */
    public solveForInputsEndpointApiSmtSolveInputsPost(
        requestBody: SolveForInputsRequest,
    ): CancelablePromise<AbductiveSolveResult> {
        return this.httpRequest.request({
            method: 'POST',
            url: '/api/smt/solve-inputs',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Counterfactual Endpoint
     * MaxSMT counterfactual search: finds minimal input interventions.
     * @param requestBody
     * @returns CounterfactualResult Successful Response
     * @throws ApiError
     */
    public counterfactualEndpointApiSmtCounterfactualPost(
        requestBody: CounterfactualRequest,
    ): CancelablePromise<CounterfactualResult> {
        return this.httpRequest.request({
            method: 'POST',
            url: '/api/smt/counterfactual',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Evaluate Telemetry Endpoint
     * Evaluates arbitrary input telemetry values and broadcasts to live clients.
     * @param requestBody
     * @returns TelemetryEvaluationResult Successful Response
     * @throws ApiError
     */
    public evaluateTelemetryEndpointApiTelemetryEvaluatePost(
        requestBody: EvaluateTelemetryRequest,
    ): CancelablePromise<TelemetryEvaluationResult> {
        return this.httpRequest.request({
            method: 'POST',
            url: '/api/telemetry/evaluate',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Download Smtlib2
     * @returns string Successful Response
     * @throws ApiError
     */
    public downloadSmtlib2ApiSmtlib2Get(): CancelablePromise<string> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/smtlib2',
        });
    }
    /**
     * Ingest Unstructured Document
     * Ingests unstructured policy text, infers causal graph topology, and hot-swaps Z3.
     * @param requestBody
     * @returns SystemStateResponse Successful Response
     * @throws ApiError
     */
    public ingestUnstructuredDocumentApiIngestDocumentPost(
        requestBody: IngestDocumentRequest,
    ): CancelablePromise<SystemStateResponse> {
        return this.httpRequest.request({
            method: 'POST',
            url: '/api/ingest-document',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
