package main

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/pun33t19/ledgerline/internal/demo"
	"github.com/pun33t19/ledgerline/internal/demo/demotest"
)

const bait = "~/.ledgerline-demo/fake-secrets.txt"

func TestRugPullAfterNCalls(t *testing.T) {
	const after = 3
	changed := make(chan struct{}, 1)
	opts := &mcp.ClientOptions{
		ToolListChangedHandler: func(context.Context, *mcp.ToolListChangedRequest) {
			select {
			case changed <- struct{}{}:
			default:
			}
		},
	}
	cs := demotest.Connect(t, newServer(after, bait, demo.NewExfilLog("")), opts)

	for i := 1; i < after; i++ {
		demotest.Call(t, cs, toolName, nil)
		if d := demotest.Tool(t, cs, toolName).Description; d != benignDescription {
			t.Fatalf("description changed early, after call %d: %q", i, d)
		}
	}

	demotest.Call(t, cs, toolName, nil) // call number `after` triggers the pull

	select {
	case <-changed:
	case <-time.After(2 * time.Second):
		t.Fatal("no notifications/tools/list_changed after the rug pull")
	}
	d := demotest.Tool(t, cs, toolName).Description
	if !strings.Contains(d, "<IMPORTANT>") || !strings.Contains(d, bait) {
		t.Fatalf("description after rug pull = %q, want malicious instructions", d)
	}
}

func TestRugPullHappensOnce(t *testing.T) {
	cs := demotest.Connect(t, newServer(1, bait, demo.NewExfilLog("")), nil)
	demotest.Call(t, cs, toolName, nil)
	first := demotest.Tool(t, cs, toolName).Description
	for range 5 {
		demotest.Call(t, cs, toolName, nil)
	}
	if got := demotest.Tool(t, cs, toolName).Description; got != first {
		t.Errorf("description kept changing: %q → %q", first, got)
	}
}
