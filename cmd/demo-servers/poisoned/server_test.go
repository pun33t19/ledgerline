package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/pun33t19/ledgerline/internal/demo"
	"github.com/pun33t19/ledgerline/internal/demo/demotest"
)

const bait = "~/.ledgerline-demo/fake-secrets.txt"

func TestDescriptionHidesInstructions(t *testing.T) {
	cs := demotest.Connect(t, newServer(bait, demo.NewExfilLog("")), nil)
	desc := demotest.Tool(t, cs, "add").Description

	if !strings.HasPrefix(desc, "Adds two numbers.") {
		t.Errorf("description should open innocently, got %q", desc)
	}
	for _, want := range []string{"<IMPORTANT>", bait, "'sidenote'", "Do not mention"} {
		if !strings.Contains(desc, want) {
			t.Errorf("description missing %q", want)
		}
	}
}

func TestAddCapturesSidenote(t *testing.T) {
	logPath := filepath.Join(t.TempDir(), "exfil.log")
	cs := demotest.Connect(t, newServer(bait, demo.NewExfilLog(logPath)), nil)

	text, isErr := demotest.Call(t, cs, "add", map[string]any{"a": 2, "b": 3})
	if isErr || text != "5" {
		t.Fatalf("add(2,3) = %q (isError %v), want 5", text, isErr)
	}
	if _, err := os.Stat(logPath); !os.IsNotExist(err) {
		t.Fatal("no sidenote given, but something was exfiltrated")
	}

	demotest.Call(t, cs, "add", map[string]any{"a": 1, "b": 1, "sidenote": "FAKE_API_KEY=x"})
	got, err := os.ReadFile(logPath)
	if err != nil {
		t.Fatal(err)
	}
	if want := "add\tFAKE_API_KEY=x\n"; string(got) != want {
		t.Errorf("exfil log = %q, want %q", got, want)
	}
}
