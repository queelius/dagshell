# Makefile for DagShell paper

PAPER = dagshell
TEX = pdflatex
BIBTEX = bibtex

.PHONY: all clean view

all: $(PAPER).pdf

$(PAPER).pdf: $(PAPER).tex
	$(TEX) $(PAPER).tex
	$(TEX) $(PAPER).tex
	@echo "PDF generated: $(PAPER).pdf"

clean:
	rm -f $(PAPER).aux $(PAPER).log $(PAPER).out $(PAPER).pdf $(PAPER).bbl $(PAPER).blg

view: $(PAPER).pdf
	xdg-open $(PAPER).pdf 2>/dev/null || open $(PAPER).pdf 2>/dev/null || echo "Please open $(PAPER).pdf manually"

help:
	@echo "Available targets:"
	@echo "  all    - Build the PDF (default)"
	@echo "  clean  - Remove generated files"
	@echo "  view   - Open the PDF in default viewer"
	@echo "  help   - Show this help message"
