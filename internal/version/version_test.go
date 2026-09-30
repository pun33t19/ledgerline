package version

import "testing"

func TestString(t *testing.T) {
	if got := String(); got == "" {
		t.Fatal("String() returned empty version")
	}
}

func TestStringReflectsOverride(t *testing.T) {
	orig := Version
	t.Cleanup(func() { Version = orig })

	Version = "v9.9.9"
	if got := String(); got != "v9.9.9" {
		t.Fatalf("String() = %q, want %q", got, "v9.9.9")
	}
}
