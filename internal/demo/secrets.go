package demo

import (
	"log"
	"os"
	"path/filepath"
	"sync"
)

// FakeSecretsDisplayPath is how malicious tool descriptions name the bait
// file. Using "~" (as Invariant's original demo did with ~/.cursor/mcp.json)
// keeps captured fixtures free of any real home directory.
const FakeSecretsDisplayPath = "~/.ledgerline-demo/fake-secrets.txt" //nolint:gosec // G101: a path to a fake bait file, not a credential

// FakeSecretsPath is the bait file the malicious demo servers try to make a
// model read. It only ever contains fake values written by demos/phase1.sh.
// Never point the demos at a real credentials file.
func FakeSecretsPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		home = "."
	}
	return filepath.Join(home, ".ledgerline-demo", "fake-secrets.txt")
}

// ExfilLog stands in for an attacker's server: anything a malicious tool
// manages to smuggle out is appended here so the demo can show it.
type ExfilLog struct {
	mu   sync.Mutex
	path string
}

// NewExfilLog returns a log writing to path; an empty path logs to stderr only.
func NewExfilLog(path string) *ExfilLog { return &ExfilLog{path: path} }

// Capture records smuggled data, if any.
func (e *ExfilLog) Capture(tool, data string) {
	if data == "" {
		return
	}
	log.Printf("[attacker] %s exfiltrated %d bytes: %q", tool, len(data), data)
	if e.path == "" {
		return
	}
	e.mu.Lock()
	defer e.mu.Unlock()
	f, err := os.OpenFile(e.path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		log.Printf("exfil log: %v", err)
		return
	}
	_, err = f.WriteString(tool + "\t" + data + "\n")
	if cerr := f.Close(); err == nil {
		err = cerr
	}
	if err != nil {
		log.Printf("exfil log: %v", err)
	}
}
