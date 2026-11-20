"""
diff_utils.py
Pure Python diff comparison utility for Privacy Policy and Terms & Conditions.
Generates clean HTML diff outputs without requiring any client-side JavaScript.
"""

import difflib
import html


def get_diff_statistics(old_text, new_text):
    """
    Computes statistical overview of changes between old and new text.
    """
    old_lines = (old_text or '').splitlines()
    new_lines = (new_text or '').splitlines()

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    additions = 0
    deletions = 0
    unchanged = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            deletions += (i2 - i1)
            additions += (j2 - j1)
        elif tag == 'delete':
            deletions += (i2 - i1)
        elif tag == 'insert':
            additions += (j2 - j1)
        elif tag == 'equal':
            unchanged += (i2 - i1)

    return {
        'old_line_count': len(old_lines),
        'new_line_count': len(new_lines),
        'additions': additions,
        'deletions': deletions,
        'unchanged': unchanged,
        'is_identical': (additions == 0 and deletions == 0)
    }


def generate_inline_diff(old_text, new_text):
    """
    Generates a unified line-by-line diff with clean HTML tags.
    - Added lines: <div class="diff-line diff-add"><span class="diff-sign">+</span> ...</div>
    - Deleted lines: <div class="diff-line diff-del"><span class="diff-sign">-</span> ...</div>
    - Unchanged lines: <div class="diff-line diff-context"><span class="diff-sign"> </span> ...</div>
    """
    old_lines = (old_text or '').splitlines()
    new_lines = (new_text or '').splitlines()

    differ = difflib.ndiff(old_lines, new_lines)
    html_lines = []

    for line in differ:
        code = line[:2]
        content = html.escape(line[2:])

        if code == '+ ':
            html_lines.append(
                f'<div class="diff-line diff-add"><span class="diff-marker">[+]</span> {content or "&nbsp;"}</div>'
            )
        elif code == '- ':
            html_lines.append(
                f'<div class="diff-line diff-del"><span class="diff-marker">[-]</span> {content or "&nbsp;"}</div>'
            )
        elif code == '  ':
            html_lines.append(
                f'<div class="diff-line diff-same"><span class="diff-marker">[ ]</span> {content or "&nbsp;"}</div>'
            )
        elif code == '? ':
            # ndiff intra-line guidance marker; skip or style subtly
            continue

    if not html_lines:
        return '<p><em>No content available to compare.</em></p>'

    return '\n'.join(html_lines)


def generate_side_by_side_diff(old_text, new_text):
    """
    Produces side-by-side table rows comparing Old vs New version.
    Returns a list of tuples: (left_num, left_type, left_text, right_num, right_type, right_text)
    Types: 'equal', 'delete', 'insert', 'replace', 'empty'
    """
    old_lines = (old_text or '').splitlines()
    new_lines = (new_text or '').splitlines()

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    rows = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for old_idx, new_idx in zip(range(i1, i2), range(j1, j2)):
                rows.append((
                    old_idx + 1, 'equal', html.escape(old_lines[old_idx]),
                    new_idx + 1, 'equal', html.escape(new_lines[new_idx])
                ))
        elif tag == 'replace':
            max_len = max(i2 - i1, j2 - j1)
            for k in range(max_len):
                old_idx = i1 + k if (i1 + k) < i2 else None
                new_idx = j1 + k if (j1 + k) < j2 else None

                left_num = old_idx + 1 if old_idx is not None else ''
                left_type = 'delete' if old_idx is not None else 'empty'
                left_text = html.escape(old_lines[old_idx]) if old_idx is not None else ''

                right_num = new_idx + 1 if new_idx is not None else ''
                right_type = 'insert' if new_idx is not None else 'empty'
                right_text = html.escape(new_lines[new_idx]) if new_idx is not None else ''

                rows.append((left_num, left_type, left_text, right_num, right_type, right_text))
        elif tag == 'delete':
            for old_idx in range(i1, i2):
                rows.append((
                    old_idx + 1, 'delete', html.escape(old_lines[old_idx]),
                    '', 'empty', ''
                ))
        elif tag == 'insert':
            for new_idx in range(j1, j2):
                rows.append((
                    '', 'empty', '',
                    new_idx + 1, 'insert', html.escape(new_lines[new_idx])
                ))

    return rows
