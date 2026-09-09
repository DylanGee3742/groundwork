import re

PAGE_MARKER = re.compile(r'<!--\s*page:\s*(\d+)\s*-->')

SECTION = re.compile(
    r'^SECTION\s+(\d+)\s*[-–]\s*(.+)$', re.IGNORECASE
)
# handles: "SECTION 1 – The ECW Profile", "SECTION 5 – Submission requirements..."
# [-–] covers both the en-dash and a plain hyphen — the doc isn't consistent about which

APPENDIX = re.compile(
    r'^APPENDIX\s+(\d+)\s*[-–]\s*(.+)$', re.IGNORECASE
)
# handles: "Appendix 1 - Form Of Tender...", "APPENDIX 3 - SUPPLIER TECHNICAL..."
# IGNORECASE matters here — Appendix 3's heading is fully uppercase, 1 and 2 aren't

CLAUSE = re.compile(
    r'^(\d+(?:\.\d+)+)\.?\s*(.+)$'
)
# handles: "4.1 Award Criteria", "4.1.3.1 Approach and Methodology",
#          "4.2Supplier Evaluation" (no space at all — \s* allows zero),
#          "4.2.2 Technical Merit (Quality) (75%)"
# requires at least one dot-segment (\.\d+)+, so a bare "4" alone won't match —
# that's deliberate, see below

SIMPLE_NUMBERED_ITEM = re.compile(
    r'^(\d+)\.\s+(.+)$'
)
# handles Appendix 3's own local numbering: "1. COMPANY DETAILS",
# "2. Approach and Methodology – 20%"
# these are single-segment ("1.", "2."), which CLAUSE deliberately doesn't
# match — CLAUSE requires a second digit after the dot, so "1. COMPANY"
# (dot followed by a space, not a digit) naturally falls through to this
# pattern instead