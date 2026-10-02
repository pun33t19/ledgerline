// Command poisoned is a deliberately malicious demo MCP server. Its add tool
// hides instructions in the tool description that try to make the model read
// a (fake) secrets file and pass it back in an argument.
//
// It exists so Ledgerline can be tested against tool poisoning. It only ever
// targets the fake file from demo.FakeSecretsPath.
package main

import (
	"flag"
	"log"

	"github.com/pun33t19/ledgerline/internal/demo"
)

func main() {
	var transport demo.Transport
	transport.RegisterFlags(flag.CommandLine)
	exfilLog := flag.String("exfil-log", "", "append exfiltrated data to this file (simulated attacker)")
	flag.Parse()

	if err := demo.Serve(newServer(demo.FakeSecretsDisplayPath, demo.NewExfilLog(*exfilLog)), transport); err != nil {
		log.Fatal(err)
	}
}
