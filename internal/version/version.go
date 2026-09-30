// Package version reports the Ledgerline build version.
package version

// Version is overridden at build time with
// -ldflags "-X github.com/pun33t19/ledgerline/internal/version.Version=v0.1.0".
var Version = "v0.0.0-dev"

// String returns the version string.
func String() string {
	return Version
}
