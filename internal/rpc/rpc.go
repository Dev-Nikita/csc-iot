// Package rpc is the intelligence-plane boundary.
//
// The contract is frozen here so the transport underneath can change without
// touching a line of controller logic. The development implementation is stdlib
// framed TCP; a gRPC adapter lives behind a build tag and is NEEDS_LOCAL_VALIDATION.
//
// T_rpc is measured separately from T_model on purpose. Once the intelligence
// plane is its own process, serialisation and network time are a real component
// of the decision budget, and folding them into the model time would hide where
// a missed deadline actually came from.
package rpc

import (
	"context"
	"time"
)

// StateRequest is what the controller sends.
type StateRequest struct {
	DecisionID  string             `json:"decision_id"`
	RunID       string             `json:"run_id"`
	LogicalTick int64              `json:"logical_tick"`
	Features    map[string]float64 `json:"features"`
	Actions     []string           `json:"actions"`
}

// ActionScore is per-action model output. Observational and interventional risk
// stay separate fields all the way to the wire.
type ActionScore struct {
	Action             string  `json:"action"`
	RiskObservational  float64 `json:"risk_observational"`
	RiskInterventional float64 `json:"risk_interventional"`
	Uncertainty        float64 `json:"uncertainty"`
	Cost               float64 `json:"cost"`
	PredictedLatencyMs float64 `json:"predicted_latency_ms"`
}

// ActionScores is the reply. It ranks; it never decides.
type ActionScores struct {
	DecisionID           string        `json:"decision_id"`
	Scores               []ActionScore `json:"scores"`
	ModelVersion         string        `json:"model_version"`
	CalibrationVersion   string        `json:"calibration_version"`
	TModelNanos          int64         `json:"t_model_nanos"`
	TCounterfactualNanos int64         `json:"t_counterfactual_nanos"`
}

// Client is the boundary the controller depends on.
type Client interface {
	// EvaluateActions must respect the deadline in ctx. A miss is a recorded
	// fallback, never a stalled controller.
	EvaluateActions(ctx context.Context, req StateRequest) (ActionScores, Timing, error)
	Descriptor() Descriptor
	Close() error
}

// Timing separates the components of the decision budget:
//
//	T_dec = T_feat + T_rpc + T_model + T_cf + T_gate
type Timing struct {
	RPCNanos            int64 `json:"t_rpc_nanos"`
	ModelNanos          int64 `json:"t_model_nanos"`
	CounterfactualNanos int64 `json:"t_cf_nanos"`
	DeadlineMissed      bool  `json:"deadline_missed"`
}

// Descriptor names the concrete RPC implementation for the manifest.
type Descriptor struct {
	Type    string `json:"rpc_type"`
	Version string `json:"rpc_version"`
	Address string `json:"address"`
}

// Deadline is the controller's enforced budget for one evaluation.
const Deadline = 100 * time.Millisecond
