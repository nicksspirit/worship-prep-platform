package rtf

import "testing"

func TestParsePreservesOrderAndNormalizesOnlyRecognizedLabels(t *testing.T) {
	t.Parallel()
	document := `{\rtf1\ansi\uc1{\fonttbl{\f0 Arial;}}` +
		`{\sdparawysiwghidden Verse 2:\par}` +
		`Amazing \u233? grace\line How sweet the sound{\*\sdslidemarker} ` +
		`That saved a wretch like me{\*\sdslidemarker}` +
		`{\sdparawysiwghidden Sunday School\par}` +
		`Custom section text}`

	result, err := Parse(document, []string{"slide-1", "slide-2", "slide-3"})
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}
	if got, want := len(result.Sections), 2; got != want {
		t.Fatalf("len(Sections) = %d, want %d", got, want)
	}
	if got, want := result.Sections[0].Label, "verse"; got != want {
		t.Errorf("recognized label = %q, want %q", got, want)
	}
	if got, want := result.Sections[1].Label, "Sunday School"; got != want {
		t.Errorf("custom label = %q, want %q", got, want)
	}
	if got, want := result.Sections[0].Slides[0].Lines[0], "Amazing é grace"; got != want {
		t.Errorf("Unicode lyric = %q, want %q", got, want)
	}
	if got, want := *result.Sections[1].Slides[0].SourceSlideUID, "slide-3"; got != want {
		t.Errorf("ordered slide UID = %q, want %q", got, want)
	}
	if got, want := result.CleanedLyrics, "Amazing é grace\nHow sweet the sound\nThat saved a wretch like me\nCustom section text"; got != want {
		t.Errorf("CleanedLyrics = %q, want %q", got, want)
	}
}

func TestParseWarnsAboutSlideCardinalityWithoutRejectingSong(t *testing.T) {
	t.Parallel()
	result, err := Parse(`{\rtf1\ansi One slide}`, []string{"slide-1", "unused-slide"})
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}
	if len(result.Sections) != 1 {
		t.Fatalf("len(Sections) = %d, want 1", len(result.Sections))
	}
	if len(result.Warnings) != 1 {
		t.Fatalf("len(Warnings) = %d, want 1", len(result.Warnings))
	}
}

func TestParseDropsNulUnicodeControls(t *testing.T) {
	t.Parallel()
	result, err := Parse(`{\rtf1\ansi Before\u0?After}`, nil)
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}
	if got, want := result.CleanedLyrics, "BeforeAfter"; got != want {
		t.Fatalf("CleanedLyrics = %q, want %q", got, want)
	}
}

func TestParseRejectsUnusableLyrics(t *testing.T) {
	t.Parallel()
	if _, err := Parse("plain text", nil); err == nil {
		t.Fatal("Parse() error = nil, want invalid RTF error")
	}
	if _, err := Parse(`{\rtf1\ansi unterminated`, nil); err == nil {
		t.Fatal("Parse() error = nil, want unterminated group error")
	}
}

func TestNormalizeLabelPreservesCustomTextExactly(t *testing.T) {
	t.Parallel()
	if got, want := normalizeLabel("Call  &  Response"), "Call  &  Response"; got != want {
		t.Fatalf("normalizeLabel() = %q, want %q", got, want)
	}
	for input, want := range map[string]string{
		"V1": "verse", "Verse2": "verse", "CHORUS 3": "chorus", "Sunday School": "Sunday School",
	} {
		if got := normalizeLabel(input); got != want {
			t.Errorf("normalizeLabel(%q) = %q, want %q", input, got, want)
		}
	}
}
