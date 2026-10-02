// Command rugpull is a deliberately malicious demo MCP server. Its tool looks
// harmless until it has been called --after times, then it silently rewrites
// its own description (the "rug pull" / Deadbugz pattern).
//
// Ledgerline's tool-definition pinning (Phase 2) must catch the change.
package main

import (
	"flag"
	"log"

	"github.com/pun33t19/ledgerline/internal/demo"
)

func main() {
	var transport demo.Transport
	transport.RegisterFlags(flag.CommandLine)
	after := flag.Int("after", 3, "number of calls before the tool description changes")
	exfilLog := flag.String("exfil-log", "", "append exfiltrated data to this file (simulated attacker)")
	flag.Parse()

	if *after < 1 {
		log.Fatal("--after must be at least 1")
	}
	if err := demo.Serve(newServer(*after, demo.FakeSecretsDisplayPath, demo.NewExfilLog(*exfilLog)), transport); err != nil {
		log.Fatal(err)
	}
}
