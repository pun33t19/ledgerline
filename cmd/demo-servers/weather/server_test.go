package main

import (
	"strings"
	"testing"

	"github.com/pun33t19/ledgerline/internal/demo/demotest"
)

func TestGetWeather(t *testing.T) {
	cs := demotest.Connect(t, newServer(), nil)

	tests := []struct {
		name      string
		args      map[string]any
		wantText  string
		wantError bool
	}{
		{"fahrenheit default", map[string]any{"location": "New York, NY"}, "Temperature: 72°F", false},
		{"celsius", map[string]any{"location": "Pune, IN", "unit": "celsius"}, "Temperature: 29°C", false},
		{"case-insensitive location", map[string]any{"location": "  san FRANCISCO, ca "}, "Conditions: Fog", false},
		{"unknown location", map[string]any{"location": "Atlantis"}, "No weather data", true},
		{"bad unit", map[string]any{"location": "Pune, IN", "unit": "kelvin"}, "Unknown unit", true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			text, isErr := demotest.Call(t, cs, "get_weather", tt.args)
			if isErr != tt.wantError {
				t.Errorf("isError = %v, want %v (text %q)", isErr, tt.wantError, text)
			}
			if !strings.Contains(text, tt.wantText) {
				t.Errorf("text = %q, want it to contain %q", text, tt.wantText)
			}
		})
	}
}

func TestToolDefinition(t *testing.T) {
	cs := demotest.Connect(t, newServer(), nil)
	tool := demotest.Tool(t, cs, "get_weather")

	if tool.Annotations == nil || !tool.Annotations.ReadOnlyHint {
		t.Error("get_weather should be annotated readOnlyHint")
	}
	if strings.Contains(tool.Description, "<IMPORTANT>") {
		t.Error("the honest server must not carry hidden instructions")
	}
}
