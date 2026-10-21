import logging
from typing import List, Dict, Tuple
import re
import random
from docx import Document
logger = logging.getLogger(__name__)




class QuizSplitter:    
    @staticmethod
    def parse_quiz_file(content: str, correct_marker: str = '#') -> List[Dict]:
        """
        Parse quiz file with support for multiple formats.
        Tries all applicable parsers and returns the best result.
        """
        all_results = []

        
        # 1. Check for Uzbek/separator format FIRST (before cleaning)
        if '====' in content:
            separator_count = content.count('====')
            if separator_count >= 3:
                logger.info("[PARSER] Trying separator format (====)")
                quizzes = QuizSplitter._parse_separator_format(content, correct_marker)
                if len(quizzes) > 0:
                    all_results.append(('separator', quizzes))
                    logger.info(f"[PARSER] Separator format: {len(quizzes)} quizzes")
        
        # Check for Uzbek format with ++++ separators
        if '++++' in content or '\n++++\n' in content:
            logger.info("[PARSER] Trying Uzbek separator format (====, ++++)")
            quizzes = QuizSplitter._parse_uzbek_format(content, correct_marker)
            if len(quizzes) > 0:
                all_results.append(('uzbek', quizzes))
                logger.info(f"[PARSER] Uzbek format: {len(quizzes)} quizzes")
        
        # 2. Check for question mark format (BEFORE cleaning)
        if re.search(r'^\?', content, re.MULTILINE):
            logger.info("[PARSER] Trying question mark format")
            quizzes = QuizSplitter._parse_question_mark_format(content)
            if len(quizzes) > 0:
                all_results.append(('question_mark', quizzes))
                logger.info(f"[PARSER] Question mark format: {len(quizzes)} quizzes")
        
        # 3. **NEW** Check for plus/minus format (BEFORE cleaning to preserve #)
        if re.search(r'^#\s*.+', content, re.MULTILINE) or re.search(r'^[+-]\s*\w+', content, re.MULTILINE):
            logger.info("[PARSER] Trying plus/minus format")
            quizzes = QuizSplitter._parse_plus_minus_format(content)  # Use RAW content!
            if len(quizzes) > 0:
                all_results.append(('plus_minus', quizzes))
                logger.info(f"[PARSER] Plus/minus format: {len(quizzes)} quizzes")        
        # NOW clean for other formats
        content_cleaned = QuizSplitter._clean_content(content)
        logger.info("[DEBUG] CLEANED CONTENT SAMPLE:")
        logger.info(content_cleaned[:1000])
        
        # 4. Lettered options format
        if re.search(r'^\d+\.\s+.+?\n[A-E]\)', content_cleaned, re.MULTILINE | re.DOTALL):
            logger.info("[PARSER] Trying lettered options format")
            quizzes = QuizSplitter._parse_lettered_options_format(content_cleaned)
            if len(quizzes) > 0:
                all_results.append(('lettered', quizzes))
                logger.info(f"[PARSER] Lettered format: {len(quizzes)} quizzes")

        # INLINE must be detected on RAW content
        INLINE_OPTIONS_DETECTOR = r'^[^\n]+\n\s*[A-E]\)\s*.+?(?:\s+[A-E]\)\s*.+?)+'
        if re.search(INLINE_OPTIONS_DETECTOR, content, re.MULTILINE | re.DOTALL):
            logger.info("[PARSER] Trying inline options format")
            quizzes = QuizSplitter._parse_inline_options_format(content)
            if quizzes:
                all_results.append(('inline_options', quizzes))

        logger.info(
            f"[DEBUG] Inline detector match: "
            f"{bool(re.search(INLINE_OPTIONS_DETECTOR, content_cleaned, re.MULTILINE | re.DOTALL))}"
        )


        # 5. Excel/TSV format
        if '\t' in content_cleaned:
            first_line = content_cleaned.split('\n')[0]
            tab_count = first_line.count('\t')
            if tab_count >= 3:
                logger.info("[PARSER] Trying Excel/TSV format")
                quizzes = QuizSplitter._parse_excel_format(content_cleaned)
                if len(quizzes) > 0:
                    all_results.append(('excel', quizzes))
                    logger.info(f"[PARSER] Excel/TSV format: {len(quizzes)} quizzes")
        
        # 6. Table format
        if '|' in content_cleaned and (re.search(r'\d+\s*\|', content_cleaned) or re.search(r'[A-F]\s*\|', content_cleaned)):
            logger.info("[PARSER] Trying table format")
            quizzes = QuizSplitter._parse_table_format(content_cleaned)
            if len(quizzes) > 0:
                all_results.append(('table', quizzes))
                logger.info(f"[PARSER] Table format: {len(quizzes)} quizzes")
        
        # 7. Moodle percentage format
        if re.search(r'\d+\.\s*.+?\{~%\d+%', content_cleaned, re.DOTALL):
            logger.info("[PARSER] Trying Moodle percentage format")
            quizzes = QuizSplitter._parse_moodle_percentage_format(content_cleaned)
            if len(quizzes) > 0:
                all_results.append(('moodle', quizzes))
                logger.info(f"[PARSER] Moodle format: {len(quizzes)} quizzes")
        
        # 8. Standard format (fallback)
        logger.info("[PARSER] Trying standard format")
        quizzes = QuizSplitter._parse_standard_format(content_cleaned, correct_marker)
        if len(quizzes) > 0:
            all_results.append(('standard', quizzes))
            logger.info(f"[PARSER] Standard format: {len(quizzes)} quizzes")
        
        # Pick the best result (most quizzes with valid structure)
        if not all_results:
            logger.warning("[PARSER] No parsers succeeded")
            return []
        
        # Score each result: count valid quizzes (2+ options, has correct answer)
        best_format = None
        best_score = 0
        best_quizzes = []
        
        for format_name, quizzes in all_results:
            valid_count = sum(1 for q in quizzes 
                            if len(q.get('options', [])) >= 2 
                            and len(q.get('options', [])) <= 20  # Reasonable limit
                            and (q.get('correct_answer') is not None or q.get('correct_answers') is not None))
            
            logger.info(f"[PARSER] {format_name}: {len(quizzes)} total, {valid_count} valid")
            
            if valid_count > best_score:
                best_score = valid_count
                best_format = format_name
                best_quizzes = quizzes
        
        logger.info(f"[PARSER] ✅ Selected format: {best_format} with {best_score} valid quizzes")
        return best_quizzes
        
    @staticmethod
    def _is_question_line(line: str) -> bool:
        """
        Question can start with:
        - #
        - 1.
        - 12.
        - 1)
        - ?
        """
        return (
            line.startswith('?') or
            line.startswith('#') or
            re.match(r'^\d+[\.\)]\s*', line) is not None
        )

    @staticmethod
    def extract_text_with_bold_markers(docx_path):
        """Extract text from DOCX and mark bold text"""
        doc = Document(docx_path)
        content = []
        
        for para in doc.paragraphs:
            line_parts = []
            for run in para.runs:
                text = run.text
                if run.bold:
                    # Mark bold text so parser can detect it
                    text = f"#{text}"
                line_parts.append(text)
            
            if line_parts:
                content.append(''.join(line_parts))
        
        return '\n'.join(content)

    @staticmethod
    def _parse_inline_options_format(content: str) -> List[Dict]:
        """
        Parse inline options format where options appear on the same line or next line.
        Handles both single-line and multi-line variants.
        """
        quizzes = []
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        
        logger.info(f"[INLINE PARSER] Total lines to process: {len(lines)}")

        # Pattern for inline options (both upper and lowercase, more flexible)
        INLINE_OPTION_PATTERN = r'([A-Ea-e])\)\s*(.+?)(?=\s+[A-Ea-e]\)|$)'
        
        # Pattern for multi-line separated options (one per line, case-insensitive)
        SEPARATED_OPTION_PATTERN = r'^([A-Ea-e])\)?\s*(.+)$'
        
        # Pattern for capitalized single-word options (Goes, Have, Plays, etc.)
        SINGLE_WORD_OPTION_PATTERN = r'^([A-E])\)\s*([A-Z][a-z]+|[A-Z]+|--|[\w\s\-/]+)$'

        i = 0
        question_count = 0
        skipped_count = 0
        
        while i < len(lines):
            current_line = lines[i]
            
            # Skip header/separator lines
            if re.match(r'^[\+\-=\|]{3,}$', current_line):
                i += 1
                continue
            
            # Skip lines that are likely headers
            if any(keyword in current_line.lower() for keyword in 
                ['fakultet', 'kafedra', 'test', 'variant', 'respublik', 'vazirligi', 'kelishildi']):
                i += 1
                continue
            
            # Skip very short lines that can't be questions
            if len(current_line) <= 2:
                i += 1
                continue
            
            # Check if this line starts with a question number OR is just a question
            question_num_match = re.match(r'^(\d+)\.\s*(.+)', current_line)
            
            # Also handle lines that might be questions without numbers
            if question_num_match:
                question_num = question_num_match.group(1)
                question_text = question_num_match.group(2).strip()
            else:
                # Check if this could be a question (doesn't start with option letter)
                if not re.match(r'^[A-Ea-e]\)\s*', current_line):
                    question_num = "unnumbered"
                    question_text = current_line.strip()
                else:
                    i += 1
                    continue
            
            # CASE 1: Question and options on same line
            option_matches = list(re.finditer(INLINE_OPTION_PATTERN, question_text))
            
            if option_matches and len(option_matches) >= 2:
                first_option_pos = option_matches[0].start()
                pure_question = question_text[:first_option_pos].strip()
                options = [m.group(2).strip() for m in option_matches]
                
                if len(pure_question) >= 2 or pure_question == "":  # Allow empty question if we have options
                    # If question is empty, use placeholder
                    if not pure_question:
                        pure_question = f"Question {question_num}"
                    
                    quizzes.append({
                        'question': pure_question,
                        'options': options,
                        'correct_answer': 0
                    })
                    question_count += 1
                    logger.debug(f"[INLINE] Q{question_num}: Same line format, {len(options)} options")
                i += 1
                continue
            
            # CASE 2: Options on next line(s)
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                # Sub-case A: Inline options on next line
                inline_matches = list(re.finditer(INLINE_OPTION_PATTERN, next_line))
                
                if inline_matches and len(inline_matches) >= 2:
                    options = [m.group(2).strip() for m in inline_matches]
                    
                    if len(question_text) >= 1:  # More lenient - allow 1 char questions
                        quizzes.append({
                            'question': question_text,
                            'options': options,
                            'correct_answer': 0
                        })
                        question_count += 1
                        logger.debug(f"[INLINE] Q{question_num}: Next line inline, {len(options)} options")
                    i += 2
                    continue
                
                # Sub-case B: Separated options (one per line)
                elif re.match(SEPARATED_OPTION_PATTERN, next_line):
                    options = []
                    j = i + 1
                    expected_letter = 'A'
                    
                    while j < len(lines) and j < i + 10:
                        line = lines[j].strip()
                        option_match = re.match(SEPARATED_OPTION_PATTERN, line)
                        
                        if option_match:
                            letter = option_match.group(1).upper()
                            option_text = option_match.group(2).strip()
                            
                            # Be more flexible - allow any letter sequence
                            if ord(letter) >= ord('A') and ord(letter) <= ord('E'):
                                options.append(option_text)
                                j += 1
                            else:
                                break
                        else:
                            break
                    
                    if len(options) >= 2 and len(question_text) >= 1:
                        quizzes.append({
                            'question': question_text,
                            'options': options,
                            'correct_answer': 0
                        })
                        question_count += 1
                        logger.debug(f"[INLINE] Q{question_num}: Separated format, {len(options)} options")
                        i = j
                        continue
            
            # CASE 3: Check if the question text itself contains a letter pattern like "A. Her B) He's C) She D) We"
            # This handles cases like question 4 in the document
            letter_pattern_match = re.search(r'\b([A-E])\.\s*(.+?)(?:\s+([A-E])\)|\s+([A-E])\.|$)', question_text)
            if letter_pattern_match:
                # Try to extract options using both .) and ) patterns
                modified_pattern = r'([A-E])[\.\)]\s*([^A-E]+?)(?=\s*[A-E][\.\)]|$)'
                letter_matches = list(re.finditer(modified_pattern, question_text))
                
                if len(letter_matches) >= 2:
                    # Find where options start
                    first_match_pos = letter_matches[0].start()
                    pure_question = question_text[:first_match_pos].strip()
                    options = [m.group(2).strip() for m in letter_matches]
                    
                    if options:
                        if not pure_question:
                            pure_question = f"Question {question_num}"
                        
                        quizzes.append({
                            'question': pure_question,
                            'options': options,
                            'correct_answer': 0
                        })
                        question_count += 1
                        logger.debug(f"[INLINE] Q{question_num}: Letter pattern format, {len(options)} options")
                    i += 1
                    continue
            
            # If we reach here, question was numbered/identified but no valid options found
            skipped_count += 1
            i += 1
        
        logger.info(f"[INLINE PARSER] Successfully parsed: {question_count}, Skipped: {skipped_count}")
        return quizzes

    @staticmethod
    def _parse_parentheses_options_format(content: str) -> List[Dict]:
        """
        Parse format with numbered questions and A), B), C), D), E) options.
        The correct answer is typically the first option (A) or marked in some way.
        
        Format:
        1. Question text here?
        A) First option (this might be bold in original)
        B) Second option
        C) Third option
        D) Fourth option
        E) Fifth option
        """
        quizzes = []
        lines = content.strip().split('\n')
        
        current_question = None
        current_question_lines = []
        current_options = []
        correct_answer = None
        in_question = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a new question (starts with number followed by period)
            question_match = re.match(r'^(\d+)\.\s*(.+)', line)
            if question_match:
                # Save previous question if exists
                if current_question and current_options and correct_answer is not None:
                    quizzes.append({
                        'question': current_question,
                        'options': current_options,
                        'correct_answer': correct_answer
                    })
                
                # Start new question
                question_text = question_match.group(2).strip()
                current_question_lines = [question_text] if question_text else []
                current_options = []
                correct_answer = None
                in_question = True
                current_question = None
                continue
            
            # Check if this is an option line (A), B), C), D), E))
            option_match = re.match(r'^([A-E])\)\s*(.+)', line)
            if option_match:
                # Finalize question text before processing options
                if in_question and current_question_lines:
                    current_question = ' '.join(current_question_lines).strip()
                    in_question = False
                
                option_letter = option_match.group(1)
                option_text = option_match.group(2).strip()
                
                # Check for correct answer markers or indicators
                is_correct = False
                cleaned_text = option_text
                
                # Check for bold markers (if text contains these phrases, it's likely the correct answer)
                if '(this is bold right answer)' in option_text.lower():
                    is_correct = True
                    cleaned_text = re.sub(r'\(this is bold right answer\)', '', option_text, flags=re.IGNORECASE).strip()
                elif 'this is bold' in option_text.lower():
                    is_correct = True
                    cleaned_text = re.sub(r'\(.*?this is bold.*?\)', '', option_text, flags=re.IGNORECASE).strip()
                # Common markers for correct answers
                elif option_text.startswith('#'):
                    is_correct = True
                    cleaned_text = option_text[1:].strip()
                elif option_text.startswith('# '):
                    is_correct = True
                    cleaned_text = option_text[2:].strip()
                elif option_text.startswith('+'):
                    is_correct = True
                    cleaned_text = option_text[1:].strip()
                elif option_text.startswith('✓') or option_text.startswith('✅'):
                    is_correct = True
                    cleaned_text = option_text[1:].strip()
                # Check if marker is at the end
                elif option_text.endswith('#') or option_text.endswith('+'):
                    is_correct = True
                    cleaned_text = option_text[:-1].strip()
                
                current_options.append(cleaned_text)
                
                if is_correct and correct_answer is None:
                    correct_answer = len(current_options) - 1
                
                continue
            
            # If we're still collecting question text (multi-line question)
            if in_question and not option_match:
                # Skip common separators
                if not re.match(r'^[\+\-=\|]+$', line):
                    current_question_lines.append(line)
        
        # Don't forget the last question
        if current_question and current_options and correct_answer is not None:
            quizzes.append({
                'question': current_question,
                'options': current_options,
                'correct_answer': correct_answer
            })
        
        # If no correct answer was marked, assume first option (A) is correct
        # This is a fallback for cases where bold formatting wasn't detected
        for quiz in quizzes:
            if quiz.get('correct_answer') is None and len(quiz['options']) >= 2:
                quiz['correct_answer'] = 0
        
        return quizzes


    @staticmethod
    def _clean_content(content: str) -> str:
        """Clean content from table artifacts and excessive whitespace."""
        # Remove table borders like +---+ and |---| but PRESERVE ==== and ++++
        content = re.sub(r'\+[-=]+\+', '', content)  # Remove +---+ but not ++++
        content = re.sub(r'\|[-=|]+\|', '', content)
        
        # Remove standalone borders but PRESERVE Uzbek separators
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines
            if not stripped:
                continue
            
            # PRESERVE Uzbek format separators
            if stripped == '====' or stripped == '++++':
                cleaned_lines.append(line)
                continue
            
            # Skip lines that are ONLY table borders (-, |, +, but not ==== or ++++)
            # This regex now excludes pure ==== and ++++
            if re.match(r'^[\+\-\|]+$', stripped) and '=' not in stripped:
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    @staticmethod
    def _parse_uzbek_plus_marker_format(content: str) -> List[Dict]:
        """
        Uzbek format:
        1. Question
        option
        option ++++
        option
        option
        """
        quizzes = []

        blocks = re.split(r'\n(?=\d+\.)', content)

        for block in blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if len(lines) < 3:
                continue

            # Question
            question_line = lines[0]
            question = re.sub(r'^\d+\.\s*', '', question_line).strip()

            options = []
            correct_index = None

            for line in lines[1:]:
                is_correct = '++++' in line
                option_text = line.replace('++++', '').strip()

                if not option_text:
                    continue

                options.append(option_text)

                if is_correct:
                    correct_index = len(options) - 1

            if question and len(options) >= 2 and correct_index is not None:
                quizzes.append({
                    'question': question,
                    'options': options,
                    'correct_answer': correct_index
                })
            else:
                logger.warning(
                    f"[UZ_PLUS PARSER] ❌ Invalid quiz: "
                    f"question={bool(question)}, options={len(options)}, correct={correct_index}"
                )

        logger.info(f"[UZ_PLUS PARSER] Parsed {len(quizzes)} quizzes")
        return quizzes


    @staticmethod
    def _parse_separator_format(content: str, correct_marker: str = '#') -> List[Dict]:
        """
        Parse format with ==== separators.
        Format: 
        ====================================================================
        1. Question text А) # correct Б) wrong В) wrong Г) wrong
        ====================================================================
        """
        quizzes = []
        
        # First, split by the long separator lines (====...)
        separator_pattern = r'={20,}'  # 20 or more equal signs
        blocks = re.split(separator_pattern, content)
        
        for block in blocks:
            block = block.strip()
            if not block or len(block) < 10:
                continue
            
            # Extract question number and text
            question_match = re.match(r'^(\d+)\.\s*(.+)', block, re.DOTALL)
            if not question_match:
                continue
            
            question_num = question_match.group(1)
            rest = question_match.group(2).strip()
            
            # Now parse the question and options
            # Pattern: "Question text А) option Б) option В) option Г) option"
            # Split by Cyrillic letters followed by )
            option_pattern = r'([А-ЯA-Z])\)\s*'
            
            # Find where options start
            option_start = re.search(option_pattern, rest)
            if not option_start:
                continue
            
            # Question is everything before first option
            question_text = rest[:option_start.start()].strip()
            options_text = rest[option_start.start():]
            
            # Split options
            option_parts = re.split(option_pattern, options_text)
            
            options = []
            correct_answer = None
            
            # Process in pairs: [letter, text, letter, text, ...]
            for i in range(1, len(option_parts), 2):
                if i + 1 >= len(option_parts):
                    break
                
                option_letter = option_parts[i]
                option_text = option_parts[i + 1].strip()
                
                # Check for correct marker
                is_correct = False
                if option_text.startswith(correct_marker):
                    is_correct = True
                    option_text = option_text[len(correct_marker):].strip()
                elif option_text.startswith('# '):
                    is_correct = True
                    option_text = option_text[2:].strip()
                
                if option_text:
                    options.append(option_text)
                    if is_correct and correct_answer is None:
                        correct_answer = len(options) - 1
            
            # Validate and add
            if question_text and len(options) >= 2:
                if correct_answer is None:
                    correct_answer = 0  # Fallback to first option
                
                quizzes.append({
                    'question': question_text,
                    'options': options,
                    'correct_answer': correct_answer
                })
                logger.info(f"[SEPARATOR PARSER] ✅ Parsed quiz {question_num}: {len(options)} options, correct={correct_answer}")
            else:
                logger.warning(f"[SEPARATOR PARSER] ❌ Invalid quiz {question_num}: question={bool(question_text)}, options={len(options)}")
        
        return quizzes

    @staticmethod
    def _parse_moodle_percentage_format(content: str) -> List[Dict]:
        """
        Parse Moodle-style format with percentage markers:
        1. Question text?
        {~%0% Wrong option
        ~%100% Correct option
        ~%0% Wrong option}
        
        Handles both single and multiple correct answers.
        For multiple correct answers, stores them as a list in 'correct_answers'.
        For single correct answer, stores as 'correct_answer' (int).
        """
        quizzes = []
        
        # Split into question blocks
        pattern = r'(\d+)\.\s*(.+?)\s*\{(.+?)\}'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        match_count = 0
        for match in matches:
            match_count += 1
            question_num = match.group(1)
            question_text = match.group(2).strip()
            options_block = match.group(3).strip()            
            # Clean question text - remove extra whitespace and newlines
            question_text = ' '.join(question_text.split())
            
            # Skip if question is too short
            if len(question_text) < 5:
                continue
            
            # Parse options from the block
            option_lines = options_block.split('\n')
            
            current_options = []
            correct_indices = []  
            
            for line in option_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Match percentage pattern in the line
                percentage_match = re.search(r'~?%(\d+(?:\.\d+)?)%\s*(.+)', line)
                if not percentage_match:
                    continue
                
                percentage = float(percentage_match.group(1))
                option_text = percentage_match.group(2).strip()
                
                # Clean up option text - remove trailing } and extra whitespace
                option_text = option_text.rstrip('}').strip()
                option_text = ' '.join(option_text.split())
                
                # Skip empty options
                if not option_text or len(option_text) < 1:
                    continue
                
                current_options.append(option_text)
                
                # Track all options with non-zero percentage as correct
                if percentage > 0:
                    correct_indices.append(len(current_options) - 1)
            
            # Build the quiz data with the collected information
            if question_text and len(current_options) >= 2 and len(correct_indices) > 0:                
                # Build quiz dict based on number of correct answers
                if len(correct_indices) == 1:
                    # Single correct answer
                    quiz_dict = {
                        'question': question_text,
                        'options': current_options,
                        'correct_answer': correct_indices[0],
                        'allows_multiple_answers': False
                    }
                else:
                    # Multiple correct answers
                    quiz_dict = {
                        'question': question_text,
                        'options': current_options,
                        'correct_answers': correct_indices,
                        'allows_multiple_answers': True
                    }
                
                quizzes.append(quiz_dict)
            else:
                logger.warning(f"[MOODLE PARSER] ❌ Invalid quiz {match_count}: question={bool(question_text)}, options={len(current_options)}, correct={len(correct_indices)}")
        
        logger.info(f"[MOODLE PARSER] Total matches found: {match_count}, Valid quizzes: {len(quizzes)}")
        return quizzes


    @staticmethod
    def _parse_question_mark_format(content: str) -> List[Dict]:
        """
        Parse format with ? as question separator and +/- for options.
        """
        quizzes = []
        
        # Split by lines starting with ?
        lines = content.split('\n')
        
        current_question = None
        current_options = []
        correct_answer = None
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Check if this is a new question (starts with ?)
            if line.startswith('?'):
                # Save previous question if it exists and is valid
                if current_question and len(current_options) >= 2 and correct_answer is not None:
                    quizzes.append({
                        'question': current_question,
                        'options': current_options,
                        'correct_answer': correct_answer
                    })
                
                # Start new question - remove the ? and any leading whitespace
                question_text = line[1:].strip()
                
                # Skip if question is too short
                if len(question_text) < 5:
                    current_question = None
                    current_options = []
                    correct_answer = None
                    continue
                
                current_question = question_text
                current_options = []
                correct_answer = None
                continue
            
            # Process option lines (start with + or -, followed by tab or space)
            if line.startswith('+') or line.startswith('-'):
                # Extract option text (remove the +/- marker and leading whitespace)
                option_text = line[1:].strip()
                
                # Skip empty options
                if not option_text or len(option_text) < 2:
                    continue
                
                # Add option
                current_options.append(option_text)
                
                # Mark as correct if it starts with +
                if line.startswith('+') and correct_answer is None:
                    correct_answer = len(current_options) - 1
        
        # Don't forget the last question
        if current_question and len(current_options) >= 2 and correct_answer is not None:
            quizzes.append({
                'question': current_question,
                'options': current_options,
                'correct_answer': correct_answer
            })
        
        logger.info(f"[QUESTION_MARK PARSER] Parsed {len(quizzes)} quizzes")
        return quizzes

    @staticmethod
    def _parse_numbered_format(content: str) -> List[Dict]:
        """Parse format with numbered questions and lettered options."""
        quizzes = []
        lines = content.strip().split('\n')
        
        current_question = None
        current_options = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            question_match = re.match(r'^(\d+)\.\s+(.+?)(?:\s+[a-d]\))', line)
            if question_match:
                if current_question and current_options:
                    quizzes.append({
                        'question': current_question,
                        'options': current_options,
                        'correct_answer': 0
                    })
                
                current_question = question_match.group(2).strip()
                current_options = []
                
                option_matches = re.finditer(r'([a-d])\)\s*([^a-d)]+)(?=[a-d]\)|$)', line)
                
                for match in option_matches:
                    option_text = match.group(2).strip()
                    current_options.append(option_text)
        
        if current_question and current_options:
            quizzes.append({
                'question': current_question,
                'options': current_options,
                'correct_answer': 0
            })
        
        return quizzes
    
    @staticmethod
    def _parse_standard_format(content: str, correct_marker: str = '#') -> List[Dict]:
        """Parse standard format with A), B), C) options."""
        quizzes = []
        lines = content.strip().split('\n')
        
        current_question = None
        current_question_lines = []  # Changed: collect multiple lines
        current_options = []
        correct_answer = None
        in_question = False  # Track if we're collecting question lines
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip separator lines completely (====, ----, etc.)
            if re.match(r'^[=\-+|]{3,}$', line):
                continue
            
            # Check for option line - support both Latin (A-Z, a-z) and Cyrillic (а-я, А-Я)
            option_match = re.match(r'^([A-Za-zА-Яа-я0-9])[.)]\s*(.+)', line)
            
            if option_match:
                # Finalize question text before processing first option
                if in_question and current_question_lines:
                    current_question = ' '.join(current_question_lines).strip()
                    in_question = False
                
                option_letter = option_match.group(1)
                option_text = option_match.group(2).strip()
                
                # Remove any trailing separators from option text
                option_text = re.sub(r'\s*[=\-+|]{3,}\s*$', '', option_text).strip()
                
                # Skip if option text is too short after cleaning
                if len(option_text) < 2:
                    continue
                
                is_correct = False
                cleaned_text = option_text
                
                # Check if separator appears after this option (indicates correct answer)
                if '===' in line or '---' in line:
                    is_correct = True
                    cleaned_text = re.sub(r'\s*[=\-+|]{3,}.*$', '', option_text).strip()
                
                if option_text.startswith(correct_marker):
                    is_correct = True
                    cleaned_text = option_text[len(correct_marker):].strip()
                elif option_text.startswith('# '):
                    is_correct = True
                    cleaned_text = option_text[2:].strip()
                elif option_text.startswith('✅') or option_text.startswith('✓'):
                    is_correct = True
                    cleaned_text = option_text[1:].strip()
                elif option_text.startswith('+'):
                    is_correct = True
                    cleaned_text = option_text[1:].strip()
                
                # Only add if we have meaningful text
                if len(cleaned_text) >= 2:
                    current_options.append(cleaned_text)
                    
                    if is_correct and correct_answer is None:
                        correct_answer = len(current_options) - 1
            else:
                # Check if this is a numbered question line (start of new question)
                question_number_match = re.match(r'^(\d+)[.)]\s*(.+)', line)
                
                if question_number_match:
                    # Save previous question if it's complete and valid
                    if current_question and len(current_options) >= 2 and len(current_options) <= 10 and correct_answer is not None:
                        quizzes.append({
                            'question': current_question,
                            'options': current_options,
                            'correct_answer': correct_answer
                        })
                    
                    # Start new question
                    question_text = question_number_match.group(2).strip()
                    question_text = re.sub(r'\s*[=\-+|]{3,}.*$', '', question_text).strip()
                    
                    current_question_lines = [question_text] if question_text else []
                    current_options = []
                    correct_answer = None
                    in_question = True
                    current_question = None
                elif in_question:
                    # This is a continuation of the question (multi-line question)
                    # Clean and add to question lines
                    cleaned_line = re.sub(r'\s*[=\-+|]{3,}.*$', '', line).strip()
                    if cleaned_line and len(cleaned_line) >= 2:
                        # Don't add lines that look like headers
                        if not any(keyword in cleaned_line.lower() for keyword in 
                                ['fakultet', 'kafedra', 'test', 'variant', 'respublik', 'vazirligi', 'kelishildi']):
                            current_question_lines.append(cleaned_line)
        
        # Don't forget the last question - with validation
        if current_question and len(current_options) >= 2 and len(current_options) <= 10 and correct_answer is not None:
            quizzes.append({
                'question': current_question,
                'options': current_options,
                'correct_answer': correct_answer
            })
        
        return quizzes

    @staticmethod
    def _parse_table_format(content: str) -> List[Dict]:
        """Parse table format with | separators and numbered rows."""
        quizzes = []
        lines = content.strip().split('\n')
        
        current_question = None
        current_options = []
        correct_answer = None
        question_started = False
        
        # Track column positions for Uzbek format
        correct_col_idx = None
        wrong_cols_idx = []
        
        for line in lines:
            line = line.strip()
            if not line or '|' not in line:
                continue
            
            # Skip header rows but capture column structure
            if any(keyword in line.lower() for keyword in 
                ['savol', 'javob', 'muqobil', "to'g'ri", 'tartib', 'raqam', 'faculty', 'fakultet']):
                # Detect column positions from header
                parts = [p.strip() for p in line.split('|')]
                for idx, part in enumerate(parts):
                    if "to'g'ri" in part.lower() or 'correct' in part.lower():
                        correct_col_idx = idx
                    elif 'muqobil' in part.lower() or 'alternative' in part.lower():
                        wrong_cols_idx.append(idx)
                continue
            
            # Skip separator lines
            if re.match(r'^[\|\-\+=\s]+$', line):
                continue
            
            # Split by | and clean up parts
            parts = [p.strip() for p in line.split('|') if p.strip()]
            
            if len(parts) < 2:
                continue
            
            marker = parts[0].strip()
            
            # Check if this is a question row (numbered 1, 2, 3, etc.)
            if marker.isdigit() or re.match(r'^\d+\.$', marker):
                # Save previous question if exists
                if current_question and current_options and correct_answer is not None:
                    quizzes.append({
                        'question': current_question,
                        'options': current_options,
                        'correct_answer': correct_answer
                    })
                
                # Extract question from parts[1]
                current_question = parts[1].strip() if len(parts) > 1 else ""
                current_options = []
                correct_answer = None
                question_started = True
                
                # Extract correct answer and options from columns
                if len(parts) > 2:
                    # parts[2] is "To'g'ri javob" column
                    correct_text = parts[2].strip()
                    if correct_text and len(correct_text) > 1:
                        # Remove markers
                        correct_text = correct_text.lstrip('#').lstrip('+').strip()
                        current_options.append(correct_text)
                        correct_answer = 0  # First option is correct
                    
                    # parts[3], parts[4], parts[5] are "Muqobil javob" columns
                    for idx in range(3, len(parts)):
                        option_text = parts[idx].strip()
                        if option_text and len(option_text) > 1:
                            # Skip if it's a separator
                            if not re.match(r'^[\+\-=\|]+$', option_text):
                                current_options.append(option_text)
        
        # Add the last question
        if current_question and current_options and correct_answer is not None:
            quizzes.append({
                'question': current_question,
                'options': current_options,
                'correct_answer': correct_answer
            })
        
        return quizzes

    @staticmethod
    def _parse_lettered_options_format(content: str) -> List[Dict]:
        """
        Parse format with numbered questions and A), B), C), D) options.
        Handles multi-line questions and detects correct answers by markers.
        
        Format:
        1. Question text here
        may span multiple lines
        A) First option
        B) Second option
        C) #Correct option (marked with # or other indicator)
        D) Fourth option
        
        2. Next question...
        """
        quizzes = []
        lines = content.strip().split('\n')
        
        current_question = None
        current_question_lines = []
        current_options = []
        correct_answer = None
        in_question = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a new question (starts with number followed by period/dot)
            question_match = re.match(r'^(\d+)\.\s*(.+)', line)
            if question_match:
                # Save previous question if exists
                if current_question and current_options and correct_answer is not None:
                    quizzes.append({
                        'question': current_question,
                        'options': current_options,
                        'correct_answer': correct_answer
                    })
                
                # Start new question
                question_text = question_match.group(2).strip()
                current_question_lines = [question_text] if question_text else []
                current_options = []
                correct_answer = None
                in_question = True
                current_question = None
                continue
            
            # Check if this is an option line (A), B), C), D))
            option_match = re.match(r'^([A-D])\)\s*(.+)', line)
            if option_match:
                # Finalize question text before processing options
                if in_question and current_question_lines:
                    current_question = ' '.join(current_question_lines).strip()
                    in_question = False
                
                option_letter = option_match.group(1)
                option_text = option_match.group(2).strip()
                
                # Check for correct answer markers
                is_correct = False
                cleaned_text = option_text
                
                # Common markers for correct answers
                if option_text.startswith('#'):
                    is_correct = True
                    cleaned_text = option_text[1:].strip()
                elif option_text.startswith('# '):
                    is_correct = True
                    cleaned_text = option_text[2:].strip()
                elif option_text.startswith('+'):
                    is_correct = True
                    cleaned_text = option_text[1:].strip()
                elif option_text.startswith('✓') or option_text.startswith('✅'):
                    is_correct = True
                    cleaned_text = option_text[1:].strip()
                # Check if marker is at the end
                elif option_text.endswith('#') or option_text.endswith('+'):
                    is_correct = True
                    cleaned_text = option_text[:-1].strip()
                
                current_options.append(cleaned_text)
                
                if is_correct and correct_answer is None:
                    correct_answer = len(current_options) - 1
                
                continue
            
            # If we're still collecting question text (multi-line question)
            if in_question and not option_match:
                # Skip common separators
                if not re.match(r'^[\+\-=\|]+$', line):
                    current_question_lines.append(line)
        
        # Don't forget the last question
        if current_question and current_options and correct_answer is not None:
            quizzes.append({
                'question': current_question,
                'options': current_options,
                'correct_answer': correct_answer
            })
        
        # If no correct answer was marked, assume first option (A) is correct
        # This is a fallback for cases where highlighting wasn't converted to markers
        for quiz in quizzes:
            if quiz['correct_answer'] is None and len(quiz['options']) >= 2:
                quiz['correct_answer'] = 0
        
        return quizzes
    
    @staticmethod
    def _parse_uzbek_format(content: str, correct_marker: str = '#') -> List[Dict]:
        quizzes = []

        # Normalize separators safely
        content = re.sub(r'\n\s*\+{3,}\s*\n', '\n++++\n', content)
        content = re.sub(r'\n\s*={3,}\s*\n', '\n====\n', content)

        # Split into question blocks
        question_blocks = content.split('++++')

        for block in question_blocks:
            block = block.strip()
            if not block:
                continue

            parts = [p.strip() for p in block.split('====') if p.strip()]
            if len(parts) < 3:
                continue

            question = parts[0]
            options = []
            correct_answer = None

            for part in parts[1:]:
                text = part.strip()

                if not text:
                    continue

                if text.startswith(correct_marker):
                    cleaned = text[len(correct_marker):].strip()
                    options.append(cleaned)
                    if correct_answer is None:
                        correct_answer = len(options) - 1
                else:
                    options.append(text)

            if len(options) >= 2:
                if correct_answer is None:
                    correct_answer = 0  # safe fallback

                quizzes.append({
                    'question': question,
                    'options': options,
                    'correct_answer': correct_answer
                })

        return quizzes

    @staticmethod
    def _parse_plus_minus_format(content: str) -> List[Dict]:
        quizzes = []

        lines = [l for l in content.splitlines() if True]

        current_question = None
        current_question_lines = []
        current_options = []
        correct_answer = None
        in_options = False

        def save_current():
            if (
                current_question
                and len(current_options) >= 2
                and correct_answer is not None
            ):
                quizzes.append({
                    'question': current_question,
                    'options': current_options,
                    'correct_answer': correct_answer
                })

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # QUESTION - "1#", "2#" style
            number_hash_match = re.match(r'^(\d+)\s*#\s*(.+)', line)
            if number_hash_match:
                save_current()
                current_question_lines = [number_hash_match.group(2).strip()]
                current_question = current_question_lines[0]
                current_options = []
                correct_answer = None
                in_options = False
                continue

            # CORRECT OPTION (+)
            if line.startswith('+'):
                if not in_options and current_question_lines:
                    current_question = '\n'.join(current_question_lines).strip()
                in_options = True
                option = line[1:].strip().rstrip('.;')
                option = re.sub(r'^[A-Fa-f]\)\s*', '', option)
                if option:
                    current_options.append(option)
                    if correct_answer is None:
                        correct_answer = len(current_options) - 1
                continue

            # WRONG OPTION (-)
            if line.startswith('-'):
                if not in_options and current_question_lines:
                    current_question = '\n'.join(current_question_lines).strip()
                in_options = True
                option = line[1:].strip().rstrip('.;')
                option = re.sub(r'^[A-Fa-f]\)\s*', '', option)
                if option:
                    current_options.append(option)
                continue

            # WRONG OPTION (=)
            if line.startswith('='):
                if not in_options and current_question_lines:
                    current_question = '\n'.join(current_question_lines).strip()
                in_options = True
                option = line[1:].strip().rstrip('.;')
                option = re.sub(r'^[A-Fa-f]\)\s*', '', option)
                if option:
                    current_options.append(option)
                continue

            is_top_level_question = (
                line.startswith('?') or
                line.startswith('*') or
                re.match(r'^\d+[\.\)]\s+\S', line)
            )

            if is_top_level_question and not (current_question_lines and not in_options and re.match(r'^\d+[\.\)]\s+', line) and current_question_lines):
                if current_question_lines and not in_options:
                    current_question_lines.append(line)
                    continue
                else:
                    save_current()
                    cleaned = line.lstrip('*').lstrip('?').strip()
                    cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
                    current_question_lines = [cleaned]
                    current_question = cleaned
                    current_options = []
                    correct_answer = None
                    in_options = False
                    continue

            # ── KEY FIX ──────────────────────────────────────────────────────────
            # Lines like "a) text b) text c) text d) text" are Mazmunlar content
            # that belongs to the question body. They must NOT be consumed as answer
            # options while we are still collecting the question (in_options=False).
            # Only skip to the body-append path; never treat them as quiz options.
            if not in_options and re.match(r'^[a-dA-D]\)\s*\S', line):
                # This is a lettered sub-content line (Mazmunlar), not a quiz option.
                # Append it to the question body.
                if current_question_lines:
                    current_question_lines.append(line)
                continue
            # ─────────────────────────────────────────────────────────────────────

            # Plain line — if collecting question body, append; else skip
            if current_question_lines and not in_options:
                if not any(kw in line.lower() for kw in
                        ['fakultet', 'kafedra', 'test', 'variant', 'respublik', 'vazirligi', 'kelishildi']):
                    current_question_lines.append(line)
                continue

        save_current()
        return quizzes

        
    @staticmethod
    def _parse_excel_format(content: str) -> List[Dict]:
        """Parse Excel format with tab-separated values."""
        quizzes = []
        lines = content.strip().split('\n')
        
        start_idx = 0
        if lines and any(keyword in lines[0].lower() for keyword in 
                        ['question', 'savol', 'вопрос', 't/r', 'tibbiy']):
            start_idx = 1
        
        for line_idx in range(start_idx, len(lines)):
            line = lines[line_idx].strip()
            if not line:
                continue
            
            parts = [p.strip() for p in line.split('\t') if p.strip()]
            
            if len(parts) < 3:
                continue
            
            question = parts[0]
            options = []
            correct_answer = None
            
            for idx, part in enumerate(parts[1:]):
                if part.startswith('#'):
                    correct_answer = len(options)
                    options.append(part[1:].strip())
                elif part.startswith('+'):
                    correct_answer = len(options)
                    options.append(part[1:].strip())
                elif part.startswith('✅'):
                    correct_answer = len(options)
                    options.append(part[1:].strip())
                else:
                    options.append(part)
            
            if correct_answer is None and len(options) >= 2:
                for idx, opt in enumerate(options):
                    if '#' in opt:
                        correct_answer = idx
                        options[idx] = opt.replace('#', '').strip()
                        break
                
                if correct_answer is None:
                    correct_answer = 0
            
            if len(options) >= 2 and correct_answer is not None:
                quizzes.append({
                    'question': question,
                    'options': options,
                    'correct_answer': correct_answer
                })
        
        return quizzes

    @staticmethod
    def get_split_options() -> List[int]:
        """Get available batch size options."""
        return [10, 20, 30, 40, 50, 100]
    
    @staticmethod
    def split_quizzes(quizzes: List[Dict], batch_size: int) -> List[List[Dict]]:
        """Split quizzes into batches of specified size."""
        if batch_size <= 0:
            raise ValueError("Batch size must be positive")
        
        batches = []
        for i in range(0, len(quizzes), batch_size):
            batches.append(quizzes[i:i + batch_size])
        
        return batches


    @staticmethod
    def calculate_batches(total_quizzes: int, batch_size: int) -> Tuple[int, int]:
        """Calculate number of batches and remaining quizzes."""
        if batch_size <= 0:
            raise ValueError("Batch size must be positive")
        
        full_batches = total_quizzes // batch_size
        remainder = total_quizzes % batch_size
        
        total_batches = full_batches + (1 if remainder > 0 else 0)
        last_batch_size = remainder if remainder > 0 else batch_size
        
        return total_batches, last_batch_size





def validate_quiz_structure(quizzes: List[Dict]) -> Tuple[bool, List[str]]:
    """Validate quiz structure and return issues."""
    issues = []
    valid_quizzes = []
    
    if not quizzes:
        issues.append("No quizzes found in file")
        return False, issues
    
    for idx, quiz in enumerate(quizzes, 1):
        is_valid = True
        
        if not quiz.get('question') or len(quiz.get('question', '').strip()) < 5:
            issues.append(f"Quiz {idx}: Missing or too short question")
            is_valid = False
        
        if not quiz.get('options') or len(quiz['options']) < 2:
            issues.append(f"Quiz {idx}: Less than 2 options")
            is_valid = False
        
        # Check for both single and multiple answer formats
        has_single_answer = quiz.get('correct_answer') is not None
        has_multiple_answers = quiz.get('correct_answers') is not None
        
        if not has_single_answer and not has_multiple_answers:
            issues.append(f"Quiz {idx}: No correct answer marked")
            is_valid = False
        elif has_single_answer:
            # Validate single answer
            if quiz.get('correct_answer', -1) >= len(quiz.get('options', [])):
                issues.append(f"Quiz {idx}: Correct answer index out of range")
                is_valid = False
        elif has_multiple_answers:
            # Validate multiple answers
            correct_answers = quiz.get('correct_answers', [])
            if not correct_answers or not isinstance(correct_answers, list):
                issues.append(f"Quiz {idx}: Invalid multiple correct answers format")
                is_valid = False
            elif any(idx >= len(quiz.get('options', [])) for idx in correct_answers):
                issues.append(f"Quiz {idx}: One or more correct answer indices out of range")
                is_valid = False
        
        if is_valid:
            valid_quizzes.append(quiz)
    
    return len(valid_quizzes) > 0, issues