// Package gostrategy is an UNSUPPORTED sketch of a dockly language strategy.
// It mirrors the Python Strategy contract (matches + plan) for documentation.
//
// Go is not a first-party dockly strategy in v1.
package gostrategy

// ProjectFacts is a minimal stand-in for dockly.project_facts.ProjectFacts.
type ProjectFacts struct {
	Language  string
	Framework string // e.g. "go-module", "plain-go"
}

// Policy mirrors dockly.strategy.Policy preferences.
type Policy struct {
	// PreferDistroless asks the strategy to favor distroless/static runtimes when possible.
	PreferDistroless bool
}

// StrategyPlan mirrors dockly.strategy.StrategyPlan.
type StrategyPlan struct {
	StrategyID    string
	Name          string
	Optimizations []string
	Rationale     string
}

// Strategy is the Go-shaped equivalent of the Python Strategy protocol.
type Strategy interface {
	ID() string
	Matches(facts ProjectFacts, policy Policy) bool
	Plan(facts ProjectFacts, policy Policy) StrategyPlan
}

// GoModulesStrategy is a non-shipping example for multi-stage Go builds.
type GoModulesStrategy struct{}

func (GoModulesStrategy) ID() string { return "go-modules" }

func (GoModulesStrategy) Matches(facts ProjectFacts, _ Policy) bool {
	return facts.Language == "go"
}

func (s GoModulesStrategy) Plan(facts ProjectFacts, policy Policy) StrategyPlan {
	opts := []string{"multi-stage-build", "go-build-trimpath"}
	if policy.PreferDistroless {
		opts = append(opts, "distroless-static")
	}
	return StrategyPlan{
		StrategyID:    s.ID(),
		Name:          "Go modules multi-stage",
		Optimizations: opts,
		Rationale:     "Unsupported example: Go module project → multi-stage binary image",
	}
}
