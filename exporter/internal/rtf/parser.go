// Package rtf derives cleaned lyrics and ordered Song Sections from EasyWorship RTF.
package rtf

import (
	"fmt"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/contract"
)

var ignoredDestinations = map[string]bool{
	"colortbl": true, "datastore": true, "filetbl": true, "fonttbl": true,
	"footer": true, "footerf": true, "footerl": true, "footerr": true,
	"header": true, "headerf": true, "headerl": true, "headerr": true,
	"info": true, "listtable": true, "listoverridetable": true, "object": true,
	"pict": true, "revtbl": true, "stylesheet": true, "themedata": true,
}

type state struct {
	ignored     bool
	label       bool
	ucSkip      int
	pendingSkip int
	starred     bool
}

// Result is the storage-neutral content derived from one RTF document.
type Result struct {
	CleanedLyrics string
	Sections      []contract.Section
	Warnings      []string
}

// Parse extracts lyrics while retaining unknown source labels exactly.
func Parse(document string, slideUIDs []string) (Result, error) {
	if !strings.HasPrefix(strings.TrimSpace(document), "{\\rtf") {
		return Result{}, fmt.Errorf("lyrics are not an RTF document")
	}
	p := parser{
		input:     document,
		states:    []state{{ucSkip: 1}},
		slideUIDs: slideUIDs,
	}
	if err := p.parse(); err != nil {
		return Result{}, err
	}
	p.finishSection()
	if len(p.sections) == 0 && strings.TrimSpace(p.slide.String()) != "" {
		p.finishSection()
	}

	var lyricSlides []string
	for _, section := range p.sections {
		for _, slide := range section.Slides {
			lyricSlides = append(lyricSlides, strings.Join(slide.Lines, "\n"))
		}
	}
	expectedSlideUIDs := p.markerCount + 1
	if len(slideUIDs) != expectedSlideUIDs {
		p.warnings = append(p.warnings, fmt.Sprintf(
			"source has %d slide UID(s) for %d RTF slide marker(s); expected %d",
			len(slideUIDs), p.markerCount, expectedSlideUIDs,
		))
	}
	return Result{
		CleanedLyrics: strings.Join(lyricSlides, "\n"),
		Sections:      p.sections,
		Warnings:      p.warnings,
	}, nil
}

type parser struct {
	input         string
	position      int
	states        []state
	label         strings.Builder
	slide         strings.Builder
	sectionLabel  string
	sectionSlides []contract.Slide
	sections      []contract.Section
	slideUIDs     []string
	usedUIDs      int
	markerCount   int
	warnings      []string
}

func (p *parser) parse() error {
	for p.position < len(p.input) {
		character := p.input[p.position]
		switch character {
		case '{':
			current := p.states[len(p.states)-1]
			current.pendingSkip = 0
			p.states = append(p.states, current)
			p.position++
		case '}':
			if len(p.states) == 1 {
				return fmt.Errorf("unexpected closing group at byte %d", p.position)
			}
			p.states = p.states[:len(p.states)-1]
			p.position++
		case '\\':
			if err := p.control(); err != nil {
				return err
			}
		case '\r', '\n':
			p.position++
		default:
			runeValue, size := utf8.DecodeRuneInString(p.input[p.position:])
			if runeValue == utf8.RuneError && size == 1 {
				return fmt.Errorf("invalid UTF-8 at byte %d", p.position)
			}
			p.writeRune(runeValue)
			p.position += size
		}
	}
	if len(p.states) != 1 {
		return fmt.Errorf("unterminated RTF group")
	}
	return nil
}

func (p *parser) control() error {
	p.position++
	if p.position >= len(p.input) {
		return fmt.Errorf("trailing escape")
	}
	current := &p.states[len(p.states)-1]
	symbol := p.input[p.position]
	switch symbol {
	case '\\', '{', '}':
		p.writeRune(rune(symbol))
		p.position++
		return nil
	case '~':
		p.writeRune(' ')
		p.position++
		return nil
	case '_':
		p.writeRune('-')
		p.position++
		return nil
	case '*':
		current.starred = true
		p.position++
		return nil
	case '\'':
		if p.position+2 >= len(p.input) {
			return fmt.Errorf("incomplete hexadecimal escape at byte %d", p.position)
		}
		value, err := strconv.ParseUint(p.input[p.position+1:p.position+3], 16, 8)
		if err != nil {
			return fmt.Errorf("invalid hexadecimal escape at byte %d", p.position)
		}
		p.writeRune(rune(value))
		p.position += 3
		return nil
	}

	if !isASCIIAlpha(symbol) {
		p.position++
		return nil
	}
	start := p.position
	for p.position < len(p.input) && isASCIIAlpha(p.input[p.position]) {
		p.position++
	}
	word := p.input[start:p.position]
	parameter, hasParameter := 0, false
	parameterStart := p.position
	if p.position < len(p.input) && (p.input[p.position] == '-' || isASCIIDigit(p.input[p.position])) {
		p.position++
		for p.position < len(p.input) && isASCIIDigit(p.input[p.position]) {
			p.position++
		}
		parsed, err := strconv.Atoi(p.input[parameterStart:p.position])
		if err != nil {
			return fmt.Errorf("invalid %s parameter at byte %d", word, parameterStart)
		}
		parameter, hasParameter = parsed, true
	}
	if p.position < len(p.input) && p.input[p.position] == ' ' {
		p.position++
	}

	isEasyWorshipStructure := word == "sdparawysiwghidden" || word == "sdslidemarker"
	if (current.starred && !isEasyWorshipStructure) || ignoredDestinations[word] {
		current.ignored = true
		current.starred = false
		return nil
	}
	current.starred = false
	if current.ignored {
		return nil
	}

	switch word {
	case "uc":
		if hasParameter && parameter >= 0 {
			current.ucSkip = parameter
		}
	case "u":
		if hasParameter {
			if parameter < 0 {
				parameter += 65536
			}
			p.writeRune(rune(parameter))
			current.pendingSkip = current.ucSkip
		}
	case "tab":
		p.writeRune(' ')
	case "line":
		p.writeRune('\n')
	case "par":
		if current.label {
			p.finishLabel()
			current.label = false
		} else {
			p.writeRune('\n')
		}
	case "sdparawysiwghidden":
		p.finishSection()
		current.label = true
	case "sdslidemarker":
		p.markerCount++
		p.finishSlide()
	}
	return nil
}

func (p *parser) writeRune(value rune) {
	current := &p.states[len(p.states)-1]
	if current.ignored || value == 0 {
		return
	}
	if current.pendingSkip > 0 && value <= unicode.MaxASCII {
		current.pendingSkip--
		return
	}
	if current.label {
		p.label.WriteRune(value)
		return
	}
	p.slide.WriteRune(value)
}

func (p *parser) finishLabel() {
	p.sectionLabel = normalizeLabel(strings.TrimSpace(p.label.String()))
	p.label.Reset()
}

func (p *parser) finishSlide() {
	text := cleanText(p.slide.String())
	p.slide.Reset()
	if text == "" {
		return
	}
	lines := strings.Split(text, "\n")
	var sourceUID *string
	if p.usedUIDs < len(p.slideUIDs) {
		uid := p.slideUIDs[p.usedUIDs]
		sourceUID = &uid
	}
	p.usedUIDs++
	p.sectionSlides = append(p.sectionSlides, contract.Slide{
		Position:       len(p.sectionSlides) + 1,
		SourceSlideUID: sourceUID,
		Lines:          lines,
	})
}

func (p *parser) finishSection() {
	if p.label.Len() > 0 {
		p.finishLabel()
	}
	p.finishSlide()
	if len(p.sectionSlides) == 0 {
		return
	}
	p.sections = append(p.sections, contract.Section{
		Position: len(p.sections) + 1,
		Label:    p.sectionLabel,
		Slides:   p.sectionSlides,
	})
	p.sectionLabel = ""
	p.sectionSlides = nil
}

func cleanText(value string) string {
	value = strings.ReplaceAll(value, "\r", "")
	lines := strings.Split(value, "\n")
	cleaned := make([]string, 0, len(lines))
	for _, line := range lines {
		line = strings.Join(strings.Fields(line), " ")
		if line != "" {
			cleaned = append(cleaned, line)
		}
	}
	return strings.Join(cleaned, "\n")
}

func normalizeLabel(label string) string {
	normalized := strings.ToLower(strings.TrimSpace(label))
	normalized = strings.Trim(normalized, "[]()*:_-. ")
	fields := strings.Fields(normalized)
	if len(fields) > 1 {
		if _, err := strconv.Atoi(strings.Trim(fields[len(fields)-1], "[]()*x:")); err == nil {
			fields = fields[:len(fields)-1]
		}
	}
	candidate := strings.Join(fields, " ")
	compact := strings.ReplaceAll(candidate, " ", "")
	switch candidate {
	case "verse", "v":
		return "verse"
	case "chorus", "ch", "chr":
		return "chorus"
	case "bridge":
		return "bridge"
	case "pre-chorus", "pre chorus":
		return "pre_chorus"
	case "refrain":
		return "refrain"
	case "intro", "introduction":
		return "intro"
	case "outro", "ending":
		return "outro"
	case "solo":
		return "solo"
	case "vamp":
		return "vamp"
	default:
		if strings.HasPrefix(compact, "verse") && isNumber(compact[len("verse"):]) ||
			strings.HasPrefix(compact, "v") && isNumber(compact[1:]) {
			return "verse"
		}
		if strings.HasPrefix(compact, "chorus") && isNumber(compact[len("chorus"):]) ||
			strings.HasPrefix(compact, "ch") && isNumber(compact[len("ch"):]) ||
			strings.HasPrefix(compact, "chr") && isNumber(compact[len("chr"):]) {
			return "chorus"
		}
		return label
	}
}

func isNumber(value string) bool {
	if value == "" {
		return false
	}
	_, err := strconv.Atoi(value)
	return err == nil
}

func isASCIIAlpha(value byte) bool {
	return value >= 'a' && value <= 'z' || value >= 'A' && value <= 'Z'
}

func isASCIIDigit(value byte) bool {
	return value >= '0' && value <= '9'
}
