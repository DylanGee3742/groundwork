from groundwork.harness.regex_patterns import (
    PAGE_MARKER,
    SECTION,
    APPENDIX,
    CLAUSE,
    SIMPLE_NUMBERED_ITEM,
)
from groundwork.harness.models.section_chunk import SectionChunk
from markdown_it import MarkdownIt
from re import match

def plain_text(inline_token):
    return ''.join(child.content for child in inline_token.children if child.type == 'text')

def matches_heading_pattern(text):
    return bool(
        SECTION.match(text)
        or APPENDIX.match(text)
        or CLAUSE.match(text)
        or SIMPLE_NUMBERED_ITEM.match(text)
    )

def build_chunk(markdown_path):
    with open(markdown_path, encoding="utf-8") as f:
        text = f.read()

    md = MarkdownIt()
    tokens = md.parse(text)
    current_page = 1
    current_section_key = None
    open_chunk = None
    it = iter(tokens)
    chunks = []

    inside_table = False

    for token in it:
        if token.type == 'html_block':
            if page_num := PAGE_MARKER.match(token.content):
                current_page = int(page_num.group(1))
                continue

        if token.type == 'table_open':
            inside_table = True
        elif token.type == 'table_close':
            inside_table = False 

        if token.type == 'heading_open':
            text = plain_text(next(it))
            if open_chunk is not None:
                chunks.append(open_chunk)
            open_chunk = {'heading': text, 'content': ''}

        elif token.type == 'inline' and not inside_table:
            text = plain_text(token)
            if matches_heading_pattern(text):
                if open_chunk is not None:
                    chunks.append(open_chunk)
                open_chunk = {'heading': text, 'content': ''}
            elif open_chunk is not None:
                open_chunk['content'] += text

        elif open_chunk is not None:
            open_chunk['content'] += token.content

    return chunks

chunks = build_chunk("/Users/dylangee/workspace/groundwork/src/groundwork/vertical/data/outputs/ITT Water Plan - Final 020926.md")
print(chunks)
# for chunk in chunks:
#     if 'SECTION' in chunk.content:
#         print(chunk)


    # function build_chunks(markdown_text):
#     lines = split into lines
#     current_page = 1
#     current_section_key = null      # tracks nearest enclosing SECTION for unnumbered sub-headers
#     raw_chunks = []
#     open_chunk = null

#     for each line in lines:
#         if line matches page_marker_pattern ("<!-- page: N -->"):
#             current_page = extracted N
#             continue

#         if line is a heading (starts with #, ##, ###, or ####):
#             heading_text = strip_markdown_and_html(line)

#             if open_chunk exists:
#                 close open_chunk (its content = everything since it opened)
#                 append open_chunk to raw_chunks

#             numbering_key = try_match_section_pattern(heading_text)      # "SECTION 4" -> "4"
#                          or try_match_appendix_pattern(heading_text)     # "Appendix 3" -> "A3"
#                          or try_match_clause_pattern(heading_text)       # "4.1.3.2 ..." -> "4.1.3.2"
#                          or null                                        # unnumbered sub-header

#             if numbering_key is a top-level SECTION or Appendix key:
#                 current_section_key = numbering_key
#                 parent_key = null
#             else if numbering_key is a clause pattern:
#                 parent_key = numbering_key with last segment dropped
#             else:
#                 # unnumbered sub-header (e.g. "Strategic Context and Drivers")
#                 numbering_key = generate_slug(heading_text)
#                 parent_key = current_section_key

#             section_type = classify_section_type(heading_text)   # keyword rules, LLM fallback

#             open_chunk = new_chunk(
#                 numbering_key, parent_key, section_type,
#                 heading_text, start_page = current_page
#             )
#         else:
#             if open_chunk exists:
#                 append line to open_chunk.content
#             # else: content before the first heading (title page, etc.) — handle separately

#     close and append final open_chunk

#     # second pass: sequence + page ranges
#     for i, chunk in enumerate(raw_chunks):
#         chunk.position = i
#         chunk.prev_id = raw_chunks[i-1].id if i > 0 else null
#         chunk.next_id = raw_chunks[i+1].id if i < len(raw_chunks)-1 else null
#         chunk.page_end = max page seen while this chunk was open

#     return raw_chunks